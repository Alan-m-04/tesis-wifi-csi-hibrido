# CONT-DUAL-01: diagnóstico offline r1 del único intento físico

Analizado desde `c243406af0052c08eafd0e130533311554b0732e`. Bundle original:
`results/local/continuidad-dual-01-60s-intento-unico/`. El auditor reproduce
integridad/replay correctos, 60 s nominales completados y ambos cierres. La
autorización `CONT-DUAL-01-60S-UNICO` está consumida, sin reintento permitido.
**171 frente a 296 son filas CSI completas válidas; no son conteos de paquetes
RF enviados/perdidos.** El resultado sigue sin aprobación de calidad, ventanas,
etiquetas, calibración o entrenamiento. No se abrió UART durante este análisis.

## Evidencia y alcance temporal

[Resumen numérico versionado](DIAGNOSTICO_CONTINUIDAD_DUAL_01_R1.json), con hashes
de los nueve originales, distribuciones, perfil, colas y referencias por incidente.
El artefacto local completo es
`results/local/diagnostico-continuidad-dual-01-r1/forense-r1.json`.
El módulo nuevo `continuity_diagnostics.py` llama al auditor original en modo
lectura; no cambia el productor, validador, políticas, firmware ni watchdog v4.
Los ocho hashes de fuentes registrados durante adquisición coinciden con los
archivos actuales; el commit declarado durante adquisición tenía árbol limpio.

Inicio común MONOTONIC: **178535024151861 ns**; deadline:
**178595024151861 ns**. Duración nominal: 60 s; duración real hasta terminar
lectores: **60,008476056 s**. Toda fila válida cae dentro del intervalo común.
También se conserva el arranque previo: RX-01 tiene dos lecturas, 526 bytes,
anteriores al inicio común; RX-02 no tiene lecturas anteriores. Las métricas de
lecturas/servicio de las tablas usan el intervalo común, salvo donde dice conexión.
No se recortan ni se reinterpretan los originales para aprobarlos.

Los intervalos entre filas usan el retorno de la lectura que aporta LF. El
timestamp local es uint32 en microsegundos, con diferencias módulo 2^32, por RX;
los relojes locales de ambos RX no están sincronizados. Cada fila guarda línea,
offsets, hash, ledger y primera/última lectura. Las distribuciones no rellenan
datos: mediana convencional, p95/p99 por rango más próximo `ceil(p*n)`.
Se informan aparte los extremos inicial/final, que no entran en los n−1 huecos.

## Diferencia persistente durante los 60 s

| Intervalo común, s | RX-01 válidas | RX-02 válidas | Diferencia |
|---|---:|---:|---:|
| [0,10) | 22 | 47 | 25 |
| [10,20) | 31 | 50 | 19 |
| [20,30) | 32 | 50 | 18 |
| [30,40) | 28 | 50 | 22 |
| [40,50) | 27 | 50 | 23 |
| [50,60) | 31 | 49 | 18 |
| Total | **171** | **296** | **125** |

Tasas descriptivas sobre 60 s: 2,85 y 4,933333 filas/s. Primera fila completa
a 0,843502325/0,627064339 s; última a 59,809508269/59,806973928 s. Edad de la
última fila en el deadline: 190,491731/193,026072 ms. La diferencia no procede
de una finalización temprana de RX-01 ni se concentra en las tres incidencias.

| Huecos entre filas, ms | n | Media | Mediana | p95 | p99 | Máximo | >1000 ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| RX-01 host | 170 | 346,859 | 212,824 | 797,810 | 1215,565 | 1395,581 | 3 |
| RX-01 local | 170 | 347,058 | 200,294 | 800,098 | 1200,083 | 1398,388 | 4 |
| RX-02 host | 295 | 200,610 | 200,542 | 219,029 | 231,330 | 398,945 | 0 |
| RX-02 local | 295 | 200,678 | 200,000 | 202,239 | 204,514 | 400,149 | 0 |

Los intervalos locales de RX-01 se agrupan alrededor de 200/400/600/800/1000/
1200/1400 ms con **96/45/15/10/1/2/1** casos. RX-02: **294/1** alrededor de
200/400 ms. Residual máximo al múltiplo de 200 ms: 5,698/5,594 ms. Esta referencia
describe periodicidad; **no estima pérdidas RF**. La fuente TX fija 5 Hz y espera
200 ms después de cada `esp_now_send`, sin probar su cadencia efectiva durante
este intento. No hay traza TX o secuencia TX en el CSV que permita verificarlo.

