# Sesiones SQLite en el tablero local

## Abrir la vista

Desde la raíz del repositorio, con las ESP desconectadas:

```bash
cd /home/alan-monar/tesis-wifi-csi-hibrido
.venv/bin/python -B tools/panel_dispositivos.py --sin-replay
```

Mantener esa terminal abierta y visitar **http://127.0.0.1:8766/sessions**.
Ctrl-C detiene el servicio. `--port 8767` permite otro puerto, siempre local.
La navegación **Sesiones · SQLite offline** también está en la página de
dispositivos. Se reutilizan el servidor, los controles y la hoja de estilo del
tablero existente; no se crea otro servidor o dashboard independiente.

`--sin-replay` evita preparar/leer los bundles C01/C03 al arrancar. En ese modo
el enlace `/replay` responde que la reproducción no está preparada. Para mantener
también la reproducción histórica, ejecutar el comando existente sin esa opción:

```bash
.venv/bin/python -B tools/panel_dispositivos.py
```

El backend utiliza `results/local/base-datos-csi/piloto.sqlite3`, creado en el
commit `403e794`. Opcionalmente, `--database RUTA` selecciona otra base derivada
dentro de `results/local/base-datos-csi/`. La vista **no crea una base ausente ni
importa datos**. Si falta, seguir por separado los comandos de preparación del
[capítulo 3](CAPITULO_3_BASE_DATOS_CSI.md), conservando los originales.
Abrir `src/sqlite_sessions.html` directamente como archivo no sustituye al backend.

## Qué muestra

La consulta se realiza al abrir la vista y al pulsar **Consultar sesiones**.
Es una instantánea de registros históricos con hora UTC de consulta, no una
observación actual de las ESP. No hay actualización automática ni consulta USB
desde `/sessions` o `/api/sessions`.

Cada fila corresponde a **una sesión y un receptor**, con estas columnas:

| Indicador | Interpretación |
| --- | --- |
| Duración apertura → cierre | Segundos hasta el cierre confirmado del receptor; no la espera posterior del journal. |
| Muestras CSI | Número de filas completas guardadas; no número de personas o paquetes RF. |
| Cadencia host | `(N−1)/(última−primera)` entre retornos host; no frecuencia RF uniforme. |
| Hueco máximo host | Mayor intervalo entre filas consecutivas, sin bordes de apertura/cierre. No determina por sí solo pérdidas o su causa. |
| Calidad estricta | Resultado original de la conexión completa. No se sustituye por integridad, replay o cierre. |

Los números se presentan con coma decimal y sin redondear los valores JSON
recibidos. La misma página explica las fórmulas y muestra por separado las
validaciones y los motivos originales con sus conteos. Una cadencia no
definible se muestra **No disponible**; una calidad ausente, **NO REGISTRADA**.

En el piloto se muestran **1.192 muestras**, **240,005564743 s**, cadencia host
**4,9792637522332885 Hz** y hueco máximo **614,782902 ms**. El aviso superior dice:

> CALIDAD ESTRICTA RECHAZADA POR PREÁMBULO.

La tabla repite **RECHAZADA · PREÁMBULO**, con texto y color. El detalle conserva
`format:RX-02` ×20 y `preamble_anomaly:RX-02` ×1. Integridad/replay verificados,
cierre confirmado y diagnóstico conforme aparecen aparte. Esos resultados
no eliminan el rechazo ni habilitan un detector, calibración o entrenamiento.

## Consulta de solo lectura y contraste con CSV

`src/csi_sqlite_view.py` reutiliza `csi_sqlite.database` y
`session_receiver_summary`, sin modificar el esquema del commit `403e794`.
La conexión usa `mode=ro` y `PRAGMA query_only=ON`; el endpoint no recibe SQL,
rutas de archivos, órdenes de importación o parámetros de adquisición.
Solo lee la base derivada y el CSV agregado del piloto.

