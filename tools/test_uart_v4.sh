#!/usr/bin/env bash
# Namespace failure is explicit; this wrapper has no direct-execution fallback.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$root/tools/offline_sandbox.sh" "$root/.venv/bin/python" -B -m unittest discover \
  -s "$root/tests" -p test_uart_v4.py -v
