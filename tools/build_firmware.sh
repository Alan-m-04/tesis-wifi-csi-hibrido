#!/usr/bin/env bash
# Build only. Requires an already activated official ESP-IDF v5.4 environment.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
case "${1:-}" in
 TX-01) project=csi_send ;; RX-01) project=csi_recv ;; RX-02) project=csi_recv_02 ;;
 *) echo 'Usage: tools/build_firmware.sh TX-01|RX-01|RX-02' >&2; exit 2 ;;
esac
version="$(idf.py --version)"
[[ "$version" =~ ESP-IDF\ v5\.4($|[.\ -]) ]] || { echo 'ESP-IDF v5.4 required' >&2; exit 2; }
exec idf.py -C "$root/firmware/$project" -B "$root/build/$1" -DIDF_TARGET=esp32s3 build
