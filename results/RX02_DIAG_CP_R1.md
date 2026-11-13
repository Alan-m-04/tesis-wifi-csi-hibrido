# Validación física acotada de checkpoints RX-02 — R1

Un único intento físico autorizado alcanzó el objetivo de 240 s desde apertura,
sin suspensión, con integridad/replay, identidad/espacio y cierre de RX-02
confirmados por auditoría offline. El resultado diagnóstico es conforme;
la **calidad estricta de conexión permanece rechazada por preámbulo**.
No hubo ventanas E/S, etiquetas físicas verificadas ni datos habilitados para
calibración/entrenamiento/producción. No reemplaza C02.

## Procedencia y alcance

Base local/remota revisada: `1bb7619f798fe92721d33b25d1e6694bae420897`, rama
`feat/backend-uart-presencia-v4`. Revisión explícita
`rx02-raw-sync-control-checkpoint-2`; protocolo diagnóstico separado
`rx02_service_diagnostic_1`; grupo `RX02-DIAG-CP-R1`, partición `diagnostic_only`.
Las fuentes nuevas quedaron registradas por hash al adquirir, junto a las
18 fuentes históricas intactas. Se publican esas fuentes sin alterarlas después
de la adquisición: los auditores verifican sus hashes exactos.

El operador ejecutó desde su terminal, informó `DIAGNOSTICO_EXIT_CODE=0` y
solicitó esta consolidación. Se revisaron `authorization-consumed.json`, el
plan autorizado (SHA256 `617cf0bf21dc3084168209669bb1e82a9dd2da5f3a1549a8edd7ff0aef44f897`)
y el preflight por metadatos (SHA256
`2fc37a8deff49dcabf745d8f44cdbebbfefceaaf454bebbf8506c8b15ca66946`).
La adquisición registra una apertura/cierre, sin reintentos. La autorización
está **consumida**, aunque el plan capturado conserve el grant histórico.
La auditoría y consolidación no abrieron UART ni reprodujeron avisos.

Condiciones declaradas actuales: solo Alan, sentado quieto frente a laptop
abierta/enchufada, suspensión desactivada y otros lectores cerrados; puerta y
ventanas cerradas, sin ventilador ni terceros. Misma disposición de posiciones
y antenas que antes, TX a algo más de 2 m y RX-02 a la derecha; sin metrología
nueva. TX-01 a cargador de pared, RX-02 a USB directo; RX-01 desconectada.
Las tres placas habían estado desconectadas desde la pausa y se conectaron
TX/RX-02 para este intento; no hubo cambios de firmware/cables/puertos/antenas
declarados. Potencia TX no medida. Misma salida/volumen de PRUEBA02 según
operador, sin nueva medición de audibilidad ni declaración posterior de escucha.

## Integridad, replay y cierre

Se verifican hashes/tamaños y conjunto completo del manifiesto, plan, procedencia,
fuentes, todas las referencias contiguas de chunks y filas, eventos y resumen
reconstruidos por replay, recibo de cierre y estado específico de persistencia.
El bundle conserva 13 archivos, 7262385 bytes totales,
1.007.158 bytes brutos, 4.772.610 bytes de journal, 47.404 operaciones,
2.243 eventos y 1.283 líneas (1.190 CSI, 20 inválidas, 69 info, un arranque/reset,
dos neutrales y READY). El arranque inicial no acredita un reset posterior.
El bruto y el rechazo por preámbulo se conservan íntegros.

Disponibilidad inicial a 1,165234831 s desde apertura; sin fatal al finalizar.
Solicitud de cierre a 240,004972992 s; inicio de cierre a 240,007883569 s;
cierre confirmado a 240,010681182 s. El intervalo de 2,797613 ms entre muestras
`closing`/`closed` incluye trabajo del cierre y registro: no es latencia aislada
del driver. Lector detenido, fd liberado, una apertura y un cierre; cola cero.
El recibo durable condicionó el aviso de cierre; el reproductor devolvió éxito
aproximadamente 1,933 s después del registro `closed`. No se infiere audibilidad.
La última operación está a 241,960954715 s desde apertura: finalización/audio,
no una prolongación del servicio UART ni un hueco de recepción de esa duración.

