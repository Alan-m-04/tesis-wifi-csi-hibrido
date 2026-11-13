#!/usr/bin/env python3
"""Preparación R3 y preflight exclusivamente por metadatos; sin ruta de captura."""
import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools')]
from devrep_rx02 import source_hashes as historical_source_hashes
from presence_v4_journal import digest, write_new
from presence_v4_uart import identity, verify_serial_runtime
from capture_csi_multi import resolve_ports
from rx02_devrep.contract import validate_plan as validate_r1, PORTS
from rx02_devrep.series import boot_id

SERIES_ID = 'RX02-DEVREP-R3'
CONNECTION_ID = SERIES_ID + '-N01'
PREPARATION = Path('results/local/preparacion-devrep-r3-N01')
OUTPUT = 'results/local/devrep-rx02-r3-N01'
METADATA_COMPARISON_REVISION = 'udev-devlinks-path-permutation-1'
MUTABLE = {'actor', 'environment', 'mounting_reference', 'setup_snapshot_path',
           'setup_snapshot_sha256', 'unused_receiver', 'conditions_confirmation'}
CONFIRMED_PLAN = PREPARATION / 'plan.confirmado-r1.json'
CURRENT_CONDITIONS = (
    'Soy el operador de R3-N01 y estoy solo; puerta y ventanas cerradas, sin ventilador. '
    'Montaje, antenas, coaxiales, cables y puertos sin cambios respecto de la referencia '
    'de R2-N01; TX a algo más de 2 m, RX-02 a la derecha y misma marca para sentado. '
    'TX al cargador de pared, RX-02 por USB directo y RX-01 desconectada. '
    'Laptop enchufada y abierta, suspensión desactivada y otros lectores serie cerrados. '
    'Distingo los avisos desde fuera con la salida y volumen actuales. '
    'Para E saldré físicamente, cerraré la puerta y permaneceré fuera hasta el tono '
    'corto final de E; después regresaré y declararé E en la terminal. '
    'Para S estaré sentado y quieto en la marca hasta el cierre confirmado. '
    'Declararé lo realmente ocurrido; esta confirmación no autoriza captura.'
)


def source_hashes():
    sources = historical_source_hashes()
    names = ['src/rx02_devrep_r3_n01/' + name + '.py' for name in
             ('__init__', 'contract', 'journal', 'session', 'series')]
    names += ['tools/preflight_devrep_r3.py', 'tools/ejecutar_devrep_r3_n01.py']
    return dict(sources, **{name: digest(ROOT / name) for name in names})


def template():
    # Reutiliza solo el contrato técnico revisado, nunca condiciones de un plan físico.
    plan = validate_r1(json.loads((ROOT / 'config/devrep_r1/D01.review.json').read_text()))
    plan = copy.deepcopy(plan)
    plan.update(connection_id=CONNECTION_ID, partition_group=CONNECTION_ID,
                slots=[dict(id=CONNECTION_ID + '-' + c, condition=c) for c in ('E', 'S')],
                output_new=OUTPUT, execution_mode='offline_only', authorization_granted=False,
                review_only=True, review_state='R3_DRAFT_ONLY_CONDITIONS_AND_EXECUTOR_PENDING',
                ready_risk_reviewed=False, preparation_schema='devrep-independent-preparation-2',
                series_id=SERIES_ID, predecessor=None, acquisition_executor_enabled=False,
                actor='PENDIENTE', mounting_reference='PENDIENTE',
                setup_snapshot_path='PENDIENTE', setup_snapshot_sha256='PENDIENTE',
                conditions_confirmation=dict(confirmed_current=False, host_boot_id=None,
                                             declaration_path=None, declaration_sha256=None))
    plan['environment'] = dict.fromkeys(plan['environment'], 'PENDIENTE')
    plan['unused_receiver']['operator_confirmation'] = 'PENDIENTE'
    return plan


def local_file(name, expected_hash):
    if not isinstance(name, str):
        raise ValueError('Falta referencia local confirmada')
    path = (ROOT / name).resolve()
    if not path.is_relative_to((ROOT / PREPARATION).resolve()) or not path.is_file():
        raise ValueError('La declaración/montaje debe estar dentro de la preparación nueva')
    if digest(path) != expected_hash:
        raise ValueError('Declaración/montaje cambió: hace falta una revisión nueva')
    return path


