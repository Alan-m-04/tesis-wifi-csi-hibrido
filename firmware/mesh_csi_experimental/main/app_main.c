/* SPDX-License-Identifier: Apache-2.0
 * Experimental source only: no claim of ESP-IDF compilation or physical use.
 * Mesh initialization follows Espressif's v5.4 internal_communication example
 * (CC0/public domain); attribution and immutable provenance are in NOTICE.md.
 */
#include <inttypes.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "sdkconfig.h"
#include "esp_event.h"
#include "esp_idf_version.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_mesh.h"
#include "esp_netif.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "esp_wifi_default.h"
#include "nvs_flash.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "driver/uart.h"
#include "wire.h"

#if !CONFIG_IDF_TARGET_ESP32S3
#error This experimental variant targets ESP32-S3 only.
#endif
#if ESP_IDF_VERSION_MAJOR != 5 || ESP_IDF_VERSION_MINOR != 4
#error Use the retained ESP-IDF v5.4 toolchain for this experimental candidate.
#endif
#if !CONFIG_ESP_CONSOLE_UART_DEFAULT || CONFIG_ESP_CONSOLE_UART_NUM != 0
#error This experimental transport requires UART0 console on the existing pins.
#endif
#if CONFIG_IDF_TARGET_ESP32S3 && !CONFIG_ESP_WIFI_CSI_ENABLED
#error CSI must be enabled.
#endif

#define EVENT_RESERVE 20000u
#define ROUTE_CAPACITY 16
typedef struct { uint8_t kind; union { tcsi_sample_t csi; char event[256]; }; } record_t;
static QueueHandle_t records;
static esp_netif_t *netif_sta;
static uint8_t own_mac[6], source_mac[6], parent_mac[6];
static uint32_t topology_epoch, callback_id, queue_drops;
static uint8_t layer;
static bool connected;
static portMUX_TYPE state_lock = portMUX_INITIALIZER_UNLOCKED;

