#!/usr/bin/env bash
# Run Python regressions + native Node contracts, isolated from devices/network.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
[[ -x .tools/node-v22.20.0/bin/node ]] || { echo 'Prepare pinned runtime with tools/prepare_node.py first' >&2; exit 2; }
if [[ $# -eq 1 ]]; then
 [[ -f "$1" ]] || { echo 'Canonical JSON does not exist' >&2; exit 2; }
 export CSI_CANONICAL_PATH="$(realpath -- "$1")"
fi
./tools/test_base.sh
./tools/offline_sandbox.sh .tools/node-v22.20.0/bin/node --test tests/js/*.test.mjs
