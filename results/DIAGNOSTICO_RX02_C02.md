# RX02-C02: hueco posterior a la ventana y continuidad frente a C01

**C02 permanece rechazada por `availability_gap:RX-02`; la ventana S no es
elegible, su etiqueta sigue sin declarar y E no se inició.** El hueco disparador
ocurrió después de T1 y antes de que se solicitara el aviso final. El análisis
no mueve fronteras, completa etiquetas, reinterpreta la cola o aprueba datos
retrospectivamente. No se propone ni prepara otra adquisición.

La evidencia nueva distingue un **intervalo host de 1.221,331818 ms** entre dos
filas completas de un intervalo local de firmware de **199.978 µs = 199,978 ms**
entre esas mismas filas. Antes del fallo se acumulan lecturas en bloques y
demoras de servicio/registro del host. Esto da soporte a entrega tardía y
degradación del pipeline host, sin identificar una causa exclusiva en disco,
planificación, USB, UART, firmware o RF. No demuestra una pausa de 1,2 s en
los timestamps de los paquetes representados por el receptor.

Fuentes: `results/local/piloto-rx02-r1-C02` y
`results/local/piloto-rx02-r1-C01`. [Resumen reproducible y referencias exactas](DIAGNOSTICO_RX02_C02.resumen.json),
[validación](DIAGNOSTICO_RX02_C02.validacion.json) y [hashes de publicación](DIAGNOSTICO_RX02_C02.archivos.json).
Los **34 archivos protegidos** (ambos bundles y ambos directorios de autorización
explícita) mantienen sus tamaños y SHA-256 originales, incluidos los permisos
consumidos. Las auditorías nuevas y sus inventarios están fuera de los bundles.

## Resultado original, sin sustitución

La auditoría RX-02 reproduce integridad, replay, identidad y almacenamiento
correctos en C02: **29.106 operaciones, 1.917 eventos, 1.014 filas completas**,
ids 0…1013 consecutivos y `queue_drops=0`. Una apertura y un cierre de RX-02,
`retry_count=0`. La calidad de conexión sigue `false`, con el preámbulo anómalo,
`availability_gap:RX-02` e `incomplete_tail:RX-02` conservados. El primer fatal
no se sustituye por el motivo de cola añadido al cerrar.

| Aspecto de C02-S | Estado reproducido |
|---|---|
| Duración original | 30 s: T0=4317281061098, T1=4347281061098 ns host monotónicos. |
| Filas incluidas | 149, ids 821…969, líneas 914…1062. |
| Bins de 5 s | 25, 24, 25, 26, 25, 24. |
| Hueco máximo con bordes | 226,869081 ms; inicio 189,973055 ms, fin 206,854737 ms. |
| Comprobaciones internas | `window_quality_ok=true`, `pilot_coverage_ok=true`. |
| Aviso final de ventana | `end_signal=null`; no fue solicitado ni reproducido. |
| Etiqueta | `status=pending`, `declaration_ns=null`, `timing_uncertainty=unknown`; cero operaciones `declare`. |
| Elegibilidad | `false`: `connection_suspended`, `anomaly_intersects_or_unlocated`, `label_quality_ok`. |
| Ventana E | Slot `RX02-C02-E` restante, `state=suspended`; no fue solicitado ni adquirido. |

Los criterios internos usan los umbrales previos sin cambios: mínimo 120 filas,
15 por bin y hueco máximo 500 ms con bordes. Que esas comprobaciones pasen no
certifica la etiqueta ni la conexión. La explicación posterior del operador se
conserva como relato del fallo, **no como un `yes`** ni como observación continua
de ocupación. Tampoco se transforma `pending` en una declaración de incertidumbre
que nunca se introdujo: ambos campos originales permanecen como estaban.

Hay 44 filas completas posteriores a T1; no se añaden a las 149 de la ventana.
No hay ventana vacía ni pareja S/E completa de C02 que pueda compararse como tal.

## Tiempos exactos del incidente

Todos los tiempos siguientes son nanosegundos monotónicos del host, sin
sincronización RF o alineación absoluta con el reloj local del receptor.

