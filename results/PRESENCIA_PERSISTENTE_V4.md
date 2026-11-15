# Preparación de adquisición persistente v4 — evidencia offline

Base exacta: `51246df4f288ede695b81f8eca8336820e6cb126`. Rama `feat/campana-presencia-persistente-v4`. Se escribió primero el [contrato](../docs/PROTOCOLO_PRESENCIA_PERSISTENTE_V4.md) y después se implementaron máquina de estados, journal/auditor, ciclo de vida PTY y avisos de laptop. [Plan concreto para revisión](../docs/PLAN_REVISION_CAMPAÑA_PERSISTENTE_V4.md). No se modifican firmware, capturadores/protocolos v1/v2/v3, detector o resultados físicos anteriores.

## Qué queda implementado

Una sola apertura por RX durante toda la conexión sintética; READY inicial estricto y tres filas continuas, plazo de 10 s, después vigilancia continua de frescura de 1 s. Antes de cada slot solicitado por el operador se respeta demora de salida de 60 s, aviso inicial y otros 30 s desde su confirmación de software; gate nuevo con otras tres filas por RX. La decisión prospectiva fija T0 y T1=T0+30 s; no se desplazan ante fallo. Reset, discontinuidad, pérdida de disponibilidad, error/interrupción, cobertura piloto insuficiente o etiqueta incierta suspenden, sin reintentar ni escoger sustitutas.

Los brutos guardan todos los bytes leídos desde cada apertura, también entre slots. Journal y líneas fijan offsets, hashes y primera/última lectura. Las ventanas referencian estos mismos brutos, sin concatenar sesiones o recortar archivos. Al terminar una ventana la conexión sigue abierta; únicamente el cierre final usa 250 ms/65536 bytes para completar una línea pendiente. Se conservan colas y errores. Disponibilidad, calidades de conexión/ventana/cobertura y etiquetas declaradas quedan visibles por separado.

El fin de ventana con conexión abierta, el fallo y ambos cierres confirmados tienen avisos diferentes. Se implementa audio opcional de laptop en un hilo separado del lector. El recibo requiere resultados efectivos de ambos cierres de PTY y comprobación `fstat`/`EBADF`, con bucle lector detenido; se persiste antes de solicitar el sonido de cierre y referencia hashes de brutos y prefijo de operaciones. Un temporizador no acredita cierre. Los avisos grabados en las demos son simulados, y los WAV exportados **no se han reproducido ni oído**.

Cada bundle nuevo incluye plan, procedencia con hashes del código/perfil, brutos por RX, operaciones, eventos derivados, resumen, recibo y manifiesto. El auditor verifica todos los archivos y reconstruye desde operaciones/bytes las decisiones y resultados; detecta un resumen, hash de lectura o recibo falsos incluso si se rehashea su archivo en el manifiesto. Esto es integridad/reproducibilidad de evidencia registrada, no prueba criptográfica de verdad física o etiqueta humana.

## Verificaciones ejecutadas

**128 pruebas Python aprobadas: 38 nuevas y 90 regresiones, sin errores, fallos u omisiones.** Son pruebas offline ejecutadas directamente en el entorno restringido disponible, con memoria/PTY propios y archivos históricos de regresión de solo lectura. No se atribuye aislamiento Bubblewrap a esas ejecuciones.

Las nuevas cubren dos ventanas por conexión con una sola pareja de READY, tres filas nuevas por gate, demora medida desde aviso real de software, T0 inclusivo/T1 exclusivo, línea que cruza inicio, timestamps repetidos, reset en el mismo chunk que la tercera fila, reset/discontinuidad entre ventanas, vuelta uint32, callback/reloj/descartes, pérdida de frescura, lector fallido, interrupción/KeyboardInterrupt, etiqueta pendiente/incierta, cobertura escasa, solicitud solapada/sustitutiva, cierre de segunda apertura fallida, fallo de un cierre, ambos cierres intentados aun con almacenamiento fallido, cola/LF/presupuestos finales, replay/alteraciones y audio asíncrono simulado.

Las 90 regresiones corresponden a `test_availability_window`, `test_controlled_v2`, `test_controlled_v3`, `test_capture_preparation`, `test_capture_boundaries` y `test_boundary_diagnostic`. Se mantienen semántica v3, paradas anteriores y rechazos históricos. No son una ejecución de toda la suite ni de firmware.

