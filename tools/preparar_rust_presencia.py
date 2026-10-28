#!/usr/bin/env python3
"""Prepare two pinned official binary components locally; no installer script."""
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    lock = json.loads((ROOT / 'config/presence_rust_reference.lock.json').read_text())
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        raise SystemExit('Reference compiler supports Linux x86_64 only')
    target = ROOT / lock['destination']
    if target.exists():
        raise SystemExit('Preserving existing compiler; no overwrite')
    cache = ROOT / '.tools/presence-rust-archives'
    cache.mkdir(exist_ok=True)
    extracted = cache / ('components-' + lock['version'])
    extracted.mkdir(exist_ok=False)
    for component in lock['components']:
        name = component['archive']; archive = cache / name
        url = lock['base_url'] + name
        checksum = urllib.request.urlopen(url + '.sha256', timeout=30).read()
        if checksum.decode().split()[0] != component['sha256']:
            raise SystemExit('Official checksum differs from lock')
        if not archive.exists():
            with urllib.request.urlopen(url, timeout=60) as response, archive.open('xb') as out:
                while chunk := response.read(1024 * 1024):
                    out.write(chunk)
        with archive.open('rb') as f:
            if hashlib.file_digest(f, 'sha256').hexdigest() != component['sha256']:
                raise SystemExit('Component SHA-256 mismatch')
        (cache / (name + '.sha256')).write_bytes(checksum)
        # Trusted pinned archive; data filter rejects paths/links escaping the
        # extraction root. install.sh is never executed or imported.
        with tarfile.open(archive, 'r:xz') as tar:
            tar.extractall(extracted, filter='data')
        print('VERIFIED ' + name, flush=True)
    compiler, standard = lock['components']
    compiler_root = extracted / compiler['archive'].removesuffix('.tar.xz') / compiler['component_directory']
    std_root = extracted / standard['archive'].removesuffix('.tar.xz') / standard['component_directory']
    shutil.copytree(compiler_root, target, symlinks=True)
    shutil.copytree(std_root / 'lib', target / 'lib', dirs_exist_ok=True, symlinks=True)
    version = subprocess.check_output([str(target / 'bin/rustc'), '-vV'], text=True)
    with (target / 'preparation.json').open('x') as f:
        json.dump({'lock': lock, 'rustc_verbose_version': version, 'remote_installer_executed': False}, f, indent=2)
        f.write('\n')
    print(version)


if __name__ == '__main__':
    main()
