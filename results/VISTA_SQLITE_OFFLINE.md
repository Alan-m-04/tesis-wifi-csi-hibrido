# Vista offline de sesiones SQLite — resultado

Partiendo de **403e794**, se añadió `/sessions` y `/api/sessions` al servidor
`tools/panel_dispositivos.py`. La vista reutiliza la navegación y el estilo del
panel de dispositivos, extraído a `device_panel.css` para ambas páginas.
Se mantienen dispositivos actuales y reproducción histórica como vistas aparte.
No se modificaron esquema, importador ni capturador.

## Datos contrastados y rechazo visible

El backend usa la vista `session_receiver_summary` mediante la conexión existente
de solo lectura (`mode=ro`, `query_only=ON`). No consulta USB, no descubre
sesiones fuera de la base y no reaudita ni lee bundles al consultar SQLite.
`--sin-replay` permite arrancar sin preparar la reproducción C01/C03.

Cada consulta del piloto compara 13 campos/estados con el CSV publicado:
11 valores numéricos, estado de calidad y detalle original. Los valores
presentados, sin redondear, son:

| Sesión / receptor | Duración (s) | Muestras | Cadencia host (Hz) | Hueco máximo host (ms) | Calidad |
| --- | ---: | ---: | ---: | ---: | --- |
| RX02-DIAG-VISOR-240S-R1 / RX-02 | 240,005564743 | 1.192 | 4,9792637522332885 | 614,782902 | **RECHAZADA · PREÁMBULO** |

El contrato DOM comprueba el aviso superior **CALIDAD ESTRICTA RECHAZADA POR
PREÁMBULO**, la repetición del rechazo en la tabla y los motivos
`format:RX-02` ×20 / `preamble_anomaly:RX-02` ×1. Integridad, replay, cierre y
diagnóstico conformes permanecen separados; no se utiliza un estado global
verde que sustituya al rechazo. SQLite y CSV conservan sus hashes originales.
Se comprobaron 4.512 archivos anteriores protegidos sin cambios; las cinco
modificaciones deliberadas de fuentes/documentación se enumeran en el resultado
estructurado. La evidencia R5 y los intentos históricos permanecen intactos.

## Pruebas realizadas

**60 pruebas Python aprobadas**, cero fallos/errores/omisiones; incluyen 11
pruebas nuevas de la vista y regresión del panel, prototipo SQLite, replay y
visor. **3 contratos Node aprobados**: sesiones, dispositivos y replay.

Se verificaron la consulta sin abrir UART ni ejecutar descubrimiento USB,
coincidencia exacta con el CSV, identidad única del piloto, columnas/valores
inválidos, discrepancias de datos/calidad, base ausente sin creación, base vacía,
acceso solo a rutas fijas y rechazo de POST/hosts ajenos. La interfaz elimina
resultados anteriores ante errores, rechaza respuestas incoherentes, limita
consultas a 12 s y no permite clics concurrentes. Los motivos se renderizan
como texto. También conserva sesiones/receptores en filas distintas y valores
no disponibles sin inventar cadencias o calidad.

El enlace a `127.0.0.1` y el HTTP se verificaron con dobles/streams en memoria.
El intento real de crear un socket recibió `EPERM`; Firefox no completó su
arranque en el entorno restringido. No se generó screenshot ni se afirma
verificación visual o HTTP real desde el agente. Bubblewrap tampoco pudo
crear namespaces; las pruebas Python se ejecutaron directamente con la
barrera de auditoría `csi_live_observer.guard` para UART y reserva.

La instantánea HTML local preparada para QA contiene un payload guardado;
no reemplaza la consulta HTTP ni representa datos actuales. La revisión
visual en el navegador del operador sigue pendiente.

## Abrir y usar en la MIPYME

```bash
cd /home/alan-monar/tesis-wifi-csi-hibrido
.venv/bin/python -B tools/panel_dispositivos.py --sin-replay
```

Visitar **http://127.0.0.1:8766/sessions** y pulsar **Consultar sesiones** para
otra instantánea. El servicio se detiene con Ctrl-C; no está expuesto a la red
del establecimiento. Sin `--sin-replay`, se conserva además la preparación
habitual de C01/C03 en el tablero.

La vista permite revisar registros, duración y continuidad por receptor y
detectar rechazos que deban investigarse antes de usar datos en etapas
posteriores. Aporta trazabilidad técnica para supervisar el sistema en una
MIPYME; no determina ocupación actual, personas, pérdidas RF, causalidad de
fallos o seguridad del local. El diagnóstico histórico sigue sin habilitar
calibración, entrenamiento o producción.

[Guía completa](../docs/VISTA_SQLITE_OFFLINE.md) y
[resultado estructurado con hashes](VISTA_SQLITE_OFFLINE.validacion.json).
Evidencia local: `results/local/vista-sqlite-r1/`. Originales e intentos
anteriores se conservaron; **C04–C06 reservadas y R5-N01 pendiente del ensayo
interactivo**. No se abrió UART ni adquirieron datos nuevos.
