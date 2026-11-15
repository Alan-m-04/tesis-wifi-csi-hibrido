"""Read-only validation of ONE recorded session; never fits or queries a model."""
import hashlib
import json
from pathlib import Path

from edge_presence_evaluation import load_json, safe_path
from eligible_presence_features import extract_eligible_window

ROOT = Path(__file__).resolve().parents[1]


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def inventory(bundle):
    """Do not follow aliases or open reserved inputs hidden inside a bundle."""
    import os
    result = {}
    for folder, dirs, files in os.walk(bundle, followlinks=False):
        for name in dirs + files:
            path = safe_path(Path(folder) / name)
            if (Path(folder) / name).is_symlink() or not path.is_relative_to(bundle):
                raise ValueError('symlink_or_external_input:' + name)
        for name in files:
            path = Path(folder) / name
            result[str(path.relative_to(bundle))] = fingerprint(path)
    return result


def native_audit(bundle):
    provenance = load_json(bundle / 'provenance.json')
    revision = provenance.get('integration_revision')
    if revision == 'rx02-devrep-r5-n01-entry-1':
        from rx02_devrep_r5_n01.session import audit_devrep
        return audit_devrep(bundle)
    if revision == 'rx02-c03-checkpoint-entry-1':
        from rx02_c03.checkpoint import audit_c03_checkpoints
        return audit_c03_checkpoints(bundle)
    if revision is None and provenance.get('persistence_revision') is None:
        from presence_rx02_journal import audit_rx02
        return audit_rx02(bundle)
    raise ValueError('unsupported_native_revision:' + str(revision))