Cada consulta del piloto contrasta 11 indicadores/estados numéricos, además
del estado de calidad y su detalle JSON, con el
[CSV conservado](../results/BASE_DATOS_CSI_PILOTO/RX02-DIAG-VISOR-240S-R1__RX-02.csv).
El contraste utiliza los valores completos, antes de presentarlos en pantalla.
Si no coinciden, el backend devuelve HTTP 503 y no publica un contraste conforme.
Una sesión distinta o una base vacía no se anuncia como piloto verificado.

Ante base ausente, versión inválida, CSV incompleto, discrepancia, error de
conexión o vencimiento de 12 s, la interfaz borra las filas anteriores y muestra
**Sin datos verificables**. Ese vencimiento solo limita la consulta del tablero;
no interviene en los plazos de adquisición. No se permite lanzar consultas
concurrentes desde el botón. Los motivos se insertan como texto, sin interpretar
HTML de la base.

Las rutas son `/sessions`, `/sessions.mjs`, `/panel.css` y `/api/sessions`.
El servidor conserva el enlace exclusivo a `127.0.0.1`, la comprobación de Host,
la política CSP y `Cache-Control: no-store`. No sirve el archivo SQLite, el CSV,
el repositorio o los brutos mediante rutas genéricas. POST no está permitido.

## Aporte a la supervisión en una MIPYME

La persona responsable puede revisar, por sesión y receptor, si existe un
registro, cuánto tiempo cubre, cuántas muestras produjo y si hubo huecos o
rechazos que requieran atención técnica. Esto aporta trazabilidad al revisar
el funcionamiento del sistema y evita tratar como aprobada una captura cuyo
archivo es íntegro pero cuya calidad fue rechazada.

El tablero permite decidir qué evidencia revisar antes de alimentar etapas
posteriores. Por ejemplo, un rechazo por preámbulo dirige la revisión al arranque
y al formato registrado; un hueco grande dirige la revisión a continuidad y
sus relojes. No atribuye una causa eléctrica, USB o RF sin diagnóstico adicional.
El piloto sigue siendo diagnóstico histórico: no mide ocupación actual,
productividad, presencia validada o seguridad del establecimiento, ni demuestra
disponibilidad operativa continua en una MIPYME.

## Pruebas y límite de verificación visual

Pasaron **60 pruebas Python y 3 contratos Node**, sin fallos ni omisiones.
Incluyen 11 pruebas nuevas del backend/vista, coincidencia con el CSV, errores
sin datos antiguos, solo lectura y regresión del panel, SQLite y reproducción.
El contrato DOM comprueba los valores completos, el aviso de preámbulo, los
conteos de motivos, la separación de validaciones, múltiples filas, estado
vacío/desconocido y el vencimiento de consultas.

```bash
PYTHONPATH=src:tools:tests .venv/bin/python -B -m unittest \
  test_sqlite_sessions_view test_device_panel test_csi_sqlite \
  test_session_offline test_rx02_live_view -v
.tools/node-v22.20.0/bin/node --test tests/js/sqlite_sessions.test.mjs \
  tests/js/device_panel.test.mjs tests/js/replay_demo.test.mjs
```

El entorno del agente rechazó crear sockets localhost con `EPERM`, por lo que
HTTP se ensayó con streams en memoria. Firefox tampoco pudo completar el
arranque con su sandbox; no se obtuvo captura ni validación visual en navegador.
La instantánea `results/local/vista-sqlite-r1/instantanea-qa.html` se conserva
solo como preparación de QA, no como una consulta actual de la base.
Bubblewrap no pudo crear namespaces: se ejecutaron los tests directamente
con barrera de auditoría Python para UART y reserva, sin atribuirles aislamiento
Bubblewrap. La revisión visual en el navegador del operador queda pendiente.

Los [resultados y hashes](../results/VISTA_SQLITE_OFFLINE.md) documentan la
conservación de SQLite, CSV, originales e intentos anteriores. **C04–C06 siguen
reservadas y R5-N01 sigue pendiente del ensayo interactivo**. Este trabajo no
abrió UART ni adquirió, calibró o entrenó con nuevos datos.
