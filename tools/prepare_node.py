#!/usr/bin/env python3
"""Prepare pinned official Node binary locally. No remote installer is executed."""
import hashlib
import json
from pathlib import Path
import platform
import tarfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]


def main():
    lock=json.loads((ROOT/'config/node_runtime.lock.json').read_text())
    if platform.system()!='Linux' or platform.machine()!='x86_64':
        raise SystemExit('This pinned runtime supports Linux x86_64 only')
    root=ROOT/'.tools';root.mkdir(exist_ok=True)
    destination=root/('node-'+lock['version'])
    if destination.exists():
        raise SystemExit('Runtime destination already exists; preserving it')
    manifest=urllib.request.urlopen(lock['base_url']+'SHASUMS256.txt',timeout=30).read()
    expected={name:digest for digest,name in (line.split() for line in manifest.decode().splitlines())}
    if expected.get(lock['archive'])!=lock['archive_sha256']:
        raise SystemExit('Official manifest and pinned hash disagree')
    archive=root/lock['archive']
    with urllib.request.urlopen(lock['base_url']+lock['archive'],timeout=60) as response,archive.open('xb') as out:
        while chunk:=response.read(1024*1024):out.write(chunk)
    with archive.open('rb') as f:
        if hashlib.file_digest(f,'sha256').hexdigest()!=lock['archive_sha256']:
            raise SystemExit('Archive SHA-256 mismatch')
    prefix=lock['archive'].removesuffix('.tar.xz')+'/'
    # Read two allowlisted regular files only; never extract paths, links or scripts.
    with tarfile.open(archive,'r:xz') as tar:
        members={m.name:m for m in tar.getmembers() if m.name in (prefix+'bin/node',prefix+'LICENSE')}
        if len(members)!=2 or any(not m.isfile() or m.size>200_000_000 for m in members.values()):
            raise SystemExit('Unexpected runtime members')
        destination.mkdir();(destination/'bin').mkdir()
        for suffix in ('bin/node','LICENSE'):
            with tar.extractfile(members[prefix+suffix]) as source,(destination/suffix).open('xb') as out:
                while chunk:=source.read(1024*1024):out.write(chunk)
    (destination/'bin/node').chmod(0o755)
    (destination/'SHASUMS256.txt').write_bytes(manifest)
    print(destination/'bin/node')


if __name__=='__main__':main()