En RX-01, 74 de 170 intervalos locales rondan 400 ms o más. La suma local entre
primera/última fila es 58,999827 s, frente a 59,199902 s de RX-02. El déficit de
filas acompaña separaciones mayores también en el reloj local. Hay un cuarto
intervalo local >1 s (`id 21→22`: 1000,001 ms), cuyo hueco host es 997,565142 ms;
por eso el diagnóstico registra tres incidencias host y no cuatro. No se cambia
el criterio estricto >1 s ni el reloj/umbral de v4.

## Callbacks, descartes, perfil y bytes

Ids completos: **0…170** en RX-01, **0…295** en RX-02, todos consecutivos; no hay
salto ni reinicio entre filas completas. `queue_drops=0` en todas ellas. No se
observa discontinuidad local según la gramática existente (delta positivo y
≤10 s); esto no convierte los huecos largos en calidad aprobada.

La fuente de ambos RX incrementa `callback_id` después de filtrar `info`, buffer
y MAC. Incrementa `queue_drops` por longitud 0/>1024 o fallo de `xQueueSend`; el
writer copia `rx_ctrl.timestamp` al CSV. Son contadores locales, no secuencia TX
ni contador de toda recepción RF. Cero descartes no cubre callbacks no generados,
rechazados antes del id, pérdidas anteriores al driver o posteriores al último
registro leído. Las fuentes inspeccionadas no atestiguan por sí solas el binario
instalado (`installed_firmware_attested=false`). Ambas fuentes desactivan ahorro
Wi-Fi; no respalda atribuir la asimetría a un ahorro configurado diferente.
Referencias inspeccionadas: [RX-01](../firmware/csi_recv/main/app_main.c),
[RX-02](../firmware/csi_recv_02/main/app_main.c) y
[TX-01](../firmware/csi_send/main/app_main.c), con hashes en el JSON nuevo.

Todas las filas completas cumplen el perfil original: MAC `1a:00:00:00:00:00`,
canal 11, bandwidth=0/HT20, rx_state=0, len=256, first_word_invalid=0, sig_mode=1,
mcs=0 y stbc=0. No se ha usado amplitud CSI para ajustar un detector.
En el tramo posterior a la primera fila CSI no aparece ninguna línea CSI completa
rechazada por formato/perfil que explique el déficit de 125 filas; las líneas
inválidas observadas pertenecen al arranque, y las colas finales se cuentan aparte.

| Evidencia | RX-01 | RX-02 |
|---|---:|---:|
| Bytes de conexión íntegros | 150310 | 255433 |
| Bytes que pertenecen a filas válidas | 144819 | 249867 |
| Otros bytes completos, incluido arranque | 4851 | 4926 |
| Cola final sin LF | 640 | 640 |
| Lecturas conexión / intervalo común | 964 / 962 | 1844 / 1844 |
| Bytes devueltos en intervalo común | 149784 | 255433 |
| Mediana / máximo de bloque leído, bytes | 128 / 384 | 128 / 384 |

Los bloques son particiones de lectura, no paquetes de firmware o RF. Las filas
válidas promedian 846,895/844,145 bytes: la diferencia de 105123 bytes brutos
se descompone exactamente en 105048 bytes de filas y 75 bytes de otros textos.
El auditor cubre cada bruto por lecturas sin omisiones o duplicados. Esto
demuestra preservación de lo leído, no ausencia de pérdida anterior a `read()`.

En el arranque se conservan 21 líneas inválidas por RX, residuos iniciales,
marcadores ROM/POWERON, READY y mensajes de inicialización. No hay reset/error
posterior al primer CSI completo; RX-02 tiene READY/retorno de app_main después
de su primera fila, orden compatible con el writer creado antes del log. Los
marcadores de arranque leídos no identifican por sí solos su causa ni excluyen
bytes previamente encolados. No se normalizan para declarar conforme la conexión.

Colas: RX-01 `[149670,150310)`, SHA256
`b6ce986991441695938b6012d70273798b63c88d8dc76614650aa328bf2c49d0`;
RX-02 `[254793,255433)`, SHA256
`397d3b1aa728f4c7de78f5a213a2eca13ab0abbaee368049686703e1c2008e72`.
Sus cabeceras literales dicen id **171/296**, timestamp local
**59949062/59934886 µs**, queue_drops=0; ninguna tiene LF ni payload completo
validado. **No son filas 172/297, no se reparan ni cuentan**. El primer fragmento
se lee hacia 59,942 s; ambas colas quedan intactas al cierre nominal.

## Servicio, lectura, persistencia y reloj del host

