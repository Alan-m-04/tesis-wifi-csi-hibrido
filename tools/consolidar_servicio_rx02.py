#!/usr/bin/env python3
"""Read-only laboratory consolidation; never acquires or approves physical data."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from presence_rx02_journal import audit_rx02
from rx02_checkpoint_journal import audit_checkpoint_rx02
from presence_v4_journal import digest,write_new
from rx02_gap_diagnostics import adjacent_gaps


def load(p):return json.loads(p.read_text())


def reference(p):return dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=digest(p))


def case(path):
    report=load(path/'laboratory.json');bundle=path/'bundle'
    if report.get('instrumentation_revision')!='bounded-function-hooks-2':
        raise ValueError('Only bounded final instrumentation is comparable')
    audit=(audit_checkpoint_rx02 if report['variant']=='checkpoint2' else audit_rx02)(bundle)
    operations=[json.loads(line) for line in (bundle/'operations.jsonl').read_text().splitlines()]
    reads=[o for o in operations if o['op']=='chunk']
    events=load(bundle/'events.json')
    rows=[e for e in events if e['kind']=='line' and e['evidence']['kind']=='row']
    gaps=adjacent_gaps(rows)
    starts=[b['data']['started_ns']-a['data']['returned_ns'] for a,b in zip(reads,reads[1:])]
    late=[]
    for w in audit['state']['windows']:
        late.extend(dict(slot=w['id'],event=e,return_minus_T1_ns=int(e['evidence']['returned_ns'])-w['T1_ns'],
                         processing_sample_minus_T1_ns=e['now_ns']-w['T1_ns']) for e in rows
                    if int(e['evidence']['first_read_started_ns'])>=w['T0_ns'] and
                    int(e['evidence']['returned_ns'])<w['T1_ns']<=e['now_ns'])
    return dict(laboratory=report,laboratory_file=reference(path/'laboratory.json'),
        bundle_manifest=reference(bundle/'manifest.json'),
        bundle_files={e['path']:dict(bytes=e['bytes'],sha256=e['sha256']) for e in load(bundle/'manifest.json')['files']},
        operations=len(operations),complete_rows=len(rows),max_host_complete_row_gap_ns=max((g['host_gap_ns'] for g in gaps),default=None),
        max_local_complete_row_gap_us=max((g['local_gap_us'] for g in gaps),default=None),
        max_previous_return_to_next_read_start_ns=max(starts,default=None),
        observed_service_rss_kib=dict(min=min(r['rss_kib'] for r in report['resources']),
                                      max=max(r['rss_kib'] for r in report['resources'])),
        observed_fds=sorted({r['fds'] for r in report['resources']}),observed_threads=sorted({r['threads'] for r in report['resources']}),
        late_rows=late,final_eligibility=audit['exploratory_eligibility'],original_tails=audit['state']['tails'],
        selected_close_confirmed=audit['state']['closed']['RX-02']['confirmed'],
        meter_has_overflow=bool(report['timings']['overflow']) or bool(report['producer_timing']['overflow']))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lab',type=Path,default=ROOT/'results/local/laboratorio-servicio-rx02-r1')
    p.add_argument('--output-new',type=Path,required=True)
    a=p.parse_args();lab=a.lab
    originals=load(lab/'originales-antes.json')
    for name,e in originals.items():
        if (ROOT/name).stat().st_size!=e['bytes'] or digest(ROOT/name)!=e['sha256']:raise ValueError('Original changed: '+name)
    cases={folder.name:case(folder) for folder in sorted(lab.glob('v2-*')) if folder.is_dir()}
    cases['sostenido-v2-nominal']=case(lab/'sostenido-v2-nominal')
    if any(c['meter_has_overflow'] for c in cases.values()):raise ValueError('Measurement buffer overflow')
    if any(c['laboratory']['errors'] or c['laboratory']['producer_error'] for c in cases.values()):
        raise ValueError('Invalid final experiment')
    physical={}
    for name in ('C01','C02'):
        b=ROOT/'results/local'/('piloto-rx02-r1-'+name);audit=audit_rx02(b)
        physical[name]=dict(integrity_ok=audit['integrity_ok'],replay_ok=audit['replay_ok'],
            fatal=audit['state']['fatal'],connection=audit['state']['connection'],
            eligibility=audit['exploratory_eligibility'],closed=audit['state']['closed'],
            authorization_consumed=load(b/'authorization-consumed.json'))
    exploratory={}
    for path in sorted(lab.glob('*/laboratory.json')):
        report=load(path)
        if report.get('instrumentation_revision')!='bounded-function-hooks-2':
            exploratory[path.parent.name]=dict(file=reference(path),fatal=report['fatal'],
                actual_elapsed_s=report['actual_elapsed_s'],
                excluded_reason='Preliminary call-retaining mocks; not used for bounded resource/performance claims')
    sources=['src/rx02_checkpoint_journal.py','src/rx02_service_lab.py','tools/reproducir_servicio_rx02.py',
        'tools/medir_crecimiento_rx02.py','tools/consolidar_servicio_rx02.py','tests/test_rx02_checkpoint.py']
    report=dict(schema='rx02-service-comparison-2',base_commit='6403274b8422ddd764397370a1a2741090254c12',
        final_cases=cases,preliminary_retained_cases=exploratory,
        growth_probe=load(lab/'crecimiento.json'),growth_probe_file=reference(lab/'crecimiento.json'),
        regression=load(lab/'pruebas-regresion.json'),regression_log=reference(lab/'pruebas-regresion.stderr.txt'),
        namespace_attempt=dict(exit_code=1,tests_executed=False,log=reference(lab/'pruebas-bwrap.stderr.txt')),
        protected_original_files=originals,original_files_unchanged=len(originals),original_outcomes=physical,
        final_source_snapshots=load(lab/'fuentes-ensayos/manifest.json'),sources={name:reference(ROOT/name) for name in sources},
        guarantees=dict(physical_UART_opened=False,physical_acquisition_prepared=False,thresholds_changed=False,
                        labels_or_history_reclassified=False,calibration=False,training=False,firmware_changed=False),
        limits=['Synthetic measured-size envelope and 5 Hz cadence, not physical radio/USB evidence',
            'Injected stage delays demonstrate mechanisms, not the unique cause of C02',
            'First stress long run rejected at coverage and is retained; nominal E still ineligible for late processing',
            'Raw fsync, locks, writes and scheduling remain synchronous; no hard OS deadline',
            'Resource samples at about 1 Hz; post-close audit peak RSS is separate from active service',
            'Operations durability changed explicitly to bounded-byte checkpoints; incomplete bundles never approved'])
    write_new(a.output_new,report)
    print(json.dumps(dict(output=str(a.output_new),cases=len(cases),preserved=len(originals),
        tests=report['regression']['tests'],physical_UART_opened=False),indent=2))


if __name__=='__main__':main()
