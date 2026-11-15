#!/usr/bin/env python3
"""Prepare and supervise one separately authorized RX-02 viewer diagnostic."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
from threading import Event, Thread
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from csi_live_observer import atomic_json, guard, read_bounded, small_json
from demo_csi_vivo import ViewServer, handler
from diagnostico_checkpoints_rx02 import diagnostic_report, serve
from presence_v4_journal import digest, write_new
from presence_v4_uart import verify_serial_runtime
from rx02_diagnostic.checkpoint import CheckpointRx02Session
from rx02_diagnostic.contract import HISTORICAL_CONNECTION, VIEW_IDENTITY_REVISION, validate_plan
from rx02_diagnostic.uart import preflight_rx02
from rx02_live_view import ATTEMPT, METADATA_LIMIT, Rx02Observer, clock_binding, clock_domain, current_rx02_snapshot


LOCAL = ROOT / 'results/local'
ORIGINAL_PREFLIGHT = LOCAL / 'preparacion-rx02-visor-240s-r1/preflight.json'
PREPARATION = LOCAL / 'preparacion-rx02-visor-240s-r1-revision-2'
BUNDLE = LOCAL / 'diagnostico-rx02-visor-240s-r1'
VIEW = LOCAL / 'vista-rx02-visor-240s-r1'
PREFLIGHT = PREPARATION / 'preflight.json'
AUTHORIZATION = PREPARATION / 'authorization.json'
NATIVE_TEMPLATE = ROOT / 'config/diagnostico_checkpoints_rx02_r1.review.json'
CONDITIONS_TEMPLATE = ROOT / 'config/visor_rx02_240s.condiciones.review.json'
SCRIPT = Path(__file__).resolve()
PORT = 8767
SOURCES = (
    'tools/visor_rx02_240s.py', 'src/rx02_live_view.py', 'src/rx02_live.html',
    'tools/demo_csi_vivo.py', 'src/csi_live.mjs', 'src/csi_live_observer.py',
    'src/csi_charts.mjs', 'src/offline_view.mjs', 'src/csi_chart_bundle.py', 'src/presence_v4_uart.py',
    'src/presence_rx02.py', 'src/presence_rx02_journal.py', 'src/presence_rx02_uart.py',
    'src/persistent_presence_v4.py', 'src/presence_v4_exploratory.py', 'src/presence_v4_journal.py',
    'src/presence_v4_pty.py', 'src/presence_v4_audio.py', 'src/availability_window.py',
    'src/capture_csi_multi.py', 'src/capture_csi.py', 'src/preserving_serial.py', 'src/controlled_protocol.py',
    'src/controlled_capture.py', 'tools/campana_presencia_v4.py', 'tools/piloto_presencia_rx02.py',
    'src/rx02_diagnostic/uart.py', 'src/rx02_diagnostic/contract.py',
    'src/rx02_diagnostic/checkpoint.py', 'src/rx02_diagnostic/journal.py',
    'tools/diagnostico_checkpoints_rx02.py', 'config/pyserial_uart_v4.lock.json',
    'config/csi_esp32s3.json', 'config/diagnostico_checkpoints_rx02_r1.review.json',
    'config/visor_rx02_240s.condiciones.review.json', 'config/visor_rx02_240s.propuesta.review.json',
)


def paths_are_local():
    for path in (LOCAL, PREPARATION, BUNDLE, VIEW):
        if path.resolve() != path:
            raise ValueError(f'Ruta fija con enlace no admitido: {path}')


def source_hashes():
    return {name: digest(ROOT / name) for name in SOURCES}


def native_plan(conditions):
    template = small_json(CONDITIONS_TEMPLATE, METADATA_LIMIT)
    if (conditions.keys() != template.keys() or conditions['rx01_disconnected'] is not True or
            conditions['environment'].keys() != template['environment'].keys()):
        raise ValueError('Declaraciones completas y RX-01 desconectada requeridas')
    plan = small_json(NATIVE_TEMPLATE, METADATA_LIMIT)
    plan.update(actor=conditions['actor'], mounting_reference=conditions['mounting_reference'],
                connection_id=ATTEMPT, partition_group=ATTEMPT,
                live_view=dict(attempt_id=ATTEMPT, identity_revision=VIEW_IDENTITY_REVISION),
                execution_mode='physical_after_approval', review_state='prepared_not_authorized',
                environment=dict(conditions['environment'], condition='Diagnóstico CSI y visualización, sin slots ni etiquetas'))
    plan['unused_receiver']['operator_confirmation'] = 'confirmed_current'
    return validate_plan(plan, allow_physical=True, execution=True)


def review_plan(conditions_path):
    raw = read_bounded(conditions_path, METADATA_LIMIT)
    plan = native_plan(json.loads(raw))
    plan['live_view'].update(bundle=str(BUNDLE), view=str(VIEW), sources=source_hashes())
    try:
        original = read_bounded(ORIGINAL_PREFLIGHT, METADATA_LIMIT)
    except FileNotFoundError:
        pass
    else:
        recorded = json.loads(original)
        previous = recorded['plan']
        if (recorded.get('schema') != 'rx02-live-preflight-1' or recorded.get('attempt_id') != ATTEMPT or
                previous.get('connection_id') != HISTORICAL_CONNECTION or
                previous.get('partition_group') != HISTORICAL_CONNECTION or
                recorded.get('physical_UART_opened') is not False):
            raise ValueError('El preflight original no corresponde a la revisión anterior')
        plan['live_view']['previous_preflight'] = dict(path=str(ORIGINAL_PREFLIGHT),
                                                      sha256=hashlib.sha256(original).hexdigest())
    return dict(schema='rx02-live-review-2', state='FRESH_METADATA_PREFLIGHT_REQUIRED', attempt_id=ATTEMPT,
                physical_UART_opened=False, metadata_checked_now=False, authorization_granted=False,
                conditions_sha256=hashlib.sha256(raw).hexdigest(), plan=plan)


def prepare(conditions_path):
    paths_are_local()
    if PREFLIGHT.exists() or AUTHORIZATION.exists() or BUNDLE.exists() or VIEW.exists():
        raise ValueError('El preflight, la autorización o la salida de este intento ya existe')
    review = review_plan(conditions_path)
    plan = review['plan']
    verify_serial_runtime()
    free = shutil.disk_usage(LOCAL).free
    if free < plan['storage_policy']['initial_free_bytes']:
        raise ValueError('Espacio libre insuficiente para iniciar')
    identity = preflight_rx02(plan)['RX-02']
    plan['live_view'].update(identity=identity, clock_domain=clock_domain())
    report = dict(schema='rx02-live-preflight-2', attempt_id=ATTEMPT, physical_UART_opened=False,
                  initial_free_bytes=free, conditions_sha256=review['conditions_sha256'], plan=plan)
    PREPARATION.mkdir(exist_ok=True)
    write_new(PREFLIGHT, report)
    return report


def reviewed_preflight():
    raw = read_bounded(PREFLIGHT, METADATA_LIMIT)
    report = json.loads(raw)
    plan = validate_plan(report['plan'], allow_physical=True, execution=True)
    live = plan['live_view']
    if (report.get('schema') != 'rx02-live-preflight-2' or report.get('attempt_id') != ATTEMPT or
            report.get('physical_UART_opened') is not False or plan['authorization_granted'] is not False or
            plan['connection_id'] != ATTEMPT or plan['partition_group'] != ATTEMPT or
            live['attempt_id'] != ATTEMPT or live['bundle'] != str(BUNDLE) or live['view'] != str(VIEW) or
            live['clock_domain'] != clock_domain() or live['sources'] != source_hashes()):
        raise ValueError('Preflight de otro intento, arranque, ruta o código')
    return plan, f'{ATTEMPT}:{hashlib.sha256(raw).hexdigest()}'


def approved():
    plan, reference = reviewed_preflight()
    grant = small_json(AUTHORIZATION, METADATA_LIMIT)
    if (grant.get('schema') != 'rx02-live-authorization-1' or grant.get('attempt_id') != ATTEMPT or
            grant.get('authorization_granted') is not True or grant.get('single_attempt') is not True or
            grant.get('reference') != reference or
            not isinstance(grant.get('human_statement'), str) or not grant['human_statement'].strip()):
        raise ValueError('Falta autorización explícita para este preflight y un único intento')
    return plan, reference


class ReviewedSession(CheckpointRx02Session):
    """Compare the native constructor's fresh snapshot before it can open."""

    def command(self, op, **data):
        if op == 'begin' and self.endpoints['RX-02'].expected != self.machine.plan['live_view']['identity']:
            raise ValueError('Cambió la identidad verificada. Apertura cancelada.')
        return super().command(op, **data)