| Suceso | Tiempo host, ns | Respecto de T1 |
|---|---:|---:|
| T1 original | 4347281061098 | 0 s |
| Evento de fin de ventana | 4347285604837 | +0,004543739 s |
| Retorno que completa id 1008 | 4355098505012 | +7,817443914 s |
| Primer instante que excede frescura de esa fila | 4356098505013 | +8,817443915 s |
| Inicio del read disparador | 4356319767667 | +9,038706569 s |
| Retorno que completa id 1009…1013 | 4356319836830 | +9,038775732 s |
| Muestra de decisión y suspensión | 4356805088842 | **+9,524027744 s** |
| Primer instante posible del aviso final | 4357281061098 | +10 s |
| Cierre confirmado RX-02 | 4358275291649 | +10,994230551 s |

El aviso final exige T1 + la cola de etiqueta contractual de 10 s. La suspensión
lo antecedió en **475,972256 ms**. El cierre posterior a ese instante no significa
que se hubiera dado el aviso: con fatal activo el estado no solicita esa señal.
Sí se registraron y reprodujeron las señales separadas de fallo y de cierre.

El par causal es **1008 → 1009**, no 1013 → una fila supuesta. Referencias:

| Fila | Línea / bytes [inicio, fin) | Lecturas primera / última | Retorno LF | Local, µs |
|---|---|---|---:|---:|
| 1008 | 1101 / [875512, 876386) | 6333 / 6333 | 4355098505012 | 202370649 |
| 1009 | 1102 / [876386, 877176) | 6333 / 6334 | 4356319836830 | 202570627 |

Diferencia host **1.221,331818 ms**, exceso de **221,331818 ms** sobre la
frescura de 1 s. Diferencia local **199978 µs**, id +1 y drops +0. La fila 1009
ya había empezado en el chunk anterior, pero recibir parte de una línea no
equivale a completar otra fila válida. No se rellenan sus tiempos intermedios.

La operación disparadora es `seq=29099`, `op=chunk`, offsets
[876794, 880889), **4.095 bytes**, SHA-256
`3ac3a88dd212df76ffd9bcd561aa042e8d5e4e2ca59f73c4e40455be69dc82c5`.
Se completa id 1009, se emite la suspensión y el mismo chunk ya leído/durable
todavía se analiza: contiene también las filas completas 1010…1013 y la cola.
Los cuatro eventos de fila que aparecen después de `suspended` en ese chunk
**no son nuevas lecturas, recuperación ni reanudación de la captura**. Todos
comparten el retorno de lectura y la muestra de decisión registrados; no hay
cronometraje separado por fila del parser.

El último tick anterior, operación 29097, veía solo **515,415490 ms** de edad de
id 1008. El siguiente procesamiento de una fila encuentra el salto entre
retornos y genera `availability_gap`, no `availability_lost` por tick. La edad
de aquella fila en la muestra de decisión ya era **1.706,583830 ms**. No se
redefine el límite para aceptar el bloque tardío.

## Lectura, durabilidad y procesamiento: lo medido y sus límites

La fuente inspeccionada toma `started_ns` y `returned_ns` alrededor de
`serial.read`. El journal escribe/flush/fsync del bruto y luego toma `now_ns`,
aplica el reductor/parser y finalmente escribe/flush/fsync la operación.
Por tanto, retorno→decisión **incluye** durabilidad del bruto, espera del lock,
planificación y sobrecarga Python. No es una duración aislada de fsync.

La siguiente tabla descompone el intervalo medido, sin asignar causas exclusivas:

| Intervalo registrado | Duración |
|---|---:|
| Retorno anterior → muestra de decisión anterior | 300,982224 ms |
| Decisión anterior → tick 29097 | 214,433266 ms |
| Tick → muestra de storage_check 29098 | 205,825550 ms |
| Storage_check → inicio del read siguiente | 500,021615 ms |
| `serial.read` disparador | **0,069163 ms** |
| Retorno disparador → muestra de decisión/fallo | **485,252012 ms** |

Los primeros cinco intervalos suman el hueco host de 1.221,331818 ms; con el
último suman 1.706,583830 ms. El read final no estuvo bloqueado durante 1,2 s:
transcurrió casi todo el intervalo antes de invocarlo. Los tiempos entre
muestras de operaciones pueden incluir parser, journal/fsync, guardia de
almacenamiento, reproducción/notificaciones, consola, entrada y planificación;
no permiten llamar a todo ello «tiempo de parser» o «latencia de disco».

