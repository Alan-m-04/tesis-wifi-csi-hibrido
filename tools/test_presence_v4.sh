#!/usr/bin/env bash
# Fail explicitly if Bubblewrap cannot isolate. No direct-execution fallback.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$root/tools/offline_sandbox.sh" "$root/.venv/bin/python" -B -m unittest discover \
  -s "$root/tests" -p test_persistent_presence_v4.py -v
