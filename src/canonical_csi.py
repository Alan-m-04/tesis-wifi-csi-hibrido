"""Loss-aware offline representation. No acquisition, transport or inference."""
import base64
import csv
import hashlib
import json
from pathlib import Path

import capture_csi_multi as capture
from csi_correspondence import idf_complex, amplitude_phase, documented_ht20_layout, carrier_role
from validate_capture import audit_capture
from controlled_protocol import V1, V2

ROOT = Path(__file__).resolve().parents[1]
REJECTED_LABEL = 'captura histórica con validación estricta rechazada'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def accepted_raw_lines(path):
    """Keep original byte offsets and full line bytes, including CR/LF."""
    offset=0; found=[]
    for number,line in enumerate(path.read_bytes().splitlines(keepends=True),1):
        start=offset;offset+=len(line)
        if not line.endswith(b'\n'):
            continue
        text=capture.ANSI.sub('',line.decode('utf-8',errors='replace')).strip()
        if not text.startswith('CSI_DATA,'):
            continue
        try:
            fields,record,values=capture.validate_sample(text)
        except (ValueError,TypeError,csv.Error,StopIteration):
            continue
        if record['mac'].lower()!=capture.SOURCE or (values['channel'],values['bandwidth'],values['rx_state'])!=(11,0,0):
            continue
        found.append((fields,{'line_1based':number,'byte_offset':start,'byte_length':len(line),
                             'line_sha256':digest(line),'line_base64':base64.b64encode(line).decode()}))
    return found


