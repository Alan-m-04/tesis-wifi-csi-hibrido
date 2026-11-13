#!/usr/bin/env python3
"""Offline post-acquisition audit + optional new visualization. Never opens UART."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from controlled_capture import ROOT, sha, dump_new
from validate_capture import audit_capture


def analyze(run,output,visualize=True):
    run=Path(run).resolve();output=Path(output).resolve()
    if not output.is_relative_to(ROOT/'results/local'):raise ValueError('New analysis output must be internal')
    bundle=json.loads((run/'bundle-manifest.json').read_text())
    for item in bundle['files']:
        path=run/item['path']
        if path.is_symlink() or not path.resolve().is_relative_to(run) or not path.is_file():raise ValueError('Unsafe acquisition path')
        if path.stat().st_size!=item['bytes'] or sha(path)!=item['sha256']:raise ValueError('Acquisition integrity mismatch')
    manifest=json.loads((run/'capture-manifest.json').read_text())
    result=audit_capture(run/'capture',manifest)
    output.mkdir(parents=True,exist_ok=False);dump_new(output/'quality.json',result)
    if visualize and all(x['integrity_ok'] for x in result['receivers'].values()):
        subprocess.run([str(ROOT/'.venv/bin/python'),'-B',str(ROOT/'tools/build_offline_bundle.py'),
                        '--capture-dir',str(run/'capture'),'--manifest',str(run/'capture-manifest.json'),
                        '--output',str(output/'visualization')],check=True)
    return 0 if result['quality_ok'] else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--output-new',type=Path,required=True)
    p.add_argument('--no-visualization',action='store_true');a=p.parse_args()
    raise SystemExit(analyze(a.run,a.output_new,not a.no_visualization))
