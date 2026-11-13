"""v3 acquisition lifecycle. Physical execution remains behind the existing CLI gate."""
from contextlib import ExitStack
import json
from pathlib import Path
import shutil
import threading
import time

import controlled_capture as base
from availability_window import AvailabilityCoordinator
from controlled_protocol import V3, STOP_POLICY_V2, AVAILABILITY_V3
from preserving_serial import preserving_serial_type


def run_capture_v3(plan, output, *, test_backend=None, seconds=None):
    base.validate_plan(plan)
    import serial
    if serial.__version__ != '3.5':
        raise ValueError('Audited pySerial 3.5 required')
    if test_backend is None and seconds is not None:
        raise ValueError('Physical duration must be 30 seconds')
    duration_ns = AVAILABILITY_V3['window_ns'] if seconds is None else int(seconds * 1e9)
    wait_ns = AVAILABILITY_V3['max_wait_ns'] if test_backend is None else test_backend.get(
        'availability_wait_ns', AVAILABILITY_V3['max_wait_ns'])
    identities = base.preflight(plan) if test_backend is None else test_backend['identities']
    out = Path(output).resolve()
    if not out.is_relative_to(base.ROOT / 'results/local'):
        raise ValueError('Output must be a NEW internal results/local directory')
    if shutil.disk_usage(out.parent if out.parent.exists() else base.ROOT).free < 100 * 1024 * 1024:
        raise ValueError('Need at least 100 MiB free internally')
    out.mkdir(parents=True, exist_ok=False)
    directory = out / 'capture'; directory.mkdir()
    base.dump_new(out / 'plan.json', plan)
    provenance = base.provenance(plan)
    provenance['startup_policy'] = 'whole connection retained; one prospective availability window; no flush'
    base.dump_new(out / 'provenance.json', provenance)
    base.dump_new(out / 'preflight.json', identities)
    session = {'protocol': V3, 'session_id': out.name, 'requested_seconds': duration_ns / 1e9,
        'evidence_type': 'physical_capture' if test_backend is None else 'synthetic_fixture',
        'receivers': dict(base.PORTS), 'results': {}, 'status': 'opening_ports',
        'note': base.capture.NOTE, 'started_utc': base.capture.utc_now(),
        'capture_start_monotonic_ns': time.monotonic_ns(), 'lifecycle': [],
        'controlled': {'seconds': duration_ns / 1e9, 'stable_window': None,
                       'stop_policy': dict(STOP_POLICY_V2), 'availability_policy': dict(AVAILABILITY_V3),
                       'effective_window_ns': str(duration_ns), 'effective_wait_ns': str(wait_ns)}}
    stop = threading.Event() if test_backend is None else test_backend.get('stop_event', threading.Event())
    unused_gate = threading.Event()
    threads = []
    factory = preserving_serial_type(serial.Serial) if test_backend is None else test_backend['factory']

    def lifecycle(event, rx=None, **data):
        session['lifecycle'].append(dict(event=event, receiver=rx,
            monotonic_ns=str(time.monotonic_ns()), utc=base.capture.utc_now(), **data))

    with (directory / 'availability.events.jsonl').open('x') as trace:
        def persist(event):
            trace.write(json.dumps(event, ensure_ascii=False) + '\n'); trace.flush()
        coordinator = AvailabilityCoordinator(sink=persist, window_ns=duration_ns, wait_ns=wait_ns)
        timing = {'seconds': duration_ns / 1e9, 'protocol': V3, 'read_from_open': True,
            'record_reads': True, 'stop_policy': dict(STOP_POLICY_V2), 'availability': coordinator,
            'deadline_getter': lambda: coordinator.stop_deadline,
            'reader_started': {rx: threading.Event() for rx in base.PORTS}}
        # Test hooks are unreachable from a physical plan or the command line.
        if test_backend is not None:
            callback = test_backend.get('coordinator_created')
            if callback:
                callback(coordinator, timing)

        def worker(rx, device):
            try:
                coordinator.reader_active(rx)
                result = base.capture.capture_receiver(device, rx, directory, out.name, unused_gate, stop, timing)
                session['results'][rx] = result
                if result.get('error'):
                    coordinator.fail('reader_error', rx); stop.set()
                coordinator.reader_finished(rx, result.get('stop', {}).get('stop_reason', 'missing_stop'),
                                            result.get('stop', {}).get('stopped_ns'))
            except Exception as exc:
                session['results'][rx] = {'error': f'{type(exc).__name__}: {exc}', 'format_reception_ok': False}
                coordinator.fail('reader_exception', rx); stop.set()

        def close(rx, device):
            lifecycle('closing', rx)
            try:
                device.close()
                lifecycle('closed', rx)
            except Exception as exc:
                lifecycle('close_error', rx, error=str(exc))
                coordinator.fail('close_error', rx)
                raise

        try:
            with ExitStack() as stack:
                try:
                    for rx, link in base.PORTS.items():
                        if coordinator.a is not None and (time.monotonic_ns() >= coordinator.d or stop.is_set() or coordinator.fatal):
                            coordinator.evaluate()
                            raise RuntimeError('Startup deadline, abort or fatal before second open')
                        if test_backend is None and base.capture.verify_port(rx, link) != identities[rx]['resolved']:
                            raise ValueError('USB changed before opening ' + rx)
                        device = factory(port=None, baudrate=115200, timeout=.05, exclusive=True)
                        stack.callback(close, rx, device)
                        device.dtr = False; device.rts = False; device.port = link
                        lifecycle('opening', rx)
                        if coordinator.a is None:
                            coordinator.begin()  # A immediately before first open; deadline never slides.
                        if time.monotonic_ns() >= coordinator.d or stop.is_set() or coordinator.fatal:
                            coordinator.evaluate()
                            raise RuntimeError('Startup deadline, abort or fatal before open')
                        device.open()
                        lifecycle('opened', rx, dtr_requested=False, rts_requested=False,
                                  open_input_flush_suppressed=getattr(device, 'open_flush_suppressed', None))
                        thread = threading.Thread(target=worker, args=(rx, device))
                        threads.append(thread); thread.start()
                        remaining = max(0, (coordinator.d - time.monotonic_ns()) / 1e9)
                        if not timing['reader_started'][rx].wait(min(2, remaining)):
                            raise RuntimeError('Reader did not start before deadline: ' + rx)
                    session['status'] = 'waiting_availability'
                    while any(t.is_alive() for t in threads):
                        coordinator.evaluate()
                        if coordinator.fatal:
                            stop.set()
                        if coordinator.t0 is not None:
                            session['status'] = 'capturing'
                        for thread in threads:
                            thread.join(timeout=.002)
                    if any(r.get('error') for r in session['results'].values()):
                        session['status'] = 'error'
                    elif stop.is_set() and coordinator.fatal == 'reader_termination_before_T1':
                        session['status'] = 'interrupted'
                    elif coordinator.fatal:
                        session['status'] = 'error'
                    elif stop.is_set():
                        session['status'] = 'interrupted'
                    elif coordinator.timed_out:
                        session['status'] = 'availability_timeout'
                    else:
                        session['status'] = 'completed'
                finally:
                    stop.set()
                    for thread in threads:
                        thread.join()
                    lifecycle('readers_joined')
            lifecycle('ports_closed')
        except KeyboardInterrupt:
            session['status'] = 'interrupted'; coordinator.fail('operator_abort')
        except Exception as exc:
            session.update(status='error', error=f'{type(exc).__name__}: {exc}')
            coordinator.fail('lifecycle_error')
        finally:
            stop.set()
            for thread in threads:
                thread.join()
            coordinator.emit('finished', status=session['status'])
            session['controlled'].update(coordinator.snapshot())
            session['capture_deadline_monotonic_ns'] = time.monotonic_ns()
            session['finished_utc'] = base.capture.utc_now()
            base.dump_new(directory / 'session.json', session)

    postflight = {}
    for rx, link in base.PORTS.items():
        try:
            if test_backend is None:
                node, props = base.capture.port_identity(link); base.capture.require_identity(rx, link, props)
                ok = node == identities[rx]['resolved'] and props.get('ID_MODEL_ID') == '55d3'
                postflight[rx] = {'identity_ok': ok}
            else:
                postflight[rx] = {'identity_ok': True, 'synthetic': True}
        except Exception as exc:
            postflight[rx] = {'identity_ok': False, 'error': str(exc)}
    base.dump_new(out / 'postflight.json', postflight)
    def entry(path):
        return {'name': path.name, 'bytes': path.stat().st_size, 'sha256': base.sha(path)}
    from validate_capture import NAMES, audit_capture
    manifest = {'schema': 'tesis-controlled-capture-v3', 'source_run_kind': V3, 'source_run_id': out.name,
        'evidence_type': session['evidence_type'], 'files': [entry(p) for p in sorted(directory.iterdir()) if p.name in NAMES],
        'read_ledgers': [entry(p) for p in sorted(directory.glob('*.reads.jsonl'))],
        'coordination_trace': entry(directory / 'availability.events.jsonl'),
        'postflight': postflight, 'source_directory': str(directory),
        'local_ignored_copy': str(directory.relative_to(base.ROOT)), 'operator_environment': plan['environment'],
        'source_provenance': provenance, 'plan_sha256': base.sha(out / 'plan.json')}
    base.dump_new(out / 'capture-manifest.json', manifest)
    try:
        audit = audit_capture(directory, manifest)
        quality = {'session_quality_ok': audit['quality_ok'], 'full_session': audit,
                   'connection_full': audit['connection_full'], 'experimental_window': audit['experimental_window'],
                   'retrospective_window_created': False}
        base.dump_new(out / 'window-index.json', {'schema': 'tesis-prospective-window-index-v3',
            'coordination_trace_sha256': manifest['coordination_trace']['sha256'],
            'T0_ns': audit['experimental_window']['T0_ns'], 'T1_ns': audit['experimental_window']['T1_ns'],
            'receivers': {rx: item['index'] for rx, item in audit['experimental_window']['receivers'].items()}})
    except Exception as exc:
        quality = {'session_quality_ok': False, 'audit_error': f'{type(exc).__name__}: {exc}'}
    base.dump_new(out / 'quality.json', quality)
    base.dump_new(out / 'bundle-manifest.json', {'scope': 'immutable full connection, prospective decision and derived audit; no self hash',
        'files': [{'path': str(p.relative_to(out)), 'bytes': p.stat().st_size, 'sha256': base.sha(p)}
                  for p in sorted(out.rglob('*')) if p.is_file()]})
    return 0 if quality['session_quality_ok'] else 1
