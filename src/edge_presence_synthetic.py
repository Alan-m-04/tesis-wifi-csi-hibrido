"""Deterministic invented I/Q for software QA, never a physical acquisition."""
import csv
import hashlib
import io
import json
from pathlib import Path

from capture_csi_multi import FIELDS, SOURCE
from edge_presence_evaluation import SCHEMA
from presence_offline import ACTIVE, INDICES

PROFILE = dict(lltf_en=True, htltf_en=True, stbc_htltf2_en=True, ltf_merge_en=True,
               channel_filter_en=True, manu_scale=False)
SCOPE = 'synthetic-room-RX02-v1'


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def write_dataset(output):
    """Two train and three evaluation connections; includes FP/FN/abstention cases."""
    from consolidar_rx02_c01 import coverage_from_refs
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    cases = [
        ('TRAIN-01', 'train', [10], [20, 22, 24], False),
        ('TRAIN-02', 'train', [9, 10, 11], [21, 23, 25], False),
        ('EVAL-01', 'evaluation', [9, 10, 11], [22, 24, 26], False),
        ('EVAL-02', 'evaluation', [20, 22, 24], [10], False),
        ('EVAL-03', 'evaluation', [10], [22, 24, 26], True),
    ]
    sessions = []
    for suffix, split, empty, occupied, invalid in cases:
        sid = 'SYNTHETIC-' + suffix
        bundle = output / sid; bundle.mkdir()
        raw, windows = bytearray(), []
        for condition, values in (('E', empty), ('S', occupied)):
            t0 = 10_000_000_000 if condition == 'E' else 50_000_000_000
            refs = []
            for i in range(150):
                ident = i + (150 if condition == 'S' else 0)
                value = values[i % len(values)]
                iq = [x for k in INDICES for x in ([0, value] if k in ACTIVE else [-128, 127])]
                iq += [99, -99] * 64  # HT-LTF is deliberately different, excluded from LLTF52.
                fields = dict.fromkeys(FIELDS, '0')
                fields.update(type='CSI_DATA', id=str(ident), mac=SOURCE, channel='11', rssi='-50',
                    sig_mode='1', len='256', first_word_invalid=str(int(invalid and i == 0)),
                    local_timestamp=str(ident * 200000), data='[' + ','.join(map(str, iq)) + ']')
                stream = io.StringIO()
                csv.writer(stream, lineterminator='\n').writerow([fields[k] for k in FIELDS])
                line = stream.getvalue().encode(); start = len(raw); raw.extend(line)
                when = t0 + 100_000_000 + i * 200_000_000
                refs.append(dict(kind='row', problem=False, id=ident, local_timestamp=ident * 200000,
                    queue_drops=0, line_1based=ident + 1, byte_offset=start, byte_end=len(raw),
                    byte_length=len(line), line_sha256=hashlib.sha256(line).hexdigest(),
                    first_read_started_ns=str(when - 1), returned_ns=str(when), inclusion='included'))
            windows.append(dict(id=sid + '-' + condition, condition=condition, T0_ns=t0,
                T1_ns=t0 + 30_000_000_000, label=dict(status='declared', observation_method='synthetic_fixture'),
                label_quality_ok=True, receivers={'RX-02': dict(included_line_references=refs,
                    coverage=coverage_from_refs(refs, t0, t0 + 30_000_000_000))}))
        audit = dict(native_audit_executed=False, integrity_ok=True, replay_ok=True,
            state=dict(evidence_type='synthetic_fixture', protocol='presence_rx02_persistent_1',
                connection_id=sid, partition_group=sid, scope=SCOPE, windows=windows,
                connection=dict(quality_ok=False, reasons=['synthetic_history_rejection'])),
            exploratory_eligibility=dict(windows=[dict(slot_id=w['id'], eligible=True) for w in windows]))
        (bundle / 'rx-02.serial.log').write_bytes(raw)
        write_json(bundle / 'audit-fixture.json', audit)
        write_json(bundle / 'sources.json', dict(firmware_ltf_config=PROFILE,
            raw=dict(path='rx-02.serial.log', sha256=hashlib.sha256(raw).hexdigest()),
            audit=dict(path='audit-fixture.json', sha256=hashlib.sha256((bundle / 'audit-fixture.json').read_bytes()).hexdigest())))
        sessions.append(dict(id=sid, partition_group=sid, split=split, bundle=sid))
    manifest = output / 'sessions.json'
    write_json(manifest, dict(schema=SCHEMA, evidence_type='synthetic_fixture', receiver='RX-02',
        scope=SCOPE, not_physical_measurements=True, sessions=sessions))
    return manifest
