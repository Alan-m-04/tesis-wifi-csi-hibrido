"""At most four fixed predecessors; no chaining, reopening or automatic recovery."""
import json
from pathlib import Path
import time
from controlled_capture import ROOT
from presence_v4_journal import digest
from rx02_devrep.contract import CONNECTIONS,SCHEDULE,setup_fingerprint


def boot_id():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def validate_setup_snapshot(plan):
    path=(ROOT/plan['setup_snapshot_path']).resolve()
    if not path.is_relative_to(ROOT/'results/local') or digest(path)!=plan['setup_snapshot_sha256']:
        raise ValueError('Uniform setup snapshot missing/changed; no opening')


def predecessor_context(plan):
    ordinal=CONNECTIONS[plan['connection_id']]['ordinal']
    if ordinal==1:return None
    previous_id=f'RX02-DEVREP-R1-D{ordinal-1:02d}'
    root=ROOT/CONNECTIONS[previous_id]['output_new']
    from rx02_devrep.session import audit_devrep
    report=audit_devrep(root)
    if report['state']['connection_id']!=previous_id or not report['series_can_continue']:
        raise ValueError('Previous connection failed/incomplete; series is stopped')
    if report['state'].get('evidence_type')!='physical_capture':
        raise ValueError('Synthetic predecessor cannot authorize a physical series opening')
    prior=json.loads((root/'plan.json').read_text())
    provenance=json.loads((root/'provenance.json').read_text())
    if setup_fingerprint(prior)!=setup_fingerprint(plan):
        raise ValueError('Setup changed; series is stopped')
    return dict(previous_id=previous_id,previous_manifest_sha256=digest(root/'manifest.json'),
        previous_close_ns=report['state']['closed']['RX-02']['at_ns'],
        host_boot_id=provenance['transport']['host_boot_id'])


def wait_for_open_target(context,clock=time.monotonic_ns):
    if context is None:return
    target=context['previous_close_ns']+SCHEDULE['inter_connection_gap_ns']
    while True:
        now=clock()
        if now>target+SCHEDULE['inter_connection_lateness_ns']:
            raise ValueError('Opening interval expired; no late opening')
        if now>=target:return
        time.sleep(min(.05,(target-now)/1e9))


def verify_recorded_predecessor(root,report):
    plan=json.loads((root/'plan.json').read_text())
    transport=json.loads((root/'provenance.json').read_text())['transport']
    expected=predecessor_context(plan)
    if transport.get('series_context')!=expected:
        raise ValueError('Predecessor audit/manifest/close binding differs')
    if expected is not None and transport.get('host_boot_id')!=expected['host_boot_id']:
        raise ValueError('Host boot differs; inter-connection monotonic times invalid')
    reference=transport.get('authorization_reference')
    if reference!=plan['connection_id']+':'+digest(root/'plan.json') or plan.get('authorization_granted') is not True:
        raise ValueError('DEVREP physical grant/reference not bound to captured plan')