| Métrica del intervalo común, ms | RX-01 mediana / p99 / máximo | RX-02 mediana / p99 / máximo |
|---|---:|---:|
| Servicio del lector, fronteras incluidas | 13,053 / 23,620 / 34,110 | 12,960 / 23,148 / 42,049 |
| Entre retornos con bytes | 16,134 / 731,831 / 1324,366 | 14,565 / 144,978 / 334,086 |
| Duración de read no bloqueante | 0,058 / 0,246 / 0,418 | 0,059 / 0,247 / 0,320 |
| Espera retorno→inicio de persistencia | 3,151 / 7,994 / 22,007 | 2,221 / 6,229 / 8,953 |
| Escritura/flush/fsync del bruto | 2,422 / 2,895 / 18,797 | 2,438 / 2,926 / 18,620 |
| Procesamiento tras persistir bruto | 0,080 / 0,537 / 0,588 | 0,078 / 0,542 / 0,705 |
| Primera lectura de fila→retorno con LF | 68,924 / 100,411 / 101,711 | 65,701 / 88,598 / 99,323 |

Los lectores funcionan sin stdin ni bucle de slots; comparten bloqueo de journal.
La espera previa a persistir incluye bloqueo y planificación; la persistencia
del bruto incluye write/flush/fsync. No está aislada la duración del fsync del
ledger, que contribuye al servicio. Servicio no equivale a disponibilidad del fd:
no se registró el resultado de cada `select` ni URBs USB o contadores de overrun.
Tampoco los timestamps read son instantes de llegada física de cada byte.

Máximo entre muestras activas consecutivas del ledger: **22,359078 ms**. Los
offsets BOOTTIME−MONOTONIC observados varían entre 50 y 33964 ns; las diferencias
de spans completos BOOTTIME−MONOTONIC y REALTIME−MONOTONIC son −403/−887 ns.
No aparece señal de pausa global o suspensión del host de escala 1 s en esta
traza; el muestreo sucesivo de relojes aporta ruido. No prueba que USB/driver,
firmware o planificación no hayan influido antes de las lecturas registradas.
239 controles de almacenamiento; mínimo libre 113935876096 bytes y máximo bruto
405743 bytes, sin error o límite registrado.

## Las tres incidencias de RX-01 y su recuperación

Tiempos relativos al inicio común; se usan fronteras `(última fila, recuperación]`.
Los ids se vinculan por bytes, no por suponer una frecuencia.

| Incidencia | Host inicio→recuperación, s | Id / líneas RX-01 | Hueco host, ms | Hueco local, ms | Primera devolución de bytes tras ancla, ms | Lecturas/bytes RX-01 | Filas RX-02 |
|---|---|---|---:|---:|---:|---|---:|
| 1 | 2,806569590→4,022134198 | 6→7 / 98→99 | 1215,564608 | 1200,083 | 1136,574303 | 6 / 867 | 7 |
| 2 | 44,025383446→45,219548291 | 128→129 / 220→221 | 1194,164845 | 1199,918 | 1116,633961 | 6 / 905 | 5 |
| 3 | 57,217679951→58,613260800 | 166→167 / 258→259 | 1395,580849 | 1398,388 | 1324,366244 | 5 / 860 | 5 |

Las recuperaciones son las filas de offsets `[10583,11450)`, `[114058,114963)`,
`[146225,147085)`, completadas por los eventos de ledger **838, 8911, 11507**.
Sus primeras lecturas son los índices 72, 736, 939; las últimas, 77, 741, 943
(índices por RX, desde cero). Los hashes y tiempos absolutos están en el JSON.
En cada incidente todos los bytes devueltos por RX-01 pertenecen a esa siguiente
fila completa. Antes de su primera devolución de bytes no hay otras lecturas
RX-01 que expliquen el hueco como una fila parcialmente recibida durante todo
el silencio; su ensamblado final tarda aproximadamente 71–79 ms más.

El servicio RX-01 cuenta 89/87/101 eventos dentro de esos huecos; RX-02,
96/92/110. Los máximos de servicio con fronteras incluidas son RX-01
19,039/22,247/24,194 ms y RX-02 23,446/36,595/20,325 ms. RX-02 devuelve
42/42/40 bloques, 5320/5249/5163 bytes. No se observa parada de su lector.

Cada recuperación avanza exactamente un id y cero descartes. Después de la
primera siguen intervalos locales 399,895/400,018/399,987/400,021/599,972 ms;
después de la segunda, 800,094/199,904/200,459/599,606/399,897 ms; después de la
tercera quedan tres transiciones completas, 199,995/800,008/200,000 ms, y la cola
171 sin validar. Hubo recuperación de entrega de filas, **no recuperación
demostrada de una cadencia estable ni ráfaga de compensación de 125 filas**.

## Hipótesis que respalda y que limita la evidencia