En la cadena causal hay muestras intermedias, pero la mayor separación entre
ellas alcanza **985,342790 ms**. No se demuestra una única pausa global mayor
de un segundo; tampoco se sostiene el servicio rápido/continuo observado en el
diagnóstico dual EXP02 anterior. Aquí las demoras crecientes en varias etapas
acumulan más de un segundo entre lecturas.

La degradación posterior a T1 ya es visible antes del disparo:

| Operación read | Retorno relativo a T1 | Bytes | Retorno → decisión |
|---|---:|---:|---:|
| 29084 | +4,799153493 s | 799 | 158,668163 ms |
| 29087 | +5,587704822 s | 3.280 | 167,365724 ms |
| 29090 | +6,260394820 s | 2.914 | 156,583916 ms |
| 29093 | +6,912753358 s | 2.593 | 117,490783 ms |
| 29096 | +7,817443914 s | 4.095 | 300,982224 ms |
| 29099 | +9,038775732 s | 4.095 | 485,252012 ms |

En esas seis lecturas, `read` dura entre 0,039514 y 0,069163 ms. La entrega de
varias filas con un único timestamp host es compatible con acumulación antes
de que la aplicación vuelva a servir el flujo. No localiza esa acumulación en
una cola concreta ni mide retraso absoluto desde el aire.

En la ventana S, los 941 reads tienen retorno→decisión máximo **34,884556 ms**;
en los primeros cuatro segundos posteriores, 122 reads y máximo **4,661458 ms**;
después de esos cuatro segundos, 20 reads y máximo **485,252012 ms**. El máximo
dentro de la ventana se conserva, sin equipararlo al episodio posterior.

No hay medidas separadas de inicio/fin del fsync, parser o select/listo, traza
de planificación, URBs USB, reloj BOOTTIME, memoria/presión del sistema o log
TX/RF concurrente. No se puede aislar disco, proceso, kernel/driver, USB,
suspensión o comportamiento eléctrico. Los controles de almacenamiento pasan;
eso verifica espacio/límites, no una latencia de disco aceptable.

## Cola final y rechazo conservador

Se conservan **349 bytes sin LF**, offsets [880540, 880889), SHA-256
`dfc8af86bd78634940863e9e27ca991b87ad84b0317eaa6cdea8b3a39b739f97`.
Su cabecera literal contiene id=1014, local_timestamp=203571797,
queue_drops=0, canal 11 y len=256. No es una fila CSI validada y **no se suma
como fila 1015 ni se completa su payload**. El salto literal respecto de la
última fila completa id 1013 es 201176 µs; sirve solo como contexto parcial.

La cola empezó en el read disparador, ya después de T1. Su intervalo original
tiene `end_ns=null`; el fallo añadido de cola tiene `start_ns=null`. El
certificador exige límites conocidos para excluir anomalías y por eso conserva
`anomaly_intersects_or_unlocated`. Ese motivo **no prueba un daño dentro de
la ventana**, pero no se elimina para aprobarla. Además, la conexión suspendida
y la etiqueta ausente bastan para mantener su inelegibilidad.

Con fatal activo, el cierre no entra en el bucle de drenaje normal: preserva
la cola y libera RX-02, sin intentar adquirir el resto para fabricarle LF.
El recibo verificado confirma `reader_stopped=true`, `error=null`,
`selected_confirmed=true`, fd liberado e `is_open=false`. La confirmación
`selected_port_closed_confirmed` refiere solo a RX-02, no a RX-01. Cola y cierre
confirmado son resultados distintos y ambos permanecen en la evidencia.

## Qué cambia frente a C01

Las 18 fuentes de adquisición coinciden por hash entre ambos intentos; también
protocolo, perfil, identidad/binding, baud/settings serie, política y límites.
Montaje/estado sin cambios desde C01 es declaración actual del operador, no
metrología o atestación del binario instalado. Ambas conexiones llegaron a
READY y disponibilidad inicial; eso no demuestra repetibilidad general de
arranque, ausencia de transitorios o estabilidad futura. No se provocó un
reset/reconexión durante este análisis.