## Cadencia y comparación descriptiva con C02

| Métrica | RX02-DIAG-CP-R1 | C02 histórica |
|---|---:|---:|
| Apertura → solicitud de cierre, s | 240.004972992 | No solicitada: suspensión |
| Apertura → inicio de cierre, s | 240.007883569 | 205.624722532 |
| Apertura → cierre confirmado, s | 240.010681182 | 205.841626668 |
| Filas CSI completas | 1190 | 1014 |
| Cadencia host entre primera/última fila, Hz | 4.971031 | 4.984683 |
| Mediana de hueco host, ms | 199.899 | 199.662 |
| p95 de hueco host, ms | 219.088 | 218.595 |
| p99 de hueco host, ms | 225.057 | 226.869 |
| Máximo de hueco host, ms | 418.888 | 1221.332 |
| Huecos host >500 ms / >1 s | 0 / 0 | 5 / 1 |
| Huecos host cero (filas agrupadas) | 0 | 14 |
| Mediana de hueco local, µs | 200000 | 200001 |
| Máximo de hueco local, µs | 405254 | 399686 |
| Cola final sin LF, bytes | 0 | 349 |
| Lecturas con bytes | 7801 | 6335 |
| Mediana retorno → decisión, ms | 2.508 | 2.303 |
| p95 retorno → decisión, ms | 13.365 | 2.833 |
| p99 retorno → decisión, ms | 13.800 | 3.959 |
| Máximo retorno → decisión, ms | 21.156 | 485.252 |
| Máximo retorno previo → inicio de próxima lectura, ms | 348.153 | 1221.263 |
| Mediana entre ticks durante servicio, ms | 5.397 | 7.792 |
| Máximo entre ticks durante servicio, ms | 26.935 | 1926.335 |

Los ids completos del nuevo ensayo son 0–1189 consecutivos, queue_drops=0 y sin
errores de continuidad del parser. Esto no demuestra ausencia de pérdidas RF:
la mediana local es 200 ms, pero existen separaciones locales de hasta
405,254 ms. La tasa host se calcula como (N−1)/(último retorno−primer retorno),
sin inflar filas, completar el extremo ni contar una cola como CSI.
El mayor hueco nuevo, id 528→529, es 418,887511 ms host y 405,254 ms locales.
El disparador C02 sigue siendo id 1008→1009: 1221,331818 ms host frente a
199,978 ms locales. Son relojes y observaciones distintos, sin sincronización RF.

C02 duró 205,841626668 s hasta cierre y suspendió por `availability_gap:RX-02`
después de la primera ventana S de 30 s; etiqueta pending/tiempo incierto,
aviso final no solicitado, vacío no iniciado y cola de 349 bytes conservada.
La nueva conexión duró 240,010681182 s hasta cierre, unas 34,169 s más,
pero no ejecutó el protocolo E/S ni su polling de comandos, demoras,
interacciones o avisos intermedios. En C02 RX-01 estaba alimentada por hub
según declaración histórica; ahora permanece desconectada. C02 declaró
continuidad eléctrica desde C01; ahora existe un intervalo de desconexión y
nuevo encendido. Mismo montaje es una declaración, no igualdad medida de RF,
carga de CPU, cachés, disco, planificación, USB o alimentación.

Para mostrar el efecto de duración se informa además un prefijo descriptivo
fijo de 180 s desde disponibilidad en cada conexión: 895/898 filas (nuevo/C02),
máximos host 418,888/391,038 ms y cero huecos >500 ms en ambos. Ese prefijo
**excluye el fallo posterior de C02** y no sustituye el análisis completo,
no es una ventana elegible, ni una selección para aprobar o calibrar.
Los percentiles usan nearest-rank del helper histórico y conservan ceros.

El máximo host y las demoras máximas son menores aquí; la mediana de cadencia
es similar y el p95/p99 retorno→decisión es mayor. No se afirma una mejora
uniforme. Retorno→decisión agrega persistencia bruta, lock, planificación y
trabajo Python; no mide solo fsync. La pausa entre reads incluye tiempos en que
no había datos disponibles. Un ensayo posterior con diferente control y duración
no identifica la causa única de C02 ni establece causalidad de checkpoints.