1. **Menor cadencia de registros asociados a callbacks que pasan el filtro en
   RX-01:** compatible con ids contiguos, timestamps locales espaciados y cero
   descartes; es la descripción más próxima a las fuentes y bytes disponibles.
   No decide entre recepción/driver CSI, filtrado previo al id, diferencias de
   exposición radioeléctrica, firmware efectivo o comportamiento del reloj.
2. **Pausa global del host, stdin bloqueado o fsync de un segundo:** no explican
   por sí solos esta traza: ambos lectores se sirven continuamente, RX-02 produce
   filas y los tiempos medidos están en milisegundos. El journal compartido sí
   aporta latencia medible; no se afirma que el host no tenga ningún efecto.
3. **Cola llena, pérdida de líneas después del id o retención de una secuencia
   regular de CSI seguida de recuperación:** no hay sus señales esperadas de
   salto de ids, aumento de queue_drops, reloj local de 200 ms durante el hueco
   o ráfaga posterior. Son menos compatibles como explicación única bajo la
   semántica de las fuentes inspeccionadas; no hay observación directa del hilo
   callback, TX UART, USB o driver para excluir todos sus fallos posibles.
4. **Pérdida RF demostrada, fallo de TX o menor calidad del canal de RX-01:** no
   demostrados. RX-02 sirve de control de flujo, pero no prueba qué recibió
   RX-01 ni qué emitió TX a cada instante. No existe secuencia TX correlacionada,
   monitor RF independiente ni contador de callbacks previos al filtro.

## Siguiente experimento mínimo propuesto, sin ejecutar ni autorizar

Para distinguir **emisión UART escasa** de **entrega tardía/pérdida en el camino
USB/host**, añadir a un único diagnóstico dual nuevo de 60 s una observación
pasiva independiente del **TX UART0 de RX-01**, a 115200 8N1, sin escribir al RX,
sin cambiar firmware, geometría o política. RX-02 se conserva como control.
Un analizador lógico/registrador compatible debe capturar bytes y tiempos
completos; el punto de prueba y su accesibilidad tienen que verificarse primero.
No se asume que ese instrumento o pin sea accesible actualmente. Correlacionar
las filas por id y bytes, conservar brutos y comparar intervalos, sin imponer
sincronía absoluta entre relojes ni ajustar un detector.

| Resultado futuro | Qué distinguiría | Qué seguiría abierto |
|---|---|---|
| UART ya emite ids/timestamps espaciados, mismos bytes que host | La escasez existe antes de la entrega USB/host observada | RF/driver/filtro/callback/writer y binario efectivo |
| UART emite filas que host no conserva, o intervalos mucho más regulares | Aporta evidencia directa de discrepancia después del punto UART | Adaptador USB, driver, planificación o almacenamiento; localizar luego con traza USB |
| Bytes coinciden y UART se acumula/retrasa respecto al timestamp local | Separa demora de emisión de demora posterior al UART | Driver/cola/tarea del RX; no demuestra pérdida RF |

Este experimento es el mínimo para observar la frontera UART ausente en este
bundle; **no separa por sí solo RF de filtrado/driver**. Si confirma escasez
anterior al UART, una etapa posterior requeriría observación RF/TX independiente
con secuencia verificable; lo recibido por un monitor tampoco equivale a lo
decodificado por RX-01. Cambiar puertos/cables/posiciones a la vez no identificaría
la capa. No se prepara aquí otro comando físico ni se reutiliza la autorización
consumida: cualquier nueva adquisición requiere plan y aprobación explícita.

## Reproducción offline y preservación

```bash
.venv/bin/python -B tools/analizar_continuidad_dual.py \
  --bundle results/local/continuidad-dual-01-60s-intento-unico \
  --output-new /tmp/continuidad-dual-01-forense-r1-NUEVO.json
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python -B \
  -m unittest test_continuity_diagnostics test_dual_continuity -v
```

269 pruebas de regresión aprobadas en 24,512 s, cero omisiones, incluidas siete
nuevas de estadística, fronteras, cabeceras, salida exclusiva y reproducción del
bundle físico sin construcción de Serial. Los fixtures PTY son sintéticos; el
análisis físico usa exclusivamente este bundle existente. No se atribuye
aislamiento de Bubblewrap a las pruebas directas. Se verifica preservación por
hash antes/después: 2624 archivos anteriores idénticos, incluidos brutos, colas,
manifiesto, resumen y autorización consumida; un archivo adicional, el estado
general, actualizado solo por apéndice con prefijo histórico intacto. No se abrieron UART,
repitieron capturas, resetearon/reconectaron ESP ni cambiaron firmware o umbral.