static void drop_record(void) {
    portENTER_CRITICAL(&state_lock); queue_drops++; portEXIT_CRITICAL(&state_lock);
}
static void event_record(const char *fmt, ...) {
    record_t item = {.kind=TCSI_KIND_EVENT};
    va_list ap; va_start(ap,fmt);
    int n=vsnprintf(item.event,sizeof(item.event),fmt,ap); va_end(ap);
    if(n<0 || n>=(int)sizeof(item.event) || xQueueSend(records,&item,0)!=pdTRUE) drop_record();
}
static bool parse_mac(const char *text, uint8_t out[6]) {
    unsigned v[6]; int n=0;
    if(strlen(text)!=17 || sscanf(text,"%2x:%2x:%2x:%2x:%2x:%2x%n",&v[0],&v[1],&v[2],&v[3],&v[4],&v[5],&n)!=6 || n!=17) return false;
    bool any=false;
    for(int i=0;i<6;i++) { if(v[i]>255) return false; out[i]=(uint8_t)v[i]; any|=v[i]!=0; }
    return any && !(out[0]&1u);
}
static void writer_task(void *arg) {
    (void)arg;
    record_t item;
    uint8_t frame[TCSI_FRAME_MAX]; uint32_t seq=0;
    for(;;) {
        if(xQueueReceive(records,&item,portMAX_DELAY)!=pdTRUE) continue;
        size_t n=item.kind==TCSI_KIND_CSI ?
            tcsi_encode_sample(frame,sizeof(frame),CONFIG_TESIS_EXP_NODE_ID,seq,&item.csi) :
            tcsi_encode_event(frame,sizeof(frame),CONFIG_TESIS_EXP_NODE_ID,seq,item.event,strlen(item.event));
        /* Raw UART API: never pass binary CSI through VFS CR/LF conversion. */
        if(!n || uart_write_bytes(UART_NUM_0,frame,n)!=(int)n) abort();
        seq++;
    }
}
static void csi_callback(void *ctx, wifi_csi_info_t *info) {
    (void)ctx;
    if(!info || !info->buf || memcmp(info->mac,source_mac,6)) return;
    record_t item={.kind=TCSI_KIND_CSI};
    tcsi_sample_t *s=&item.csi;
    portENTER_CRITICAL(&state_lock);
    s->callback_id=callback_id++; s->queue_drops=queue_drops;
    s->topology_epoch=topology_epoch; s->layer=layer; memcpy(s->parent_mac,parent_mac,6);
    portEXIT_CRITICAL(&state_lock);
    if(!info->len || info->len>CONFIG_TESIS_EXP_CSI_MAX_BYTES || (info->len&1u)) { drop_record(); return; }
    s->len=info->len; s->first_word_invalid=info->first_word_invalid;
    memcpy(s->source_mac,info->mac,6); memcpy(s->node_mac,own_mac,6);
    const wifi_pkt_rx_ctrl_t *r=&info->rx_ctrl;
    int64_t m[TCSI_META_COUNT]={r->rssi,r->rate,r->sig_mode,r->mcs,r->cwb,r->smoothing,
        r->not_sounding,r->aggregation,r->stbc,r->fec_coding,r->sgi,r->noise_floor,
        r->ampdu_cnt,r->channel,r->secondary_channel,r->timestamp,r->ant,r->sig_len,r->rx_state};
    memcpy(s->meta,m,sizeof(m)); memcpy(s->data,info->buf,info->len);
    if(xQueueSend(records,&item,0)!=pdTRUE) drop_record();
}
static void mesh_handler(void *arg, esp_event_base_t base, int32_t id, void *data) {
    (void)arg; (void)base;
    int reason=0;
    portENTER_CRITICAL(&state_lock);
    switch(id) {
    case MESH_EVENT_PARENT_CONNECTED: {
        mesh_event_connected_t *e=data;
        memcpy(parent_mac,e->connected.bssid,6); layer=(uint8_t)e->self_layer;
        topology_epoch++; connected=true; break;
    }
    case MESH_EVENT_PARENT_DISCONNECTED:
        reason=((mesh_event_disconnected_t*)data)->reason;
        connected=false; topology_epoch++; memset(parent_mac,0,6); layer=0; break;
    case MESH_EVENT_LAYER_CHANGE:
        layer=(uint8_t)((mesh_event_layer_change_t*)data)->new_layer; topology_epoch++; break;
    case MESH_EVENT_CHANNEL_SWITCH:
        topology_epoch++; reason=((mesh_event_channel_switch_t*)data)->channel; break;
    case MESH_EVENT_STOPPED:
        connected=false; topology_epoch++; memset(parent_mac,0,6); layer=0; break;
    default: break;
    }
    uint32_t epoch=topology_epoch; uint8_t current_layer=layer;
    uint8_t parent[6]; memcpy(parent,parent_mac,6);
    portEXIT_CRITICAL(&state_lock);
    event_record("MESH_EVENT t_us=%" PRId64 " event=%" PRId32 " layer=%u epoch=%" PRIu32 " parent=" MACSTR " detail=%d",
                 esp_timer_get_time(),id,current_layer,epoch,MAC2STR(parent),reason);
    if(id==MESH_EVENT_PARENT_CONNECTED && esp_mesh_is_root()) {
        esp_err_t a=esp_netif_dhcpc_stop(netif_sta);
        esp_err_t b=esp_netif_dhcpc_start(netif_sta);
        event_record("ROOT_DHCP stop=%d start=%d",(int)a,(int)b);
    }
}
static void probe_task(void *arg) {
    (void)arg;
    mesh_addr_t routes[ROUTE_CAPACITY]; uint32_t sequence=0;
    const TickType_t period=pdMS_TO_TICKS(1000/CONFIG_TESIS_EXP_HZ);
    TickType_t wake=xTaskGetTickCount();
    for(;;) {
        portENTER_CRITICAL(&state_lock); bool up=connected; portEXIT_CRITICAL(&state_lock);
        if(up && esp_mesh_is_root()) {
            int total=esp_mesh_get_routing_table_size(), count=0;
            if(total>ROUTE_CAPACITY) event_record("ROUTE_OVERFLOW total=%d capacity=%d",total,ROUTE_CAPACITY);
            else if(esp_mesh_get_routing_table(routes,sizeof(routes),&count)==ESP_OK) {
                uint8_t probe[14]={'E','X','P','1'};
                for(int i=0;i<4;i++) probe[4+i]=(uint8_t)(sequence>>(8*i));
                memcpy(probe+8,own_mac,6);
                mesh_data_t packet={.data=probe,.size=sizeof(probe),.proto=MESH_PROTO_BIN,.tos=MESH_TOS_P2P};
                for(int i=0;i<count && i<ROUTE_CAPACITY;i++) {
                    if(!memcmp(routes[i].addr,own_mac,6)) continue;
                    esp_err_t err=esp_mesh_send(&routes[i],&packet,MESH_DATA_P2P,NULL,0);
                    event_record("PROBE_TX t_us=%" PRId64 " seq=%" PRIu32 " to=" MACSTR " result=%d",esp_timer_get_time(),sequence,MAC2STR(routes[i].addr),(int)err);
                }
                sequence++;
            }
        }
        /* No catch-up burst if a blocking Mesh send exceeds one period. */
        if((TickType_t)(xTaskGetTickCount()-wake)>=period) wake=xTaskGetTickCount();
        vTaskDelayUntil(&wake,period);
    }
}
static void receive_task(void *arg) {
    (void)arg;
    uint8_t buf[1500]; mesh_addr_t from; int flags;
    for(;;) {
        mesh_data_t data={.data=buf,.size=sizeof(buf)};
        esp_err_t err=esp_mesh_recv(&from,&data,pdMS_TO_TICKS(1000),&flags,NULL,0);
        if(err!=ESP_OK) { if(err!=ESP_ERR_MESH_TIMEOUT) { event_record("MESH_RX_ERROR code=%d",(int)err); vTaskDelay(pdMS_TO_TICKS(100)); } continue; }
        if(data.size==14 && !memcmp(buf,"EXP1",4)) {
            uint32_t seq=(uint32_t)buf[4]|((uint32_t)buf[5]<<8)|((uint32_t)buf[6]<<16)|((uint32_t)buf[7]<<24);
            event_record("PROBE_RX t_us=%" PRId64 " seq=%" PRIu32 " logical_from=" MACSTR " declared_origin=" MACSTR,
                esp_timer_get_time(),seq,MAC2STR(from.addr),MAC2STR(buf+8));
        } else event_record("MESH_RX_OTHER size=%u",data.size);
    }
}
static void status_task(void *arg) {
    (void)arg;
    for(;;) {
        portENTER_CRITICAL(&state_lock);
        uint32_t drops=queue_drops, callbacks=callback_id, epoch=topology_epoch;
        bool up=connected; uint8_t l=layer;
        portEXIT_CRITICAL(&state_lock);
        event_record("STATUS t_us=%" PRId64 " callbacks=%" PRIu32 " queue_drops=%" PRIu32 " epoch=%" PRIu32 " layer=%u connected=%d",esp_timer_get_time(),callbacks,drops,epoch,l,(int)up);
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
void app_main(void) {
    const char *ssid=CONFIG_TESIS_EXP_ROUTER_SSID, *pass=CONFIG_TESIS_EXP_ROUTER_PASSWORD;
    const char *mesh_pass=CONFIG_TESIS_EXP_MESH_PASSWORD;
    /* Fail before initializing Wi-Fi; never erase NVS to hide an init failure. */
    if(!strlen(ssid) || strlen(ssid)>32 || strlen(pass)<8 || strlen(pass)>63 ||
       strlen(mesh_pass)<8 || strlen(mesh_pass)>63 ||
       (CONFIG_TESIS_EXP_NODE_ID!=0 && !parse_mac(CONFIG_TESIS_EXP_SOURCE_MAC,source_mac)) ||
       !tcsi_budget_fits(CONFIG_ESP_CONSOLE_UART_BAUDRATE,CONFIG_TESIS_EXP_HZ,CONFIG_TESIS_EXP_CSI_MAX_BYTES,EVENT_RESERVE)) {
        fputs("EXPERIMENTAL_CONFIG_REJECTED: check local config and budget; Wi-Fi not started\n",stderr); return;
    }
    esp_log_level_set("*",ESP_LOG_NONE);
    uart_config_t uart={.baud_rate=CONFIG_ESP_CONSOLE_UART_BAUDRATE,.data_bits=UART_DATA_8_BITS,
        .parity=UART_PARITY_DISABLE,.stop_bits=UART_STOP_BITS_1,.flow_ctrl=UART_HW_FLOWCTRL_DISABLE,
        .source_clk=UART_SCLK_DEFAULT};
    ESP_ERROR_CHECK(uart_param_config(UART_NUM_0,&uart));
    if(!uart_is_driver_installed(UART_NUM_0)) ESP_ERROR_CHECK(uart_driver_install(UART_NUM_0,256,4096,0,NULL,0));
    records=xQueueCreate(32,sizeof(record_t));
    if(!records || xTaskCreate(writer_task,"exp_writer",6144,NULL,4,NULL)!=pdPASS) abort();
    event_record("EXPERIMENTAL_V1_NOT_CAPTURE_READY node=%d baud=%d candidate_hz=%d max_csi=%d",
                 CONFIG_TESIS_EXP_NODE_ID,CONFIG_ESP_CONSOLE_UART_BAUDRATE,CONFIG_TESIS_EXP_HZ,CONFIG_TESIS_EXP_CSI_MAX_BYTES);
    uint32_t actual_baud=0; ESP_ERROR_CHECK(uart_get_baudrate(UART_NUM_0,&actual_baud));
    event_record("UART_CONFIG baud_reported=%" PRIu32 " frame=8N1 flow=none",actual_baud);
    ESP_ERROR_CHECK(nvs_flash_init()); ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    ESP_ERROR_CHECK(esp_netif_create_default_wifi_mesh_netifs(&netif_sta,NULL));
    wifi_init_config_t wifi=WIFI_INIT_CONFIG_DEFAULT(); ESP_ERROR_CHECK(esp_wifi_init(&wifi));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_set_bandwidth(WIFI_IF_STA,WIFI_BW_HT20));
    ESP_ERROR_CHECK(esp_wifi_set_bandwidth(WIFI_IF_AP,WIFI_BW_HT20));
    ESP_ERROR_CHECK(esp_wifi_get_mac(WIFI_IF_STA,own_mac));
    uint8_t ap_mac[6]; ESP_ERROR_CHECK(esp_wifi_get_mac(WIFI_IF_AP,ap_mac));
    event_record("NODE_IDENTITY sta=" MACSTR " ap=" MACSTR,MAC2STR(own_mac),MAC2STR(ap_mac));
    if(CONFIG_TESIS_EXP_NODE_ID!=0) {
        wifi_csi_config_t csi={.lltf_en=true,.htltf_en=true,.stbc_htltf2_en=true,
                              .ltf_merge_en=true,.channel_filter_en=true,.manu_scale=false,.shift=false};
        ESP_ERROR_CHECK(esp_wifi_set_csi_config(&csi));
        ESP_ERROR_CHECK(esp_wifi_set_csi_rx_cb(csi_callback,NULL));
        ESP_ERROR_CHECK(esp_wifi_set_csi(true));
        /* No promiscuous mode in this first candidate. Its necessity and
         * coexistence with Mesh must be established by a separate test. */
    }
    ESP_ERROR_CHECK(esp_mesh_init());
    ESP_ERROR_CHECK(esp_event_handler_register(MESH_EVENT,ESP_EVENT_ANY_ID,mesh_handler,NULL));
    ESP_ERROR_CHECK(esp_mesh_set_topology(MESH_TOPO_TREE));
    ESP_ERROR_CHECK(esp_mesh_set_max_layer(4)); ESP_ERROR_CHECK(esp_mesh_disable_ps());
    ESP_ERROR_CHECK(esp_mesh_fix_root(true));
    if(CONFIG_TESIS_EXP_NODE_ID==0) ESP_ERROR_CHECK(esp_mesh_set_type(MESH_ROOT));
    mesh_cfg_t cfg=MESH_INIT_CONFIG_DEFAULT();
    const uint8_t mesh_id[6]={0x54,0x45,0x53,0x49,0x53,0x01}; memcpy(cfg.mesh_id.addr,mesh_id,6);
    cfg.channel=11; cfg.router.ssid_len=strlen(ssid); memcpy(cfg.router.ssid,ssid,strlen(ssid));
    memcpy(cfg.router.password,pass,strlen(pass));
    cfg.mesh_ap.max_connection=4; memcpy(cfg.mesh_ap.password,mesh_pass,strlen(mesh_pass));
    ESP_ERROR_CHECK(esp_mesh_set_ap_authmode(WIFI_AUTH_WPA2_PSK));
    ESP_ERROR_CHECK(esp_mesh_set_config(&cfg));
    ESP_ERROR_CHECK(esp_mesh_start());
    /* Wi-Fi APIs are not called after Mesh starts. Channel/bandwidth fields
     * on each CSI record remain evidence of the actual reception. */
    if(xTaskCreate(probe_task,"exp_probe",4096,NULL,3,NULL)!=pdPASS ||
       xTaskCreate(receive_task,"exp_rx",4096,NULL,3,NULL)!=pdPASS ||
       xTaskCreate(status_task,"exp_status",3072,NULL,2,NULL)!=pdPASS) abort();
}
