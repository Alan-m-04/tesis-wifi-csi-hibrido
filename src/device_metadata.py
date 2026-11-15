"""Current local metadata only; never constructs, opens or reads a UART.

Reuse the capture identity constants and udev/stat identification functions.
This inventory neither runs preflight nor changes any experimental state.
"""
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import stat

import capture_csi_multi as capture
from controlled_capture import PORTS

RECEIVERS=capture.RECEIVERS
TTY=re.compile(r'tty(?:ACM|USB)\d+$')


def catalogue():
    """Expected identities only; no observation is made by creating this list."""
    devices=[dict(id=rx,usb_serial=serial,by_id=PORTS[rx],by_id_observed=False,
        status='no_verificable',node=None,permissions=None,notes=[],queried_at_utc=None,
        ready=None,csi_received=None) for rx,serial in RECEIVERS.items()]
    devices.append(dict(id='TX-01',usb_serial=None,by_id=None,by_id_observed=False,node=None,
        permissions=None,status='no_verificable',status_text='no verificable por USB',
        queried_at_utc=None,ready=None,csi_received=None,
        notes=['TX alimentado externamente según el escenario declarado; no se infiere su estado eléctrico o WiFi.']))
    return devices


def dev_mount_complete(text):
    """Conservative absence gate: a full devtmpfs, not a masked /dev view.

Positive identity observations can still be shown in a limited namespace.
Absence is always local to this process, never proof of physical unplugging.
"""
    rows=[]
    for line in text.splitlines():
        fields=line.split()
        if len(fields)<10 or '-' not in fields:continue
        split=fields.index('-')
        if split<6 or split+1>=len(fields):continue
        rows.append((fields[4],fields[3],fields[5].split(','),fields[split+1]))
    dev=[r for r in rows if r[0]=='/dev']
    if not dev or dev[-1][1]!='/' or dev[-1][3]!='devtmpfs' or 'nodev' in dev[-1][2]:return False
    # A serial subtree or individual tty bind can hide host devices.
    return not any(p.startswith('/dev/serial') or TTY.fullmatch(p.removeprefix('/dev/'))
                   for p,_,_,_ in rows)


class LocalMetadata:
    def scan(self):
        notes=[];paths=set();visible=set();complete=True;usb_serials=set()
        try:
            entries=list(Path('/dev').iterdir())
            visible={p.name for p in entries}
            paths.update(str(p) for p in entries if TTY.fullmatch(p.name))
        except OSError as exc:
            complete=False;notes.append('/dev no enumerable: '+str(exc))
        try:
            sysnames={p.name for p in Path('/sys/class/tty').iterdir() if TTY.fullmatch(p.name)}
            if sysnames-visible:
                complete=False;notes.append('Hay tty en sysfs sin nodo visible en /dev: '+', '.join(sorted(sysnames-visible)))
        except OSError as exc:
            complete=False;notes.append('sysfs no enumerable: '+str(exc))
        # A receiver can be enumerated on USB before a tty driver/node exists.
        # Such a hint prevents an absence claim; it never supplies READY or CSI.
        try:
            for entry in Path('/sys/bus/usb/devices').iterdir():
                try:serial=(entry/'serial').read_text().strip()
                except FileNotFoundError:continue
                if serial in RECEIVERS.values():usb_serials.add(serial)
        except OSError as exc:
            complete=False;notes.append('Inventario USB/sysfs no verificable: '+str(exc))
        directory=Path('/dev/serial/by-id')
        try:paths.update(str(p) for p in directory.iterdir())
        except FileNotFoundError:pass  # No serial links is normal on a complete empty view.
        except OSError as exc:
            complete=False;notes.append('by-id no enumerable: '+str(exc))
        try:
            if not dev_mount_complete(Path('/proc/self/mountinfo').read_text()):
                complete=False;notes.append('Vista de /dev limitada o no demostrablemente completa; no permite afirmar ausencia.')
        except OSError as exc:
            complete=False;notes.append('Visibilidad de /dev no verificable: '+str(exc))
        if len(paths)>64:
            complete=False;notes.append('Inventario excede 64 rutas; consulta no concluyente.')
            paths=set(sorted(paths)[:64])
        return dict(paths=sorted(paths),complete=complete,notes=notes,usb_serials=sorted(usb_serials))

    def identity(self,path):
        # The existing helper uses resolve/stat and udevadm info, never Serial.
        return capture.port_identity(path)

    def permissions(self,node):
        st=os.stat(node)
        if not stat.S_ISCHR(st.st_mode):raise ValueError('El nodo dejó de ser un dispositivo de caracteres')
        return dict(mode=oct(stat.S_IMODE(st.st_mode)),uid=st.st_uid,gid=st.st_gid,
            effective_read=os.access(node,os.R_OK,effective_ids=True),
            effective_write=os.access(node,os.W_OK,effective_ids=True))