Evidencia persistida en `results/local/campana-persistente-v4/`, ignorada por Git:

- `ensayo-dos-ventanas-validado/`: dos ventanas de 30 s **lógicos**, con reloj virtual por pasos y PTY reales del proceso. Verificación de ambas calidades, cobertura, declaraciones sintéticas, una apertura/cierre por RX y replay de todo el bundle.
- `ensayo-nominal-definitivo/`: una ventana nominal de 30 s con `SyntheticClock(speed=1)`, sin aceleración, precedida por la demora real de salida y seguida del margen final/cierres. La fuente es explícitamente sintética de objetivo 10 Hz; no se extrapola a las ~5 filas/s físicas ni se afirma RF continua. Las métricas observadas y hashes quedan en el [registro de validación](PRESENCIA_PERSISTENTE_V4.validacion.json). Sus fuentes se fijaron al iniciar el ensayo; después solo se hizo idempotente el cleanup de descriptores PTY, conservando la fuente anterior local y añadiendo una prueba contra doble cierre/reutilización de fd. Máquina de estados, reloj y fronteras permanecieron iguales; el ensayo por pasos y las 38 pruebas finales verifican el cleanup definitivo.
- `operador-aborto-validado/`: práctica CLI local con `abort`; conserva interrupción, cero ventanas y ambos resultados de cierre, sin audio ni etiquetas inventadas.
- `sonidos-prueba/`: cuatro WAV distintos, exportados sin reproducción. Prueba de reproductor con retorno fallido simulado; audibilidad sin comprobar.
- `pruebas-verificadas.log`, `regresion-v1-v2-v3.log`, `bubblewrap.log`: resultados y fallo explícito de aislamiento.

El primer ensayo de desarrollo acelerado conservó un rechazo `availability_lost:RX-01`: la aceleración magnifica pausas del host/almacenamiento. No se relajó 1 s para aprobarlo, se reabrió automáticamente ni se sustituyó su ventana. Las pruebas positivas por pasos separan determinismo del contrato de latencia real; el ensayo nominal comprueba aparte el bucle sin acelerar. Los intentos/logs de desarrollo, incluidos fallos de pruebas corregidos antes de esta entrega, permanecen en carpetas separadas.

`./tools/test_presence_v4.sh` fue intentado y **falló con código 1 antes de ejecutar pruebas**: Bubblewrap no puede crear namespaces en este entorno. El wrapper nuevo llama al aislador existente y no tiene fallback. No se afirma aislamiento de red/dispositivos por Bubblewrap que no se ejecutó; no se modificaron permisos, kernel o configuración para eludir el fallo.

Reproducción directa de la revisión offline, distinta del wrapper de aislamiento:

```sh
.venv/bin/python -B -m unittest discover -s tests -p test_persistent_presence_v4.py -v
PYTHONPATH=src:tests .venv/bin/python -B -m unittest \
  test_availability_window test_controlled_v2 test_controlled_v3 \
  test_capture_preparation test_capture_boundaries test_boundary_diagnostic -v
```

## Límites y pasos que requieren revisión posterior

El backend físico **no está implementado ni habilitado**; la preparación por defecto no abre dispositivos y la demo/práctica solo crean PTY propios. Falta promover/revisar transporte UART con identidad USB, exclusividad, apertura sin flush/DTR/RTS, almacenamiento y cierre reales. Persistir resuelve no pedir READY por cada slot, pero el primer READY fresco al abrir y su repetibilidad entre visitas siguen sin demostrar. No se reconecta ni resetea para obtenerlo.

Faltan comprobar sin UART la audibilidad/discriminación en exterior/silla/recorrido, modo de energía/sonido de laptop, tiempos reales de salida y posiciones/puerta/montaje sin mover equipos. Falta revisar los criterios prospectivos de cobertura y las particiones por conexión completa. Dos conexiones propuestas no prueban suficiencia estadística. La etiqueta es declaración con incertidumbre temporal desconocida, no verdad observada ni inferencia CSI.

No se abrió UART físico, adquirieron mediciones, calibró/inferió el detector con datos físicos, modificó firmware o creó autorización física. La futura campaña requiere revisión del plan, transporte y avisos, y autorización nueva explícita. Este resultado prepara el trabajo; no acredita una campaña ejecutada o presencia validada.
