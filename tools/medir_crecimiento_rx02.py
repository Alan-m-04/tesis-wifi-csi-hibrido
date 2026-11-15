#!/usr/bin/env python3
"""CPU-only synthetic growth probe; no transport, physical data or timing claim."""
import argparse
import json
from pathlib import Path
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from presence_rx02 import Rx02Presence
from presence_v4_journal import write_new
from rx02_service_lab import synthetic_row,SIZES


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-new',type=Path,required=True)
    args=parser.parse_args()
    plan=json.loads((ROOT/'config/piloto_rx02_r1_C01.review.json').read_text())
    m=Rx02Presence(plan);m.apply('begin',0);m.apply('opened',1,receiver='RX-02')
    boot=(b'I (537) wifi:ic_enable_sniffer\r\n'
          b'I (10) csi_recv_02: RX-02 READY channel=11 HT20 UART0=115200 raw CSI; source=1a:00:00:00:00:00\n'
          b'I (545) main_task: Returned from app_main()\r\n')
    m.apply('chunk',2,receiver='RX-02',chunk=boot,started_ns=1,returned_ns=2)
    points=[]
    for ident in range(18000):
        now=(ident+1)*200_000_000
        m.apply('chunk',now,receiver='RX-02',chunk=synthetic_row(ident,SIZES[ident%4]),started_ns=now,returned_ns=now)
        m.apply('tick',now+1)
        for cue in m.signals:
            if cue['ack_ns'] is None:m.apply('cue_ack',m.now,signal_id=cue['id'],success=True)
        if m.initial_available is not None and not m.windows:
            m.apply('request',m.now,slot_id='RX02-C01-E',last=False)
        if ident+1 in (500,5000,18000):
            tick=[];summaries=[];serial=[]
            for _ in range(10):
                start=time.perf_counter_ns()
                for _ in range(100):m.apply('tick',m.now)
                tick.append((time.perf_counter_ns()-start)/100)
                start=time.perf_counter_ns();m.summary();summaries.append(time.perf_counter_ns()-start)
                record=dict(seq=ident,op='tick',now_ns=m.now,data={})
                start=time.perf_counter_ns()
                for _ in range(100):json.dumps(record,ensure_ascii=False,allow_nan=False)
                serial.append((time.perf_counter_ns()-start)/100)
            points.append(dict(rows=ident+1,events=len(m.events),fatal=m.fatal,
                median_tick_cpu_ns=statistics.median(tick),median_full_summary_cpu_ns=statistics.median(summaries),
                median_fixed_record_json_cpu_ns=statistics.median(serial)))
    write_new(args.output_new,dict(evidence_type='synthetic_CPU_growth_probe_not_physical_or_realtime',
        points=points,policy_changed=False,summary_hot_path='Only window completion and finalization, not every read/tick',
        observed_records_not_used_for_fixture_generation=True))
    print(json.dumps(points,indent=2))


if __name__=='__main__':main()