## Checkpoints y recursos realmente observados

El estado registra 7.801 sincronizaciones brutas del decorador y 76 checkpoints
exitosos de operaciones, última secuencia durable 47.403, 47.404 registros y
pendiente final cero; máximo pendiente **65.536 bytes**, dentro de la cota.
El hash/longitud del journal y ausencia de escritor pendiente se verifican por
`audit_checkpoint_rx02` del paquete diagnóstico. Los contadores no equivalen a
todos los fsync del proceso/kernel/dispositivo: hay persistencia histórica antes
de instalar el decorador y fsync de finalización/manifiesto/otros archivos.
No se midió la duración individual de fsync ni se ensayó corte de energía.

`service-metrics.json` conserva 38.648 pasos, máximo de `step()` 21,569259 ms,
CPU de proceso 13,363558151 s (aprox. 5,57% de un núcleo sobre 240 s) y
ru_maxrss de **26.596 KiB** (25,973 MiB) hasta el fin del servicio. El máximo
`step()` excluye sueño explícito y trabajo fuera de la llamada; no es un límite
para el ciclo entero. El pico RSS incluye importación/arranque anteriores y no
es muestreo periódico ni pico garantizado de finalización/auditoría. C02 no tiene
CPU/RSS medidos de forma equivalente. No hay medición física periódica de fds,
hilos, memoria ni latencia de cada etapa; no se extrapolan valores PTY.
Límites de eventos/líneas/operaciones y espacio permanecen íntegros.

El plazo de 240 s es objetivo de solicitud de cierre; write/fsync/driver siguen
síncronos sin garantía de máximo temporal. Ante muerte abrupta pueden perderse
o truncarse hasta 65.536 bytes de operaciones desde el último checkpoint;
sin manifiesto final íntegro y replay no se aprueba un prefijo parcial.

## Evidencia publicada y reproducción offline

- [Resumen verificable y referencias por hash](RX02_DIAG_CP_R1.resumen.json).
- [Validación de pruebas](RX02_DIAG_CP_R1.validacion.json).
- [Inventario de evidencia y preservación](RX02_DIAG_CP_R1.hashes.json).
- [Preparación y contrato](../docs/VALIDACION_FISICA_CHECKPOINTS_RX02_R1.md).

Los brutos, audio, operaciones y auditorías completas permanecen en los bundles
locales originales, sin sobrescribirlos. La publicación incluye métricas,
referencias, hashes y código; no traslada los brutos a Git.
La consolidación local nueva es
`results/local/consolidacion-diagnostico-checkpoints-rx02-r1/`.

```bash
.venv/bin/python -B tools/diagnostico_checkpoints_rx02.py \
  --audit results/local/diagnostico-checkpoints-rx02-r1
.venv/bin/python -B tools/consolidar_diagnostico_checkpoints_rx02.py \
  --output-new results/local/consolidacion-diagnostico-checkpoints-rx02-revision-NUEVA
```

La segunda salida debe ser nueva; no repetir contra una carpeta existente.
Ninguno de esos comandos abre UART. Los auditores necesitan las fuentes exactas
registradas al adquirir y los bundles locales; el resumen público no las suplanta.

El siguiente paso de campaña se limita a un borrador C03 con selección explícita
de persistencia y sin autorización, descrito en
[la revisión de campaña](../docs/REVISION_C03_CHECKPOINTS_RX02.md).
C01/C02, sus estados, particiones y autorizaciones consumidas permanecen intactos.

## Validación de los cambios publicados

450 pruebas aprobadas en 49,092 s, cero fallos, errores u omisiones: 433
históricas, 11 de entrada diagnóstica, cuatro de consolidación física y dos de
revisión de campaña. Bubblewrap con red aislada, /dev privado, repo/referencias
y tres fotos históricas montados en lectura; ningún UART físico accesible. Se
excluye test_presence_offline (calibración/inferencia fuera de alcance).
Las pruebas físicas aquí reproducen el bundle existente; no son otra captura.
38 archivos históricos protegidos y todos los archivos de los bundles nuevo
y C02 reverificados intactos antes/después de consolidar y probar.