def capture_worker():
    plan, reference = approved()
    if small_json(VIEW / 'attempt.json') != dict(attempt_id=ATTEMPT, reference=reference) or BUNDLE.exists():
        raise ValueError('Intento no iniciado por el supervisor o salida ya usada')
    write_new(VIEW / 'capture-started.json', dict(attempt_id=ATTEMPT, reference=reference))
    with ReviewedSession(BUNDLE, plan, authorization_reference=reference) as session:
        try:
            atomic_json(VIEW / 'clock-binding.json', clock_binding(BUNDLE, reference))
        except (OSError, ValueError) as exc:
            print(f'Visor sin constancia de reloj: {exc}', file=sys.stderr, flush=True)
        serve(session)


def observer_worker():
    plan, reference = reviewed_preflight()
    deadline = None
    observer = None
    next_poll = time.monotonic()
    supervisor = os.getppid()
    try:
        while True:
            if deadline is None and ((VIEW / 'source-exit.json').is_file() or os.getppid() != supervisor):
                deadline = time.monotonic() + 10
            if observer is None and (VIEW / 'clock-binding.json').is_file():
                observer = Rx02Observer(BUNDLE, VIEW, plan, reference)
            if observer is not None:
                observer.poll()
                snapshot = observer.snapshot()
                atomic_json(VIEW / 'latest.json', snapshot)
                if observer.error:
                    raise ValueError(observer.error)
                if deadline is not None and snapshot['backlog_bytes'] == 0 and observer.source_stopped:
                    if observer.raw_offset != observer.paths[1].stat().st_size:
                        raise ValueError('Quedaron bytes brutos sin observar')
                    write_new(VIEW / 'observer-result.json', dict(rows_seen=observer.total,
                              rows_discarded_view=observer.dropped, invalid_lines=observer.invalid,
                              operations=observer.seq, raw_bytes=observer.raw_offset))
                    return int(observer.total == 0)
            if deadline is not None and time.monotonic() >= deadline:
                if observer is not None:
                    observer.stop('El proceso de adquisición salió. Cierre sujeto a auditoría.')
                    atomic_json(VIEW / 'latest.json', observer.snapshot())
                raise ValueError('Vista sin cierre de fuente o sin drenaje completo')
            next_poll = max(time.monotonic(), next_poll + .25)
            time.sleep(max(0, next_poll - time.monotonic()))
    finally:
        if observer is not None:
            observer.close()