def canonical_block(raw, block, invalid):
    """One documented LTF view; roles and hardware validity are distinct."""
    a,b=block['byte_start'],block['byte_stop']
    global_pairs=idf_complex(raw,invalid)
    values=global_pairs[a//2:b//2]
    roles=[carrier_role(block['name'],k) for k in block['indices']]
    polar=[amplitude_phase(z) for z in values]
    return {'ltf':block['name'],'byte_start':a,'byte_stop':b,'indices':list(block['indices']),
            'roles':roles,'real':[None if z is None else int(z.real) for z in values],
            'imag':[None if z is None else int(z.imag) for z in values],
            'amplitude':[x[0] for x in polar],'phase_rad':[x[1] for x in polar],
            'hardware_valid':[z is not None for z in values],
            'cfr_usable':[z is not None and role in ('data','pilot') for z,role in zip(values,roles)],
            'phase_known':[x[1] is not None for x in polar]}


def stringify_ns(value):
    if isinstance(value,dict):
        return {k:str(v) if k.endswith('_ns') and isinstance(v,int) else stringify_ns(v) for k,v in value.items()}
    if isinstance(value,list):return [stringify_ns(v) for v in value]
    return value


def canonicalize(directory, manifest, profile):
    directory=Path(directory)
    audit=audit_capture(directory,manifest)
    if not audit['manifest_ok'] or not all(x['integrity_ok'] for x in audit['receivers'].values()):
        raise ValueError('Source integrity mismatch; diagnostic rejection is not permission to alter bytes')
    session=json.loads((directory/'session.json').read_text())
    gate=int(session['capture_start_monotonic_ns'])
    evidence=manifest['evidence_type'] if manifest else session.get('evidence_type','unspecified')
    if manifest and manifest.get('source_run_kind') in (V1, V2):
        prefix='captura dual controlada' if evidence=='physical_capture' else 'prueba sintética controlada'
        if manifest['source_run_kind'] == V2:
            prefix += ' v2'
        label=prefix+' con validación estricta '+('aceptada' if audit['quality_ok'] else 'rechazada')
    else:
        label=REJECTED_LABEL if evidence=='physical_capture' and not audit['quality_ok'] else 'datos diagnósticos; sin conclusiones de presencia'
    files={f.name:{'bytes':f.stat().st_size,'sha256':digest(f.read_bytes())} for f in directory.iterdir()
           if f.name in ({'session.json'}|{rx.lower()+ext for rx in capture.RECEIVERS for ext in ('.csv','.serial.log','.summary.json')})}
    if profile.get('target')!='esp32s3':raise ValueError('ESP32-S3 profile required')
    config=profile['firmware_ltf_config']
    output={'schema':'tesis-canonical-csi-v1','evidence_type':evidence,'diagnostic_only':True,
            'status_label':label,'strict_quality_ok':audit['quality_ok'],'strict_audit':audit,
            'run_id':manifest.get('source_run_id') if manifest else session['session_id'],
            'original_files':files,'original_session':stringify_ns(session),'profile':profile,
            'source_manifest':stringify_ns(manifest),
            'derivation':{'base_commit':'73099b3347ff5403ca789c7c87d398ec7928b09b',
                          'representation':'real+j*imag from Im/Re; byte order and raw originals preserved',
                          'profile_sha256':digest(json.dumps(profile,sort_keys=True).encode()),
                          'firmware_sources':{x['repository_path']:x['sha256'] for x in json.loads((ROOT/'docs/PROCEDENCIA_BASE.json').read_text())['files'] if x['repository_path'].endswith('app_main.c')}},
            'profile_evidence':'verified source configuration; historical installed binary not attested',
            'ltf_evidence':'conditional ESP-IDF v5.4 HT20/non-STBC table model; not inferred from length alone',
            'clock_policy':'host read timestamps shared per chunk; no RF synchronization or interpolation',
            'capture_start_monotonic_ns':str(gate),'receivers':{}}
    # Preserve long integer timestamps as decimal strings everywhere in the exported envelope.
    for key in ('capture_start_monotonic_ns','capture_deadline_monotonic_ns'):
        output['original_session'][key]=str(output['original_session'][key])
    v2 = session.get('protocol') == V2
    if v2:
        output['nominal_window'] = {
            'seconds': session['requested_seconds'],
            'start_ns': str(session['controlled']['common_start_ns']),
            'deadline_ns': str(session['controlled']['common_deadline_ns']),
            'counts_and_stops': {rx: {key: data[key] for key in
                ('preamble_rows', 'common_window_rows', 'post_deadline_rows', 'stop')}
                for rx, data in audit['receivers'].items()}}
    for rx,serial in capture.RECEIVERS.items():
        raw_path=directory/(rx.lower()+'.serial.log');csv_path=directory/(rx.lower()+'.csv')
        raw_rows=accepted_raw_lines(raw_path)
        with csv_path.open(newline='') as stream:
            reader=csv.DictReader(stream);rows=[(r,reader.line_num) for r in reader]
        if len(raw_rows)!=len(rows):raise ValueError('Raw/CSV row count differs')
        frames=[]
        for index,((row,csv_line),(raw_fields,raw_ref)) in enumerate(zip(rows,raw_rows)):
            if raw_fields!=[row[k] for k in capture.FIELDS]:raise ValueError('Raw/CSV fields differ')
            metadata={k:int(row[k]) for k in capture.FIELDS if k not in ('type','mac','data')}
            blocks=documented_ht20_layout(metadata,config)
            raw=json.loads(row['data'])
            frames.append({'original_fields':dict(row),'csv_record_index_0based':index,'csv_line_1based':csv_line,
                           'raw_reference':dict(raw_ref,file=raw_path.name,file_sha256=files[raw_path.name]['sha256']),
                           'csv_reference':{'file':csv_path.name,'sha256':files[csv_path.name]['sha256']},
                           'receiver_id':rx,'usb_serial':serial,'callback_id':row['id'],
                           'host_monotonic_ns':row['host_monotonic_ns'],'host_timestamp_utc':row['host_timestamp_utc'],
                           'host_elapsed_ns':str(int(row['host_monotonic_ns'])-gate),
                           'local_timestamp_us_uint32':row['local_timestamp'],
                           'blocks':[canonical_block(raw,b,bool(metadata['first_word_invalid'])) for b in blocks]})
            if v2:
                when = int(row['host_monotonic_ns'])
                phase = ('preamble' if when < int(session['controlled']['common_start_ns']) else
                         'nominal' if when < int(session['controlled']['common_deadline_ns']) else 'after_deadline')
                frames[-1].update(timing_phase=phase, received_in_common_window=phase == 'nominal')
        output['receivers'][rx]={'receiver_id':rx,'usb_serial':serial,'frames':frames}
    return output
