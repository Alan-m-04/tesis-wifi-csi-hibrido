/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TESIS_EXP_WIRE_H
#define TESIS_EXP_WIRE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define TCSI_META_COUNT 19u
#define TCSI_MAX_CSI 1024u
#define TCSI_HEADER_BYTES 16u
#define TCSI_CSI_FIXED_BYTES 186u
#define TCSI_FRAME_OVERHEAD 20u
#define TCSI_FRAME_MAX (TCSI_FRAME_OVERHEAD + TCSI_CSI_FIXED_BYTES + TCSI_MAX_CSI)
#define TCSI_KIND_CSI 1u
#define TCSI_KIND_EVENT 2u
/* Meta order is explicit in docs/PROTOCOLO_MESH_CSI_EXPERIMENTAL.md. */
typedef struct {
    uint32_t callback_id, queue_drops, topology_epoch;
    uint8_t layer, source_mac[6], node_mac[6], parent_mac[6];
    int64_t meta[TCSI_META_COUNT];
    uint16_t len;
    uint8_t first_word_invalid;
    int8_t data[TCSI_MAX_CSI];
} tcsi_sample_t;
uint32_t tcsi_crc32(const uint8_t *data, size_t len);
size_t tcsi_encode_sample(uint8_t *out, size_t cap, uint8_t node, uint32_t seq,
                          const tcsi_sample_t *sample);
size_t tcsi_encode_event(uint8_t *out, size_t cap, uint8_t node, uint32_t seq,
                         const char *event, size_t len);
/* 8N1 bound, 80% ceiling, plus an explicit event/log reserve. Not a benchmark. */
bool tcsi_budget_fits(uint32_t baud, uint32_t hz, uint16_t csi_len,
                      uint32_t event_bytes_per_second);
#endif
