/* SPDX-License-Identifier: Apache-2.0 */
#include "wire.h"
#include <string.h>
static void put16(uint8_t *p, uint16_t v) { p[0]=(uint8_t)v; p[1]=(uint8_t)(v>>8); }
static void put32(uint8_t *p, uint32_t v) { for(unsigned i=0;i<4;i++) p[i]=(uint8_t)(v>>(8*i)); }
static void put64(uint8_t *p, uint64_t v) { for(unsigned i=0;i<8;i++) p[i]=(uint8_t)(v>>(8*i)); }
uint32_t tcsi_crc32(const uint8_t *p, size_t n) {
    uint32_t crc=UINT32_MAX;
    for(size_t i=0;i<n;i++) { crc^=p[i]; for(unsigned j=0;j<8;j++) crc=(crc>>1)^(0xedb88320u & (0u-(crc&1u))); }
    return crc^UINT32_MAX;
}
static size_t begin(uint8_t *out,size_t cap,uint8_t node,uint32_t seq,uint8_t kind,size_t len) {
    size_t total=TCSI_FRAME_OVERHEAD+len;
    if(!out || node>2 || len>UINT16_MAX || total>cap) return 0;
    memcpy(out,"TCSI",4); out[4]=1; out[5]=kind; out[6]=node; out[7]=0;
    put32(out+8,seq); put16(out+12,(uint16_t)len); put16(out+14,0);
    return total;
}
static void finish(uint8_t *out,size_t total) { put32(out+total-4,tcsi_crc32(out,total-4)); }
size_t tcsi_encode_sample(uint8_t *out,size_t cap,uint8_t node,uint32_t seq,const tcsi_sample_t *s) {
    if(!s || !s->len || s->len>TCSI_MAX_CSI || (s->len&1u) || s->first_word_invalid>1) return 0;
    size_t total=begin(out,cap,node,seq,TCSI_KIND_CSI,TCSI_CSI_FIXED_BYTES+s->len);
    if(!total) return 0;
    uint8_t *p=out+TCSI_HEADER_BYTES;
    put32(p,s->callback_id); put32(p+4,s->queue_drops); put32(p+8,s->topology_epoch);
    p[12]=s->layer; memcpy(p+13,s->source_mac,6); memcpy(p+19,s->node_mac,6); memcpy(p+25,s->parent_mac,6);
    for(unsigned i=0;i<TCSI_META_COUNT;i++) put64(p+31+i*8,(uint64_t)s->meta[i]);
    put16(p+183,s->len); p[185]=s->first_word_invalid; memcpy(p+186,s->data,s->len);
    finish(out,total); return total;
}
size_t tcsi_encode_event(uint8_t *out,size_t cap,uint8_t node,uint32_t seq,const char *event,size_t len) {
    if(!event || !len || len>256) return 0;
    for(size_t i=0;i<len;i++) if((unsigned char)event[i]<32 || (unsigned char)event[i]>126) return 0;
    size_t total=begin(out,cap,node,seq,TCSI_KIND_EVENT,len);
    if(!total) return 0;
    memcpy(out+TCSI_HEADER_BYTES,event,len); finish(out,total); return total;
}
bool tcsi_budget_fits(uint32_t baud,uint32_t hz,uint16_t len,uint32_t events) {
    if(!baud || !hz || hz>100 || !len || len>TCSI_MAX_CSI || (len&1u)) return false;
    uint64_t demand=(TCSI_FRAME_OVERHEAD+TCSI_CSI_FIXED_BYTES+(uint64_t)len)*hz+events;
    return demand*10u*100u <= (uint64_t)baud*80u;
}
