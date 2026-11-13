"""Optional real-time 60 s test. Only owned PTYs; never forwards a UART path."""
import argparse
import json
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tests'), str(ROOT/'tools')]
import dual_continuity as dc
from test_uart_v4 import Rig
from campana_presencia_v4 import fixture_row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-new', type=Path, required=True)
    args = parser.parse_args()
    rig = Rig()
    session = None
    try:
        plan = json.loads((ROOT/'config/continuidad_dual_60s_r1.review.json').read_text())
        session = dc.ContinuitySession(args.output_new, plan, test_backend=rig.backend)
        origin = time.monotonic()

        def produce():
            tick = 0; pending = None
            try:
                while not session.stop.is_set():
                    elapsed = time.monotonic()-origin
                    for rx, pair in rig.pairs.items():
                        if rx == 'RX-01' and 5 <= elapsed < 7: continue
                        if rx == 'RX-02' and 20 <= elapsed < 22:
                            if pending is None:
                                line = fixture_row(tick, 100000+tick*200000)
                                pair.fixture_write(line[:100]); pending = line[100:]
                            continue
                        if rx == 'RX-02' and pending:
                            pair.fixture_write(pending); pending = None
                        pair.fixture_write(fixture_row(tick, 100000+tick*200000))
                    if elapsed > 59.5:
                        for pair in rig.pairs.values(): pair.fixture_write(b'CSI_DATA,synthetic-tail')
                        break
                    tick += 1
                    session.stop.wait(.2)
            except BaseException as exc:
                session._fail(exc)

        producer = threading.Thread(target=produce)
        producer.start()
        result = session.run(); producer.join()
        r = result['report']
        assert result['integrity_ok'] and result['replay_ok']
        assert r['completed_nominal_duration'] and r['both_ports_closed_confirmed']
        assert not r['quality_approval'] and not any(r['permitted_uses'].values())
        for state in r['receivers'].values():
            assert state['tail']['byte_length'] == len(b'CSI_DATA,synthetic-tail')
            assert any(x['recovered_ns'] is not None for x in state['incidents'])
        print(json.dumps(dict(evidence_type='synthetic_fixture', physical_UART_opened=False,
            integrity_ok=True, replay_ok=True, both_ports_closed_confirmed=True,
            quality_approval=False, actual_elapsed_ns=r['dual_observation']['actual_elapsed_ns']), indent=2))
    finally:
        if session is not None: session.finish()
        rig.finish_fixture()


if __name__ == '__main__': main()