| Continuidad de conexión completa | C01 | C02 |
|---|---:|---:|
| Apertura → cierre | 664,114355399 s | 205,841626668 s |
| Filas completas | 3.299 | 1.014 |
| Mediana / máximo hueco host | 200,133822 / 416,871054 ms | 199,661826 / 1221,331818 ms |
| Huecos host >500 ms / >1 s | 0 / 0 | 5 / 1 |
| Máximo hueco local | 401,429 ms | 399,686 ms |
| Mediana / máximo retorno→decisión | 2,561310 / 73,721540 ms | 2,303220 / 485,252012 ms |
| Máximo retorno→inicio del siguiente read | 346,921789 ms | 1221,262655 ms |
| Filas adyacentes con retorno host idéntico | 0 | 14 pares |
| Cola final | 0 bytes | 349 bytes sin LF |
| Etiquetas / ventanas exploratorias | Dos declaradas / dos elegibles | Ninguna declarada / ninguna elegible |

C02 tiene cinco huecos host mayores de 500 ms, **todos posteriores a T1**:
788,551329; 672,689998; 652,358538; 904,690556 y 1221,331818 ms. Los saltos
locales de sus respectivos pares son 199572, 199911, 200024, 203488 y 199978 µs.
Se conserva el máximo local anterior cercano a 400 ms; no se presenta la
cadencia local como perfectamente uniforme. Los 14 pares de hueco host cero
son filas agrupadas en un read, no simultaneidad RF o muestras duplicadas.

Las medianas/p95 de toda C02 ocultan un episodio breve al final; por eso se
publican fases, extremos y cadena causal. Se comparan distribuciones de lo
realmente registrado, sin igualar artificialmente duración, eliminar esperas
o tratar ambos intentos como réplicas independientes de igual exposición.
Las filas consecutivas/drops cero no demuestran ausencia de pérdidas RF antes
del callback ni después del último dato observado.

**Evidencia nueva:** RX-02 no garantiza continuidad host bajo esta operación
solo porque C01 y A1/B/A2 no mostraron huecos >1 s. En este fallo, la separación
de timestamps host diverge claramente de la local en los mismos ids y coincide
con lecturas agrupadas y mayor demora del journal/servicio del host. Esto
prioriza investigar el camino de entrega/registro y la planificación, con la
incertidumbre indicada. No justifica aumentar frescura/cobertura ni atribuir
automáticamente una avería RF, un defecto de RX-02 o un cambio por ocupación.
Sin un lector concurrente de RX-01 tampoco se identifica un efecto común a
ambos receptores.

## Estado y siguiente decisión

Ambas autorizaciones originales quedan **consumidas y no reutilizables**, con
referencias distintas C01/C02, y ambos bundles quedan intactos. C02 conserva
su partición por conexión completa `RX02-C02` / `development_future`, incluido
el fallo: no se reemplaza, divide o selecciona una ventana favorable. La
campaña permanece detenida para revisión; C03–C06 no se preparan ni ejecutan.

Antes de considerar otra adquisición, corresponde revisar offline el costo y
los puntos de observación del journal/fsync, guardia de almacenamiento y
servicio del bucle frente a estos tiempos. Las trazas existentes acotan el
problema, pero no distinguen por sí solas todas esas capas. Una instrumentación
o experimento futuro necesitaría revisión propia y autorización nueva; aquí
no se implementa ni se prepara. No se calibra, entrena, clasifica presencia,
ajusta firmware/montaje/umbrales o abre UART.

## Reproducción y comprobaciones

```bash
.venv/bin/python -B tools/diagnosticar_rx02_c02.py \
  --output-new results/local/diagnostico-rx02-C02-REPRODUCCION-NUEVA
PYTHONPATH=src:tests .venv/bin/python -B -m unittest \
  test_rx02_gap_diagnostics test_presence_rx02 test_v4_availability_diagnostic
```

La herramienta solo lee los originales y crea una salida externa exclusiva.
Reproduce ambas auditorías, verifica referencias de filas, cobertura, cola y
consumo/cierre antes de comparar. **53 pruebas aprobadas, cero fallos, errores
u omisiones**, diez nuevas para distinguir el par disparador de la última fila,
tiempos locales/host, agrupación, bordes, cola literal, etiqueta ausente y
permisos separados. Pruebas directas offline con endpoints sintéticos, sin
afirmar aislamiento Bubblewrap. Evidencia completa local en
`results/local/diagnostico-rx02-C02-r1/` y `-r2/`; fuentes y hashes en el resumen.
