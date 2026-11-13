#!/usr/bin/env python3
"""Consolidate only existing A1/B/A2; plots use the already pinned local runtime."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from antenna_aba_analysis import build_series,add_transport_samples,render_plots,PHASES
from presence_v4_journal import digest,write_new


def consolidate(bundles_root,preparation):
    bundles={p:Path(bundles_root)/('continuidad-antena-aba-r3-'+p) for p in PHASES}
    summary,data=build_series(bundles)
    preparation=Path(preparation)
    names=['autorizacion-serie.json','confirmacion-croquis-A1-B-r1.json',
        'confirmacion-posicion-B-r1.json','confirmacion-retorno-A1-para-A2-r1.json',
        'confirmacion-suspension-A1-r1.json','confirmacion-fuser-A1-r1.json',
        'confirmacion-alimentacion-TX-A1-r1.json','croquis-A1-B-provisional-r1.md']
    names += ['preparacion-'+p+'-validada-r1.json' for p in PHASES]
    names += ['preflight-reportado-y-comando-'+p+'-r1.json' for p in PHASES]
    authorization=json.loads((preparation/'autorizacion-serie.json').read_text())
    if not authorization['authorization_granted'] or len(authorization['per_attempt'])!=3:
        raise ValueError('Original three-attempt authorization required')
    if not json.loads((preparation/'confirmacion-posicion-B-r1.json').read_text())['fixed_parts_intact_by_operator']:
        raise ValueError('B fixed-parts declaration missing')
    if not json.loads((preparation/'confirmacion-retorno-A1-para-A2-r1.json').read_text())['antenna_returned_to_A1_by_operator']:
        raise ValueError('A2 return declaration missing')
    for phase in PHASES:
        proof=json.loads((preparation/('preparacion-'+phase+'-validada-r1.json')).read_text())
        if digest(bundles[phase]/'plan.json')!=proof['plan_sha256']:
            raise ValueError('Prepared/captured plan hash differs: '+phase)
        mount=ROOT/proof['mount_snapshot']
        if digest(mount)!=proof['mount_snapshot_sha256']:
            raise ValueError('Mount reference altered: '+phase)
        names.append(mount.name)
    summary['preparation_evidence']={name:dict(bytes=(preparation/name).stat().st_size,
        sha256=digest(preparation/name)) for name in names}
    mount=json.loads((ROOT/json.loads((preparation/'preparacion-A1-validada-r1.json').read_text())['mount_snapshot']).read_text())
    photos={v['photo']:v['photo_sha256'] for v in mount['identity_reference'].values()}
    photos[mount['A1']['general_photo']['path']]=mount['A1']['general_photo']['sha256']
    if any(digest(Path(p))!=sha for p,sha in photos.items()):raise ValueError('Reference photograph changed')
    summary['photo_reference_sha256']=photos
    summary['geometry_evidence_scope']='Operator declarations, unchanged photographs and confirmed relative sketch; no angular metrology or B/A2 photo measurement'
    summary['acquisition_preflight_evidence']='Operator reported completion; no stdout/exit code archived. Acquisition runtime rechecked identities before/after opening.'
    summary['sources']={p:digest(ROOT/p) for p in ('src/antenna_aba_analysis.py','tools/comparar_antena_aba.py',
        'src/continuity_diagnostics.py','requirements-comparacion.txt')}
    add_transport_samples(bundles,summary,data)
    return summary,data


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundles-root',type=Path,default=ROOT/'results/local')
    parser.add_argument('--preparation',type=Path,default=ROOT/'results/local/preparacion-antena-aba-r3')
    parser.add_argument('--output-new',type=Path,required=True)
    args=parser.parse_args(argv)
    output=args.output_new.resolve()
    if output.exists():parser.error('New exclusive output required')
    for phase in PHASES:
        bundle=(args.bundles_root/('continuidad-antena-aba-r3-'+phase)).resolve()
        if output.is_relative_to(bundle):parser.error('Output must be outside all original bundles')
    summary,data=consolidate(args.bundles_root,args.preparation)
    output.mkdir(parents=True,exist_ok=False)
    write_new(output/'comparison.json',summary)
    write_new(output/'observations.json',data)
    manifest=render_plots(summary,data,output/'figures')
    manifest['summary_sha256']=digest(output/'comparison.json')
    manifest['observations_sha256']=digest(output/'observations.json')
    write_new(output/'figures.json',manifest)
    print(output)
    return 0


if __name__=='__main__':raise SystemExit(main())
