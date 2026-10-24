#!/usr/bin/env bash
# Read-only sources, isolated network, private /dev. No physical serial paths.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec bwrap --unshare-all --die-with-parent --ro-bind /usr /usr --ro-bind /lib /lib --ro-bind /lib64 /lib64 \
 --ro-bind /etc/ld.so.cache /etc/ld.so.cache --ro-bind /etc/localtime /etc/localtime \
 --ro-bind "$root" "$root" --proc /proc --dev /dev --tmpfs /tmp --chdir "$root" \
 --setenv HOME /tmp --setenv PYTHONDONTWRITEBYTECODE 1 --setenv PYTHONPATH "$root/src" "$@"