def audit_worker():
    plan, reference = reviewed_preflight()
    exited = small_json(VIEW / 'source-exit.json')
    if (exited.get('attempt_id') != ATTEMPT or exited.get('reference') != reference or
            type(exited.get('exit_code')) is not int):
        raise ValueError('Falta constancia de salida del proceso capturador')
    result = dict(attempt_id=ATTEMPT, connection_id=plan['connection_id'], partition_group=plan['partition_group'],
                  reference=reference, capture_exit_code=exited['exit_code'],
                  integrity_ok=False, replay_ok=False, close_verified=False, diagnostic_ok=False)
    try:
        if not (BUNDLE / 'manifest.json').is_file():
            raise ValueError('Bundle incompleto. Falta el manifiesto final.')
        if small_json(BUNDLE / 'plan.json', METADATA_LIMIT) != plan:
            raise ValueError('Plan nativo distinto del revisado')
        if small_json(BUNDLE / 'authorization-consumed.json', METADATA_LIMIT).get('reference') != reference:
            raise ValueError('Consumo de autorización incompatible')
        report = diagnostic_report(BUNDLE)
        if report['state']['connection_id'] != ATTEMPT or report['state']['partition_group'] != ATTEMPT:
            raise ValueError('Identidad de replay incompatible')
        write_new(VIEW / 'audit-native.json', report)
        result.update(integrity_ok=report['integrity_ok'], replay_ok=report['replay_ok'],
                      close_verified=report['diagnostic']['close_ok'],
                      diagnostic_ok=report['diagnostic']['diagnostic_ok'],
                      quality_ok=report['state']['connection']['quality_ok'],
                      manifest_sha256=digest(BUNDLE / 'manifest.json'))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result['error'] = str(exc)
    write_new(VIEW / 'audit-result.json', result)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return int(not result['diagnostic_ok'])