def validate(plan, *, confirmed=False):
    reference = template()
    if set(plan) != set(reference) or any(plan[k] != v for k, v in reference.items() if k not in MUTABLE):
        raise ValueError('Plan R3, identidad, orden, criterios y salida nuevos exactos requeridos; sin autorización')
    if set(plan.get('environment', {})) != set(reference['environment']):
        raise ValueError('Campos ambientales incompletos o desconocidos')
    unused = plan.get('unused_receiver', {})
    if (set(unused) != set(reference['unused_receiver']) or
            any(unused.get(k) != v for k, v in reference['unused_receiver'].items()
                if k != 'operator_confirmation')):
        raise ValueError('RX-01 debe permanecer sin UART; disposición nueva por confirmar')
    if not confirmed:
        return
    confirmation = plan.get('conditions_confirmation', {})
    if (set(confirmation) != set(reference['conditions_confirmation']) or
            confirmation.get('confirmed_current') is not True or
            confirmation.get('host_boot_id') != boot_id()):
        raise ValueError('PENDIENTE: confirmar condiciones actuales con el usuario para este boot antes del preflight')
    values = [plan['actor'], plan['mounting_reference'], *plan['environment'].values()]
    if any(not isinstance(v, str) or not v.strip() or 'PENDIENTE' in v.upper() for v in values):
        raise ValueError('PENDIENTE: completar únicamente condiciones confirmadas por el usuario')
    if unused.get('operator_confirmation') != 'confirmed_current':
        raise ValueError('PENDIENTE: confirmar estado actual de RX-01')
    local_file(confirmation['declaration_path'], confirmation['declaration_sha256'])
    local_file(plan['setup_snapshot_path'], plan['setup_snapshot_sha256'])
    if plan['mounting_reference'] != plan['setup_snapshot_path']:
        raise ValueError('La referencia de montaje debe ser la nueva confirmada')


def metadata_snapshot():
    resolved = resolve_ports(['RX-02'], PORTS)
    snapshot = identity('RX-02')
    if resolved['RX-02'] != snapshot['resolved']:
        raise ValueError('Identidad USB cambió durante el preflight')
    enumerated = []
    for pattern in ('ttyACM*', 'ttyUSB*'):
        for tty in sorted(Path('/sys/class/tty').glob(pattern)):
            run = subprocess.run(['udevadm', 'info', '--query=property', '--path', str(tty.resolve())],
                                 check=True, capture_output=True, text=True, timeout=10)
            props = dict(line.split('=', 1) for line in run.stdout.splitlines() if '=' in line)
            enumerated.append(dict(sysfs=str(tty.resolve()), properties=props))
    serials = [x['properties'].get('ID_SERIAL_SHORT') for x in enumerated]
    if serials.count('5C93200689') != 1:
        raise ValueError('RX-02 debe tener una identidad única también en sysfs/udev')
    if '5C93199744' in serials:
        raise ValueError('RX-01 enumerada: contradice el plan pendiente de permanecer desconectada; revisar sin manipular')
    return dict(identities={'RX-02': snapshot}, enumerated_tty_metadata=enumerated)


def metadata_for_comparison(snapshot):
    """Solo DEVLINKS de udev ignora orden; no muta el original ni elimina duplicados."""
    comparable = copy.deepcopy(snapshot)
    if isinstance(comparable, dict) and isinstance(comparable.get('enumerated_tty_metadata'), list):
        for tty in comparable['enumerated_tty_metadata']:
            properties = tty.get('properties') if isinstance(tty, dict) else None
            if isinstance(properties, dict) and isinstance(properties.get('DEVLINKS'), str):
                properties['DEVLINKS'] = ' '.join(sorted(properties['DEVLINKS'].split()))
    return comparable


def metadata_snapshots_equal(first, second):
    return metadata_for_comparison(first) == metadata_for_comparison(second)


