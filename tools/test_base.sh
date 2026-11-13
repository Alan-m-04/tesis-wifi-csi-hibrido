#!/usr/bin/env bash
# Only synthetic PTYs and read-only offline evidence; no host serial devices.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
command -v bwrap >/dev/null
[[ -x "$root/.venv/bin/python" ]] || { echo 'Prepare .venv with requirements-dev.txt' >&2; exit 2; }
args=(--unshare-all --die-with-parent --ro-bind /usr /usr --ro-bind /lib /lib --ro-bind /lib64 /lib64
      --ro-bind /etc/ld.so.cache /etc/ld.so.cache --ro-bind /etc/localtime /etc/localtime
      --ro-bind "$root" "$root" --proc /proc --dev /dev --tmpfs /tmp --chdir "$root"
      --setenv HOME /tmp --setenv PYTHONPATH "$root/src" --setenv PYTHONDONTWRITEBYTECODE 1
      --unsetenv CSI_PHYSICAL_CAPTURE_DIR)
reference="$root/data/raw/dual-60s-20261024T205854Z/captura"
if [[ -d "$reference" ]]; then args+=(--setenv CSI_PHYSICAL_CAPTURE_DIR "$reference"); fi
exec bwrap "${args[@]}" "$root/.venv/bin/python" -B -m unittest discover -s tests -v