def spawn(worker):
    return subprocess.Popen([sys.executable, '-B', str(SCRIPT), worker], cwd=ROOT, start_new_session=True)


def run_attempt():
    plan, reference = approved()
    if BUNDLE.exists() or VIEW.exists():
        raise ValueError('La salida del intento ya existe. No hay reintentos.')
    if preflight_rx02(plan)['RX-02'] != plan['live_view']['identity']:
        raise ValueError('Cambió la identidad o permisos desde el preflight')
    with ViewServer(('127.0.0.1', PORT), handler(VIEW, snapshot_reader=current_rx02_snapshot, page='rx02_live.html')) as server:
        server.timeout = .1
        VIEW.mkdir(exist_ok=False)
        write_new(VIEW / 'attempt.json', dict(attempt_id=ATTEMPT, reference=reference))
        print(f'Visor de solo lectura: http://127.0.0.1:{PORT}/ · Ctrl-C solicita cierre del capturador.', flush=True)
        interrupted = False
        signaled = False
        http_failed = False
        stop_http = Event()

        def request_close(signum, frame):
            nonlocal interrupted
            interrupted = True

        def serve_view():
            nonlocal http_failed
            try:
                while not stop_http.is_set():
                    server.handle_request()
            except OSError as exc:
                if not stop_http.is_set():
                    http_failed = True
                    print(f'Falló el servidor del visor: {exc}', file=sys.stderr, flush=True)

        original_handler = signal.signal(signal.SIGINT, request_close)
        observer = capture = None
        try:
            Thread(target=serve_view, name='rx02-http-read-only', daemon=True).start()
            observer = spawn('--observer-worker')
            if interrupted:
                return 1
            capture = spawn('--capture-worker')
            while capture.poll() is None:
                if interrupted and not signaled:
                    signaled = True
                    capture.send_signal(signal.SIGINT)
                time.sleep(.05)
            capture_code = capture.wait()
            write_new(VIEW / 'source-exit.json', dict(attempt_id=ATTEMPT, reference=reference, exit_code=capture_code))
            auditor = spawn('--audit-worker')
            while auditor.poll() is None or observer.poll() is None:
                time.sleep(.05)
            audit_code, view_code = auditor.wait(), observer.wait()
            # Give the browser a chance to receive the terminal audit status.
            if not interrupted:
                time.sleep(1)
            print(f'Capturador={capture_code} · visor={view_code} · auditor={audit_code} · evidencia {VIEW}', flush=True)
        finally:
            stop_http.set()
            if capture is not None and capture.poll() is None:
                if not signaled:
                    capture.send_signal(signal.SIGINT)
                capture.wait()
            if observer is not None and observer.poll() is None:
                observer.terminate()
                observer.wait()
            signal.signal(signal.SIGINT, original_handler)
    return int(any((capture_code, view_code, audit_code, interrupted, http_failed)))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--review-plan', type=Path, metavar='CONDICIONES_JSON')
    mode.add_argument('--preflight-only', type=Path, metavar='CONDICIONES_JSON')
    mode.add_argument('--review', action='store_true')
    mode.add_argument('--execute-after-approval', action='store_true')
    for worker in ('capture', 'observer', 'audit'):
        mode.add_argument(f'--{worker}-worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    paths_are_local()
    if not args.capture_worker:
        sys.addaudithook(guard)
    try:
        if args.review_plan:
            print(json.dumps(review_plan(args.review_plan), indent=2, ensure_ascii=False))
        elif args.preflight_only:
            report = prepare(args.preflight_only)
            print(json.dumps(dict(preflight=str(PREFLIGHT), **report), indent=2, ensure_ascii=False))
        elif args.review:
            plan, reference = reviewed_preflight()
            print(json.dumps(dict(state='REVIEW', authorization_reference=reference, plan=plan,
                command='.venv/bin/python -B tools/visor_rx02_240s.py --execute-after-approval'),
                indent=2, ensure_ascii=False))
        elif args.execute_after_approval:
            return run_attempt()
        elif args.capture_worker:
            capture_worker()
        elif args.observer_worker:
            return observer_worker()
        else:
            return audit_worker()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'RX-02: {exc}', file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
