#!/usr/bin/env python3
"""Finite synthetic owned-PTY load comparison; no physical input or server."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import resource
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from csi_live_observer import (MAX_SNAPSHOT,Observer,SharedFlag,atomic_json,boot_id,current_snapshot,
                               guard,small_json)
from rx02_service_lab import MAX_DURATION_S,Meter,run_case

MAX_RESOURCE_SAMPLES=128

SCENARIOS={
    'baseline':dict(observer=False,consumer_interval_s=None,max_rows=None),
    'normal':dict(observer=True,consumer_interval_s=.25,max_rows=300),
    'slow':dict(observer=True,consumer_interval_s=2.5,max_rows=8),
}


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def manifest(bundle):
    # This function is used only for this invocation's newly-created bundle.
    return {p.name:dict(bytes=p.stat().st_size,sha256=digest(p))
            for p in sorted(Path(bundle).iterdir()) if p.is_file()}


def resources():
    status=dict(line.split(':',1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    io=dict(line.split(':',1) for line in Path('/proc/self/io').read_text().splitlines())
    return dict(rss_kib=int(status['VmRSS'].split()[0]),cpu_ns=time.process_time_ns(),
                wall_ns=time.monotonic_ns(),fds=len(list(Path('/proc/self/fd').iterdir())),
                io={key:int(io[key]) for key in ('rchar','wchar','read_bytes','write_bytes')})


def sampled_cpu_percent(samples):
    """Percent of one CPU over sampled interval, excluding subsequent audit."""
    if len(samples)<2:return None
    first,last=samples[0],samples[-1]
    wall=(last['wall_ns']-first['wall_ns']) if 'wall_ns' in first else int((last['elapsed_s']-first['elapsed_s'])*1e9)
    return 100*(last['cpu_ns']-first['cpu_ns'])/wall if wall>0 else None


def native_worker(path,duration):
    sys.addaudithook(guard)
    report=run_case(path,variant='checkpoint2',mechanism='none',delay_ms=0,
                    duration=duration,windows=False,poll_ms=5)
    if report['errors'] or report['fatal'] or not report['integrity_ok'] or not report['replay_ok']:
        raise SystemExit(1)


def clock_proof(bundle):
    # run_case above explicitly injects time.monotonic_ns into its synthetic
    # backend. This attestation is external, never added to native provenance.
    return dict(schema='synthetic-PTY-clock-binding-1',bundle=str(bundle.resolve()),
                clock_domain='host_monotonic_ns',host_boot_id=boot_id(),
                plan_sha256=digest(bundle/'plan.json'),provenance_sha256=digest(bundle/'provenance.json'))


def observer_worker(bundle,view,proof,stop,max_rows,resource_period_s):
    sys.addaudithook(guard)
    view.mkdir(exist_ok=False)
    o=Observer(bundle,clock_binding=proof,max_rows=max_rows)
    meter=Meter();samples=[];states=[];errors=[];last_byte=0
    max_backlog=max_snapshot=max_retained=0;cpu_start=time.process_time_ns();start=time.monotonic_ns()
    next_resource=0;next_poll=time.monotonic()
    try:
        while True:
            begin=time.monotonic_ns();o.poll();decoded=time.monotonic_ns()
            meter.add('poll_ns',decoded-begin)
            new=[r for r in o.rows if r['reference']['byte_end']>last_byte]
            for row in new:
                meter.add('source_return_to_decode_ns',decoded-int(row['t_ns']))
                meter.add('first_read_to_decode_ns',decoded-int(row['first_read_ns']))
            if new:last_byte=new[-1]['reference']['byte_end']
            if stop.is_set():o.stop('Fin de medición del observador; no ordena detener la fuente')
            snapshot=o.snapshot();publish_start=time.monotonic_ns()
            atomic_json(view/'latest.json',snapshot);published=time.monotonic_ns()
            meter.add('publication_ns',published-publish_start)
            for row in new:meter.add('source_return_to_publication_ns',published-int(row['t_ns']))
            max_snapshot=max(max_snapshot,(view/'latest.json').stat().st_size)
            max_backlog=max(max_backlog,snapshot['backlog_bytes'])
            max_retained=max(max_retained,len(snapshot['rows']))
            if snapshot['flow_state'] not in states:states.append(snapshot['flow_state'])
            if published>=next_resource and len(samples)<MAX_RESOURCE_SAMPLES:
                samples.append(resources())
                next_resource=published+int(resource_period_s*1e9)
            if o.error:errors.append(o.error);break
            if stop.is_set():break
            next_poll+=.25
            # Skip missed display polls; never accumulate a queue of callbacks.
            next_poll=max(next_poll,time.monotonic())
            stop.wait(max(0,next_poll-time.monotonic()))
    except BaseException as exc:
        errors.append(type(exc).__name__+': '+str(exc))
    finally:
        final=o.snapshot();o.close()
        atomic_json(view/'observer-report.json',dict(schema='observer-PTY-meter-1',
            timings=meter.summary(),resources=samples,states=states,errors=errors,
            sampled_cpu_percent_one_core=sampled_cpu_percent(samples),
            cpu_ns=time.process_time_ns()-cpu_start,wall_ns=time.monotonic_ns()-start,
            peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            max_snapshot_bytes=max_snapshot,max_backlog_bytes=max_backlog,max_rows_retained=max_retained,
            raw_bytes_read=o.raw_offset,
            final=final))
    if errors:raise SystemExit(1)


def measure_case(root,scenario,duration):
    config=SCENARIOS[scenario];ctx=mp.get_context('spawn')
    source=ctx.Process(target=native_worker,args=(root,duration),name='native-owned-PTY')
    observer=None;stop=SharedFlag(ctx);meter=Meter();cpu_start=time.process_time_ns()
    source.start()
    started=time.monotonic()
    deadline=started+duration+(90 if duration>120 else 20)
    resource_period_s=10 if duration>120 else 1
    next_resource=started
    next_progress=started+60
    consumer_resources=[]
    last_byte=last_revision=unique=revision_gaps=0;states=[];read_errors=[];reads=0
    next_consume=0;terminal_consumed=False
    try:
        if config['observer']:
            while time.monotonic()<deadline:
                try:
                    proof=clock_proof(root/'bundle')
                    small_json(root/'bundle'/'provenance.json',131072)
                    if not (root/'bundle'/'operations.jsonl').exists():raise FileNotFoundError()
                    break
                except (OSError,ValueError):
                    if not source.is_alive():raise RuntimeError('Native source ended before its metadata was available')
                    time.sleep(.01)
            else:raise TimeoutError('Native metadata deadline')
            atomic_json(root/'synthetic-clock-binding.json',proof)
            observer=ctx.Process(target=observer_worker,
                args=(root/'bundle',root/'view',proof,stop,config['max_rows'],resource_period_s),name='read-only-observer')
            observer.start()
        while time.monotonic()<deadline:
            now=time.monotonic();source_alive=source.is_alive()
            if config['observer'] and now>=next_resource and len(consumer_resources)<MAX_RESOURCE_SAMPLES:
                consumer_resources.append(resources())
                next_resource=now+resource_period_s
            if now>=next_progress:
                print(json.dumps(dict(case=root.name,elapsed_s=round(now-started),source_alive=source_alive,
                    consumer_unique_rows=unique,consumer_reads=reads)),flush=True)
                next_progress=now+60
            if config['observer'] and now>=next_consume:
                try:
                    begin=time.monotonic_ns();s=current_snapshot(root/'view'/'latest.json')
                    # Exercise the same JSON serialization as the local API;
                    # no TCP/network/render latency is asserted by this test.
                    json.dumps(s,ensure_ascii=False,allow_nan=False).encode()
                    received=time.monotonic_ns();meter.add('snapshot_read_serialize_ns',received-begin);reads+=1
                    if s['revision']>last_revision:
                        if last_revision:revision_gaps+=max(0,s['revision']-last_revision-1)
                        last_revision=s['revision']
                    for row in s['rows']:
                        end=row['reference']['byte_end']
                        if end>last_byte:
                            unique+=1;last_byte=end
                            meter.add('source_return_to_consumer_ns',received-int(row['t_ns']))
                    if s['flow_state'] not in states:states.append(s['flow_state'])
                    if s['sample_age_ms'] is not None:meter.add('latest_sample_age_at_consumer_ns',s['sample_age_ms']*1e6)
                    if not source_alive and s['source_stopped'] and s['backlog_bytes']==0:terminal_consumed=True
                except FileNotFoundError:pass  # Initial snapshot not published yet.
                except (OSError,ValueError,KeyError,TypeError) as exc:
                    if len(read_errors)<32:read_errors.append(type(exc).__name__+': '+str(exc))
                next_consume=now+config['consumer_interval_s']
            if not source_alive:
                if not config['observer'] or terminal_consumed or observer is not None and not observer.is_alive():break
            time.sleep(.01)
        else:raise TimeoutError('Bounded PTY case deadline')
        source.join(2)
        before=manifest(root/'bundle')
        if observer is not None:
            stop.set();observer.join(3)
            if observer.is_alive():raise TimeoutError('Observer did not stop')
        after=manifest(root/'bundle');atomic_json(root/'native-hashes-after.json',after)
        native=small_json(root/'laboratory.json')
        obs=small_json(root/'view'/'observer-report.json') if observer is not None else None
        raw=after['rx-02.serial.log']
        report=dict(schema='native-PTY-observer-comparison-1',methodology_revision='sustained-PTY-3',scenario=scenario,config=config,
            duration_s=duration,source_exitcode=source.exitcode,observer_exitcode=observer.exitcode if observer else None,
            native_integrity_ok=native['integrity_ok'],native_replay_ok=native['replay_ok'],
            native_fatal=native['fatal'],native_errors=native['errors'],native_closed=native['closed'],
            native_open_close_counts=native['open_close_counts'],native_windows=native['windows'],
            active_service_duration_s=native['active_service_duration_s'],
            generated_rows=native['generated_rows'],generated_bytes=native['generated_bytes'],raw_bytes=raw['bytes'],
            source_byte_count_equals_raw=native['generated_bytes']==raw['bytes'],
            generated_sha256=native['generated_sha256'],raw_sha256=raw['sha256'],
            source_sha256_equals_raw=native['generated_sha256']==raw['sha256'],
            original_unchanged_during_observer_drain=before==after,
            native_sampled_cpu_percent_one_core=sampled_cpu_percent(native['resources']),
            native_sampled_max_rss_kib=max(r['rss_kib'] for r in native['resources']),
            native_service_interval=native['timings']['values'].get('service_interval_ns'),
            observer=obs,consumer=dict(reads=reads,unique_rows=unique,revision_gaps=revision_gaps,
                rows_not_observed=None if obs is None else obs['final']['rows_seen']-unique,
                states=states,errors=read_errors,timings=meter.summary(),resources=consumer_resources,
                sampled_cpu_percent_one_core=sampled_cpu_percent(consumer_resources),
                cpu_ns=time.process_time_ns()-cpu_start),
            physical_UART_opened=False,clock_binding_outside_original=True)
        ok=(source.exitcode==0 and native['integrity_ok'] and native['replay_ok'] and not native['fatal'] and not native['errors']
            and not native['producer_error'] and native['active_service_duration_s'] is not None
            and native['active_service_duration_s']>=duration and not native['windows']
            and not native['timings']['overflow'] and not native['producer_timing']['overflow']
            and before==after and report['source_byte_count_equals_raw'] and report['source_sha256_equals_raw']
            and native['open_close_counts']=={'open':1,'close':1}
            and native['closed'].get('RX-02',{}).get('confirmed') is True)
        if obs is not None:
            final=obs['final']
            ok=(ok and observer.exitcode==0 and not obs['errors'] and not read_errors and terminal_consumed
                and final['source_stopped'] and final['backlog_bytes']==0 and final['invalid_lines']==0
                and final['seq']==native['persistence_status']['final_operations']
                and obs['raw_bytes_read']==raw['bytes'] and final['rows_seen']==native['generated_rows']
                and final['rows_seen']==final['rows_discarded_view']+len(final['rows'])
                and obs['max_rows_retained']<=config['max_rows'] and obs['max_snapshot_bytes']<=MAX_SNAPSHOT
                and not obs['timings']['overflow'] and not meter.overflow and 0<unique<=final['rows_seen'])
            if scenario=='slow':
                ok=ok and (duration<10 or 0<unique<final['rows_seen'] and final['rows_discarded_view']>0)
        report['checks_passed']=bool(ok);atomic_json(root/'comparison.json',report)
        return report
    finally:
        stop.set()
        for process in (observer,source):
            if process is not None and process.is_alive():
                process.terminate();process.join(3)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-new',type=Path,required=True)
    p.add_argument('--duration',type=float,default=8)
    p.add_argument('--repetitions',type=int,choices=(1,2,3),default=2)
    p.add_argument('--scenario',choices=('all',*SCENARIOS),default='all')
    a=p.parse_args();out=a.output_new.resolve()
    if not out.is_relative_to(ROOT/'results/local') or not 3<=a.duration<=MAX_DURATION_S:
        p.error(f'New results/local path and duration 3..{MAX_DURATION_S} s required')
    sys.addaudithook(guard);out.mkdir(parents=True,exist_ok=False)
    source_names=('tools/medir_observador_pty.py','src/csi_live_observer.py','src/rx02_service_lab.py',
        'src/presence_rx02_uart.py','src/rx02_checkpoint_journal.py')
    atomic_json(out/'measurement-plan.json',dict(schema='PTY-load-plan-1',methodology_revision='sustained-PTY-3',host_boot_id=boot_id(),
        recorded_at_utc=datetime.now(timezone.utc).isoformat(),python=sys.version,
        os=dict(system=os.uname().sysname,kernel=os.uname().release,machine=os.uname().machine),
        allowed_logical_cpus=len(os.sched_getaffinity(0)),
        sources={n:digest(ROOT/n) for n in source_names},duration_s=a.duration,repetitions=a.repetitions,
        scenario=a.scenario,scenarios=SCENARIOS,source_rate_hz=5,source_fragment_interval_ms=20,observer_interval_ms=250,
        note='Unscaled host clock; synthetic owned PTY only; no RF, TCP or browser paint latency'))
    reports=[]
    for repetition in range(a.repetitions):
        order=list(SCENARIOS) if repetition%2==0 else list(reversed(SCENARIOS))
        if a.scenario!='all':order=[a.scenario]
        for scenario in order:
            case=out/f'{len(reports)+1:02d}-{scenario}'
            try:r=measure_case(case,scenario,a.duration)
            except BaseException as exc:
                atomic_json(out/'interrupted.json',dict(case=case.name,error=repr(exc),completed=[r['scenario'] for r in reports]))
                raise
            reports.append(r);print(json.dumps(dict(case=case.name,passed=r['checks_passed'],rows=r['generated_rows'],
                cpu_percent=r['native_sampled_cpu_percent_one_core'])),flush=True)
    summary={}
    for name in SCENARIOS:
        group=[r for r in reports if r['scenario']==name]
        if group:summary[name]=dict(cases=len(group),all_checks_passed=all(r['checks_passed'] for r in group),
            median_native_cpu_percent=statistics.median(r['native_sampled_cpu_percent_one_core'] for r in group),
            max_native_service_interval_ns=max(r['native_service_interval']['max'] for r in group))
    atomic_json(out/'summary.json',dict(schema='PTY-load-summary-1',scenarios=summary,
        limitations=['Small synthetic load comparison, no hardware equivalence or causal overhead guarantee',
                     'Latency starts at host read completion; excludes RF, firmware, browser network and paint',
                     'Native cpu_ns/peak_rss in laboratory.json include finalization/audit; sampled service CPU is separate',
                     'Slow scenario deliberately uses eight display rows; visual losses are not original byte losses'],
        checks_passed=all(r['checks_passed'] for r in reports)))
    return int(not all(r['checks_passed'] for r in reports))


if __name__=='__main__':raise SystemExit(main())