def snapshot(probe=None,*,now=None):
    probe=probe or LocalMetadata()
    started=(now or (lambda:datetime.now(timezone.utc).isoformat()))()
    expected=catalogue();devices={d['id']:d for d in expected if d['id'] in RECEIVERS}
    try:scan=probe.scan()
    except (OSError,ValueError) as exc:scan=dict(paths=[],complete=False,notes=['Error de inventario: '+str(exc)])
    found={rx:{} for rx in RECEIVERS};query_errors=[]
    for path in scan['paths']:
        claimed=next((rx for rx in RECEIVERS if path==PORTS[rx]),None)
        if claimed:devices[claimed]['by_id_observed']=True
        try:
            node,props=probe.identity(path)
            rx=next((r for r,s in RECEIVERS.items() if props.get('ID_SERIAL_SHORT')==s),None)
            if claimed and claimed!=rx:
                raise ValueError('La ruta by-id no coincide con la serie USB esperada')
            if rx is None:
                if not props.get('ID_SERIAL_SHORT'):raise ValueError('Serie USB no verificable')
                continue
            capture.require_identity(rx,path,props)
            if props.get('ID_MODEL_ID')!='55d3':raise ValueError('PID USB distinto del esperado')
            item=dict(node=node,permissions=None)
            try:item['permissions']=probe.permissions(node)
            except (OSError,ValueError,NotImplementedError) as exc:
                raise ValueError('Nodo/permisos no verificables: '+str(exc)) from exc
            found[rx][node]=item
        except (OSError,ValueError) as exc:
            query_errors.append(str(path)+': '+str(exc))
    for rx,item in devices.items():
        matches=list(found[rx].values())
        if len(matches)==1 and not query_errors:
            item.update(status='detectado',**matches[0])
            item['notes'].append('Identidad USB verificada en la vista local; permisos UART no exigidos por este panel.')
        elif len(matches)>1:
            item['notes'].append('Serie duplicada en varios nodos: '+', '.join(sorted(found[rx])))
        elif not matches and RECEIVERS[rx] in scan.get('usb_serials',[]):
            item['notes'].append('Serie observada en USB/sysfs, pero sin nodo UART verificable en esta consulta.')
        elif not matches and scan['complete'] and not query_errors:
            item.update(status='ausente')
            item['notes'].append('Sin coincidencias en el inventario local completo; no prueba desconexión física o falta de alimentación.')
        else:item['notes'].append('No hay evidencia suficiente para resolver la identidad o afirmar ausencia.')
        item['queried_at_utc']=started
    tx=expected[-1];tx['queried_at_utc']=started
    return dict(schema='local-device-metadata-1',queried_at_utc=started,
        query_finished_at_utc=(now or (lambda:datetime.now(timezone.utc).isoformat()))(),
        view='Espacio de nombres y permisos del proceso que sirve este panel',
        inventory_complete=scan['complete'] and not query_errors,
        inventory_notes=scan['notes']+query_errors,devices=[*devices.values(),tx],
        UART_opened=False,READY_observed=False,CSI_observed=False,
        experimental_state_modified=False,replay_data_accessed=False)