def prevalidate(bundle, *, synthetic_fixture=False):
    report = dict(schema='tesis-edge-session-prevalidation-1', accepted=False,
        processing_ready=False, native_audit_executed=False, evidence_type=None,
        integrity_ok=False, replay_ok=False, labels_ok=False, eligibility_ok=False,
        strict_quality_ok=False, close_ok=False, features_ok=False, windows=[],
        rejection_reasons=[], model_training_executed=False, inference_executed=False,
        model_evaluation_ready=False, model_evaluation_reason='requires_multiple_independent_whole_sessions_and_reviewed_use_contract',
        physical_UART_opened=False, reserve_opened=False, sources_unchanged=None)
    stage = 'input'
    before = None
    def reject(code, detail=None):
        item = dict(code=code, detail=detail)
        if item not in report['rejection_reasons']:
            report['rejection_reasons'].append(item)
    try:
        bundle = safe_path(bundle)
        if not bundle.is_dir():
            raise ValueError('bundle_directory_missing:' + str(bundle))
        # Reject a sealed session even if its directory was renamed, before raw inventory.
        if (bundle / 'plan.json').is_file():
            plan = load_json(bundle / 'plan.json')
            for key in ('connection_id', 'partition_group'):
                if key in plan: safe_path(plan[key])
            if plan.get('future_partition') == 'evaluation_future_sealed':
                raise ValueError('sealed_evaluation_partition')
        before = inventory(bundle)
        report['input_file_count'] = len(before)
        report['input_inventory_sha256'] = hashlib.sha256(
            json.dumps(before, sort_keys=True).encode()).hexdigest()
        stage = 'native_audit'
        if synthetic_fixture:
            from edge_presence_evaluation import read_synthetic
            audit, traces, _ = read_synthetic(bundle)
            report['audit_kind'] = 'synthetic_decision_fixture_not_native_audit'
        else:
            audit = native_audit(bundle)
            report.update(native_audit_executed=True, audit_kind='native_integrity_replay_receipt_and_eligibility')
            traces = None
        state = audit['state']
        report.update(evidence_type=state['evidence_type'], session_id=state['connection_id'],
                      partition_group=state['partition_group'], connection_full=state['connection'],
                      integrity_ok=audit.get('integrity_ok') is True, replay_ok=audit.get('replay_ok') is True)
        if not report['integrity_ok']: reject('integrity_failed')
        if not report['replay_ok']: reject('replay_failed')
        report['strict_quality_ok'] = state['connection'].get('quality_ok') is True
        if not report['strict_quality_ok']:
            reject('strict_connection_rejected', state['connection'].get('reasons', []))
        if state.get('fatal'): reject('connection_fatal', state['fatal'])
        closed = state.get('closed', {})
        report['close_ok'] = (set(closed) == {'RX-02'} and all(
            c.get('confirmed') is True and c.get('reader_stopped') is True and not c.get('error')
            for c in closed.values()))
        if not report['close_ok']: reject('close_not_confirmed', closed)
        if state.get('future_partition') == 'evaluation_future_sealed': reject('sealed_evaluation_partition')
        if audit.get('series_can_continue') is False: reject('native_administrative_schedule_failed')
        stage = 'labels_and_eligibility'
        windows = state['windows']
        if len(windows) != 2 or {w.get('condition') for w in windows} != {'E', 'S'}:
            reject('complete_E_S_connection_required')
        eligibility = audit.get('exploratory_eligibility', {})
        gates = {w['slot_id']: w for w in eligibility.get('windows', [])}
        if not synthetic_fixture:
            if eligibility.get('identity_ok') is not True: reject('native_identity_not_verified')
            if eligibility.get('storage_ok') is not True: reject('native_storage_not_verified')
        report['original_permitted_uses'] = eligibility.get('permitted_uses', {})
        # Processing-only prevalidation does not require or grant model-use permission.
        raw = None
        membership = set()
        from consolidar_rx02_c01 import frame_from_reference, coverage_from_refs
        profile = load_json(ROOT / 'config/csi_esp32s3.json')['firmware_ltf_config']
        for window in windows:
            slot = window['id']
            item = dict(slot_id=slot, condition=window['condition'], label=window['label'],
                label_ok=window['label'].get('status') == 'declared' and window.get('label_quality_ok') is True,
                native_eligible=window.get('eligible') is True,
                exploratory_eligible=gates.get(slot, {}).get('eligible') is True,
                eligibility_reasons=gates.get(slot, {}).get('reasons', []), features=None)
            report['windows'].append(item)
            if not item['label_ok']: reject('label_not_declared_or_not_conforming', dict(slot_id=slot, label=window['label']))
            if not item['exploratory_eligible']: reject('window_ineligible', dict(slot_id=slot, reasons=item['eligibility_reasons']))
            if not item['native_eligible']: reject('strict_window_ineligible', slot)
            stage = 'features:' + slot
            refs = window['receivers']['RX-02']['included_line_references']
            keys = [r['line_1based'] for r in refs]
            if len(set(keys)) != len(keys) or membership.intersection(keys):
                raise ValueError('duplicate_or_shared_original_row_reference:' + slot)
            membership.update(keys)
            coverage = coverage_from_refs(refs, window['T0_ns'], window['T1_ns'])
            original = window['receivers']['RX-02']['coverage']
            if any(original[k] != coverage[k] for k in ('included_rows', 'bins_5s', 'gaps_ns', 'max_gap_ns')):
                raise ValueError('original_coverage_differs:' + slot)
            if traces is None:
                if raw is None: raw = (bundle / 'rx-02.serial.log').read_bytes()
                frames = [frame_from_reference(raw, ref, profile)[0] for ref in refs]
            else:
                frames = traces[slot]
            result = extract_eligible_window(audit, slot, frames)
            item.update(feature_status=result['feature_status'], features=result['features'],
                        feature_reasons=result['reasons'], input_rows=len(refs))
            if result['features'] is None: reject('features_not_evaluable', dict(slot_id=slot, reasons=result['reasons']))
        report['labels_ok'] = len(windows) == 2 and all(w['label_ok'] for w in report['windows'])
        report['eligibility_ok'] = len(windows) == 2 and all(
            w['native_eligible'] and w['exploratory_eligible'] for w in report['windows'])
        report['features_ok'] = len(windows) == 2 and all(w['features'] is not None for w in report['windows'])
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
        reject(stage + '_failed', str(exc))
    finally:
        if before is not None:
            try:
                report['sources_unchanged'] = inventory(bundle) == before
                if not report['sources_unchanged']: reject('sources_changed_during_prevalidation')
            except (OSError, ValueError) as exc:
                report['sources_unchanged'] = False
                reject('source_recheck_failed', str(exc))
    report['processing_ready'] = not report['rejection_reasons']
    report['accepted'] = report['processing_ready']
    return report
