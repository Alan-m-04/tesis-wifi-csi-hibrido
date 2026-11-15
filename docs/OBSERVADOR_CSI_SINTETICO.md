# CSI provisional ejecutable sin ESP

Desde la raíz del repositorio:

```bash
.venv/bin/python -B tools/demo_csi_vivo.py --seconds 45
```

Abrir **http://127.0.0.1:8767/**. `--port 8768` cambia el puerto; Ctrl-C termina
la demo. El productor espera un segundo, emite I/Q inventado, pausa entre los
segundos 5 y 9 y reanuda hasta completar la duración. El servidor permanece
abierto después del fin para inspeccionar el estado detenido.

Sin servidor ni navegador:

```bash
.venv/bin/python -B tools/demo_csi_vivo.py --headless --seconds 12
```

No requiere ESP, firmware, Internet o dependencias nuevas. Cada ejecución crea
`results/local/demo-csi-sintetico-…/`; `--output-new results/local/NOMBRE-NUEVO`
fija una ruta nueva. Contiene `original/` (journal y bruto), `view/latest.json`
(una instantánea reemplazable), `producer-result.json` (hashes/auditoría) y
`demo-report.json` (estados y salida de procesos).

Para reiniciar solo la visualización de un productor sintético existente:

```bash
.venv/bin/python -B tools/demo_csi_vivo.py --observe-synthetic results/local/RUTA-DE-LA-DEMO/original
```

Esto no reinicia el productor ni rejuvenece sus muestras. Solo se admiten fixtures
de esta demo y del mismo boot host; fuentes físicas/históricas y C04–C06 se rechazan.

## Procesos y reutilización

El productor finito usa `OwnedPty`, `Rx02Journal` y `V4Journal.command` existentes.
No solicita ventanas E/S ni crea declaraciones experimentales. El contrato de la
fixture conserva el ID `RX02-C01`: es un registro **sintético en otra carpeta**,
no continuación ni reemplazo de C01 física. Su procedencia dice `synthetic_fixture`
y transporte físico deshabilitado. Los mensajes READY inventados no verifican ESP.

Otro proceso observa journal/bruto en **solo lectura**, comprobando secuencia,
offsets y hashes. Reutiliza `_StartupSequenceFramer`, el parser/validador,
`frame_from_reference`, `documented_ht20_layout`, `canonical_block` y `row_mean`.
Conserva máscaras y referencias; no ejecuta efectos de UART/audio o elegibilidad
experimental. La auditoría nativa completa se hace al terminar la fixture.

Un tercer proceso sirve solo HTML/JS e instantáneas en **127.0.0.1**. El navegador
no lee el journal ni da órdenes al productor. `csi_charts.mjs` comparte las funciones
de mapa de calor y RSSI extraídas del reproductor, con los helpers originales.
Los datos/escalas históricos son idénticos; su artefacto vigente es
`results/local/demo-offline-c01-c03-shared-live-r1/index.html`.

El visor lleva **SIMULADO · SIN ESP · CSI PROVISIONAL · SIN DETECTOR CALIBRADO**.
Los enlaces a metadatos actuales y reproducción histórica son vistas distintas.
Para usarlos, iniciar en otra terminal el servidor existente:
`.venv/bin/python -B tools/panel_dispositivos.py` (puerto 8766). No es necesario
para que funcione la demo sintética del puerto 8767.
La futura adquisición física está deshabilitada. No hay botones/endpoints de
captura ni decisiones de presencia, personas o coordenadas.

## Estados y pérdidas visuales

| Estado | Presentación |
|---|---|
| Esperando | Todavía no hay fila CSI válida; sin traza. |
| Recibiendo | Última fila válida con menos de 2 s de edad host; LLTF52/RSSI originales del fixture. |
| Datos antiguos | Silencio, vista en pausa o muestra vieja: se borran las trazas activas y se conserva la hora de última muestra. No prueba cierre ni ausencia de personas. |
| Detenido | Error/parada del observador u operación final del productor sintético; motivo explícito, nunca cierre físico verificado. |

La edad sale de `returned_ns`, no de la llegada/publicación de la instantánea.
Backend y navegador la actualizan: un observador muerto, petición bloqueada o
reinicio no convierte datos viejos en actuales. Muerte abrupta del productor sin
operación final significa datos antiguos, no un cierre inventado.

Límites del **visor**, sin cambiar criterios: 300 filas/30 s; 64 operaciones por
sondeo; 16 KiB por operación/chunk; framer acotado; instantánea máximo 2 MiB.
HTTP tiene un handler, cola de cuatro solicitudes y timeout de socket de 1 s;
el cliente, una petición y timeout de 2 s. Refresco propuesto: 250 ms. El productor
de demo admite máximo 120 s y 50 filas nominales/s, sin suponer frecuencia RF.