def confirm_current_conditions(plan_path, *, ask=None):
    """Human confirmation in the operator terminal; never queries USB or grants capture."""
    plan = json.loads(Path(plan_path).read_text())
    validate(plan)
    if plan['conditions_confirmation']['confirmed_current'] is not False:
        raise ValueError('Confirmación previa existente; conservarla y revisar antes de otra revisión')
    directory = ROOT / PREPARATION
    declaration = directory / 'declaracion-actual-terminal-r1.json'
    mounting = directory / 'montaje-confirmado-terminal-r1.json'
    confirmed = ROOT / CONFIRMED_PLAN
    if any(path.exists() for path in (declaration, mounting, confirmed)):
        raise ValueError('Artefacto de confirmación R3 existente; no sobrescribir ni reutilizar')
    host_boot = boot_id()
    input_hash = digest(Path(plan_path))
    print(CURRENT_CONDITIONS, flush=True)
    response = (ask or input)(
        'Solo si TODO sigue vigente, escriba CONFIRMO; si hay cambios, cancele y descríbalos: ')
    if response.strip() != 'CONFIRMO':
        raise ValueError('Condiciones actuales no confirmadas; sin metadatos ni autorización')
    if host_boot != boot_id() or input_hash != digest(Path(plan_path)):
        raise ValueError('Boot o plan cambió durante la confirmación; revisar')
    recorded = datetime.now(timezone.utc).isoformat()
    write_new(declaration, dict(schema='devrep-r3-current-operator-declaration-1',
        connection_id=CONNECTION_ID, recorded_at_utc=recorded, host_boot_id=host_boot,
        evidence_type='operator_declaration_not_physical_measurement',
        source='Confirmación explícita en terminal normal del operador',
        statement_shown=CURRENT_CONDITIONS, response=response,
        authorization_granted=False, physical_UART_opened=False, capture_executed=False))
    environment = dict(
        condition='Operador solo; puerta/ventanas cerradas y sin ventilador, según confirmación actual',
        occupancy='Solo operador; E se realizará saliendo físicamente y cerrando la puerta',
        movement='E: fuera hasta tono corto final; S: sentado y quieto hasta cierre confirmado',
        geometry='Montaje R2-N01 sin cambios; TX a algo más de 2 m, RX-02 a la derecha; misma marca sentada',
        tx_power='TX al cargador de pared; potencia RF no medida',
        mounting_confirmation='Antenas, coaxiales, cables y puertos sin cambios según confirmación actual',
        sound_practice_reference='Distingue avisos desde fuera con salida/volumen actuales; declaración humana',
        laptop_power_lid='Laptop enchufada y abierta',
        suspension_ac_battery='Suspensión desactivada según confirmación actual',
        serial_readers_absent='Otros lectores serie cerrados según confirmación actual')
    write_new(mounting, dict(schema='devrep-r3-current-setup-declaration-1',
        connection_id=CONNECTION_ID, recorded_at_utc=recorded, host_boot_id=host_boot,
        declaration_path=str(declaration.relative_to(ROOT)), declaration_sha256=digest(declaration),
        environment=environment, RX02_power='USB directo', RX01='Desconectada',
        evidence_type='operator_declaration_not_physical_measurement'))
    plan.update(actor='Operador de R3-N01, confirmado en terminal', environment=environment,
                mounting_reference=str(mounting.relative_to(ROOT)),
                setup_snapshot_path=str(mounting.relative_to(ROOT)), setup_snapshot_sha256=digest(mounting))
    plan['unused_receiver']['operator_confirmation'] = 'confirmed_current'
    plan['conditions_confirmation'] = dict(confirmed_current=True, host_boot_id=host_boot,
        declaration_path=str(declaration.relative_to(ROOT)), declaration_sha256=digest(declaration))
    validate(plan, confirmed=True)
    write_new(confirmed, plan)
    return confirmed


def run_preflight(plan_path, receipt):
    plan_path, receipt = Path(plan_path), Path(receipt)
    plan = json.loads(plan_path.read_text())
    validate(plan, confirmed=True)
    directory = (ROOT / PREPARATION).resolve()
    snapshots_path = receipt.with_suffix('.snapshots.json')
    if receipt.resolve().parent != directory or receipt.suffix != '.json' or receipt.exists() or snapshots_path.exists():
        raise ValueError('Recibo JSON nuevo directamente en preparación R3; no sobrescribir ni reutilizar')
    if (ROOT / OUTPUT).exists():
        raise ValueError('La salida de captura ya existe; no reintentar ni reemplazar')
    initial_boot, initial_plan_hash = boot_id(), digest(plan_path)
    hashes = source_hashes()
    hashes['tools/preflight_devrep_r3.py'] = digest(Path(__file__))
    verify_serial_runtime()  # Hash/versiones de pySerial; no construye Serial.
    free = shutil.disk_usage(directory).free
    if free < plan['storage_policy']['initial_free_bytes']:
        raise ValueError('Menos de 100 MiB libres antes de adquirir')
    first, second = metadata_snapshot(), metadata_snapshot()
    validate(plan, confirmed=True)
    comparison = dict(revision=METADATA_COMPARISON_REVISION, raw_equal=first == second,
                      equal_under_revision=metadata_snapshots_equal(first, second))
    # Evidencia sin aprobación, conservada incluso si la comparación siguiente falla.
    write_new(snapshots_path, dict(schema='devrep-r3-preflight-snapshots-1',
        state='SNAPSHOTS_ONLY_NOT_APPROVAL', recorded_at_utc=datetime.now(timezone.utc).isoformat(),
        connection_id=CONNECTION_ID, plan_sha256=initial_plan_hash, host_boot_id=initial_boot,
        first=first, second=second, metadata_comparison=comparison, sources=hashes,
        physical_UART_opened=False, capture_executed=False, authorization_granted=False))
    if not metadata_snapshots_equal(first, second) or boot_id() != initial_boot or digest(plan_path) != initial_plan_hash:
        raise ValueError('Metadatos, boot o plan cambiaron durante la inspección')
    current_hashes = source_hashes()
    current_hashes['tools/preflight_devrep_r3.py'] = digest(Path(__file__))
    if current_hashes != hashes:
        raise ValueError('Fuentes cambiaron durante el preflight')
    evidence = dict(schema='devrep-r3-preparation-metadata-1', state='PREFLIGHT_METADATA_ONLY',
                    recorded_at_utc=datetime.now(timezone.utc).isoformat(), series_id=SERIES_ID,
                    connection_id=CONNECTION_ID, plan_sha256=initial_plan_hash,
                    plan_path=str(plan_path.resolve().relative_to(ROOT.resolve())),
                    host_boot_id=initial_boot, metadata=first, sources=hashes,
                    metadata_snapshots=dict(first=first, second=second), metadata_comparison=comparison,
                    free_bytes=free, conditions_confirmed_current=True,
                    physical_UART_opened=False, capture_executed=False, authorization_granted=False,
                    acquisition_executor_enabled=False, ready_observed=False,
                    device_restart_status='unknown', exclusive_open_verified=False,
                    scope='Preparación R3; metadatos completos visibles al proceso; no habilita ejecutor R1 ni captura')
    write_new(receipt, evidence)
    return evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=ROOT / PREPARATION / 'plan.local.r1.json')
    parser.add_argument('--preflight-only', action='store_true')
    parser.add_argument('--confirm-current-conditions', action='store_true')
    parser.add_argument('--receipt-new', type=Path, default=ROOT / PREPARATION / 'preflight-r3-N01-r1.json')
    args = parser.parse_args(argv)
    try:
        if args.preflight_only:
            sidecar = args.receipt_new.with_suffix('.snapshots.json')
            if args.receipt_new.exists() or sidecar.exists() or (ROOT / OUTPUT).exists():
                raise ValueError('Salida o recibo existente; no sobrescribir ni reintentar')
            plan_path = confirm_current_conditions(args.plan) if args.confirm_current_conditions else args.plan
            result = run_preflight(plan_path, args.receipt_new)
        else:
            if args.confirm_current_conditions:
                raise ValueError('Confirmación de condiciones solo con --preflight-only')
            plan = json.loads(args.plan.read_text())
            validate(plan)
            result = dict(state='PREPARED_CONDITIONS_PENDING' if
                          plan['conditions_confirmation'].get('confirmed_current') is not True else
                          'PREPARED_NOT_AUTHORIZED', connection_id=CONNECTION_ID, output_new=OUTPUT,
                          physical_UART_opened=False, metadata_preflight_executed=False,
                          authorization_granted=False, acquisition_executor_enabled=False)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, EOFError, subprocess.SubprocessError) as exc:
        print('PREFLIGHT_NOT_APPROVED: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