Se distinguen filas expulsadas del buffer, actualizaciones omitidas por el
navegador y líneas inválidas. Nada elimina bytes del original. Pausar/cerrar el
navegador no pausa productor/observador. Las señales de parada usan flags de un
byte sin mutex; interrumpir al observador no deja candados bloqueados. El supervisor
puede reiniciar solo ese observador hasta dos veces, nunca el productor/conexión.

## Verificación y límites

Pruebas de JSONL/CSI partidos, bruto incompleto, hash erróneo, truncado/rotación,
secuencias, límites, muestras inválidas, edad al reiniciar e interrupciones.
Procesos reales con PTY propios verificaron consumidor lento, muerte y reinicio
del observador, interrupción limpia/brusca del productor y registro original
íntegro. HTTP en memoria verifica desconexión del navegador; DOM/canvas simulado
verifica borrado de trazas, pausa, timeout y recuperación. No son pruebas visuales
de navegador ni medidas de exactitud física. La verificación final seleccionada
aprobó 37 casos Python y los arneses JS del visor y de la reproducción histórica.

La demo headless de 12 s mostró los cuatro estados y recuperación, preservó todos
los bytes enviados y pasó integridad/replay nativos. Una prueba inicial quedó
bloqueada al terminar un observador que usaba eventos compartidos; se interrumpió
y se corrigió con flags sin mutex. Los ensayos posteriores pasaron. Evidencia:
`results/local/implementacion-live-r1/`.

Para una adquisición autorizada falta revisar/habilitar el adaptador físico
solo de lectura y vincular plan, procedencia, receptor, boot y reloj originales.
Hoy se rechaza esa fuente. La vista seguirá siendo provisional: los checkpoints
no publican un marcador durable por operación; el cierre/auditoría aprueban el
bundle final, no este visor. La fixture no verifica disponibilidad, criterios E/S
completos o comportamiento eléctrico de ESP.

El operador confirmó parcialmente que el visor sintético abre y muestra LLTF52,
RSSI y huecos sin rellenar. No se da por terminada la comprobación de todos los
controles, estados, reconexiones o latencia de navegador. Declaración conservada
en `results/local/mediciones-live-pty-r1/comprobacion-parcial-operador.json`;
la hora registrada es la de registro, no una hora de prueba inferida.

La medición con el capturador completo y PTY propio se reproduce así:

```bash
.venv/bin/python -B tools/medir_observador_pty.py --output-new results/local/medicion-pty-NUEVA --duration 8 --repetitions 2
```

Es un laboratorio finito sin servidor ni ESP. Reutiliza `rx02_service_lab.run_case`
y `CheckpointRx02Session`, con el mismo productor inventado a 5 Hz, fragmentos
separados 20 ms y servicio a 5 ms. No solicita ventanas ni declaraciones E/S.
Compara sin observador, observador de 300 filas/consumidor a 250 ms y observador
de ocho filas/consumidor lento a 2,5 s; alterna el orden en la segunda repetición.
El consumidor lento tiene un buffer reducido explícito para provocar expulsiones
de visualización; no representa otra configuración del capturador.

Ese capturador no incorpora boot/dominio de reloj en su procedencia nativa.
Solo este laboratorio atestigua externamente el `time.monotonic_ns` que inyectó,
ligando ruta, hashes de plan/procedencia y boot en `synthetic-clock-binding.json`.
No modifica los originales. El observador comprueba además transporte sintético
y evidencia sintética; la constancia no permite fuentes físicas. No es una opción
del CLI del visor. Las fuentes físicas siguen rechazadas.

La revisión encontró y corrigió el rechazo erróneo de `storage_check`, operación
de control emitida por el capturador; las operaciones desconocidas siguen
deteniendo solo el observador. No se cambió el capturador, checkpoints o criterios.
Los informes conservan CPU/RSS, intervalos del servicio, tiempos de parser y
publicación, cobertura del consumidor, backlog, descartes y auditoría nativa.
La latencia empieza en la lectura host y termina en la instantánea/consumidor
local: no incluye RF, firmware, TCP, render ni audibilidad.

Resultados y límites: [mediciones e integración PTY](MEDICIONES_OBSERVADOR_PTY.md).
Procesos separados evitan esperas/acks del visor hacia el capturador, pero no la
competencia de CPU/disco del sistema. Falta carga prolongada/representativa,
navegador real y adaptación física autorizada. Presencia y localización siguen
pendientes de datos independientes, calibración y evaluación.
