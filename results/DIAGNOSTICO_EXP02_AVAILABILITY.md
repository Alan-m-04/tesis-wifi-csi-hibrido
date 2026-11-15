# Diagnóstico offline de EXP02: availability_lost:RX-01

Desde la base limpia `4f1223345a8a7086bf3c9a6a5dc3ad52a72f632f`, rama
`feat/backend-uart-presencia-v4`. Se analiza exclusivamente el intento existente
`results/local/exp-v4-c02-ES-20261101T222444Z-intento-unico/`.

**Disparador demostrado:** en el tick 1028 el reloj de decisión estaba
**1,006375455 s** después del retorno de la lectura que completó la última fila
válida de RX-01. El límite prospectivo seguía siendo **1 s**. Habían llegado
768 bytes posteriores sin LF: no completaban otra fila válida y no renovaron
disponibilidad. RX-02 acababa de completar otra fila, con edad de 5,673129 ms.
El rechazo se reproduce y se conserva; no se aumenta el umbral para aprobar.

No se demuestra una pausa global del host de un segundo ni un bloqueo interactivo
de esa duración en el intervalo causal. La causa física del hueco de RX-01 sigue
indeterminada. No se abrió UART, relanzó, reseteó, reconectó o cambió firmware.

## Resultado original y preservación

Integridad y replay correctos: **1035 operaciones, 280 eventos**, fatal
`availability_lost:RX-01`. Ambos receptores alcanzaron disponibilidad inicial,
pero **no hubo ninguna solicitud de slot ni ventana E/S**. Se conservaron
17 filas completas válidas de RX-01, 32 de RX-02 y una cola de 768 bytes en RX-01.
El preámbulo permanece anómalo/no interpretado y la conexión rechazada.

La autorización `EXP-V4-C02-ES-20261103T155915Z-UNICO` quedó consumida por el
lanzador antes de su único proceso hijo. El recibo confirma ambos cierres reales,
sin inferirlos de un temporizador o del código de salida. El diagnóstico no
renueva ese permiso ni propone otra adquisición.

Se inventariaron y verificaron **2459 archivos previos intactos**, incluidos el
intento, preparación, consola, auditorías, autorización/marcador consumido,
capturas anteriores y fuentes firmware/protocolos. Los artefactos nuevos están
separados en `results/local/diagnostico-exp02-availability-20261103T161331Z/`.

## Tiempos exactos y secuencia de decisión

Todos estos relojes son nanosegundos monotónicos del host; no son tiempos RF.
`A = 173523780960320`. Disponibilidad inicial: `173525355926154`
(1,574965834 s desde A). Suspensión: `173530748851912`
(6,967891592 s desde A).

| Evidencia | RX-01 | RX-02 |
|---|---:|---:|
| Última fila válida: id / línea | 16 / 109 | 31 / 125 |
| Bytes de esa fila [inicio, fin) | [18399, 19218) | [30632, 31379) |
| Primera lectura que la toca | 173529675548430 | 173530682602801 |
| Retorno de lectura que la completa | **173529742476457** | **173530743178783** |
| Muestra de reloj de decisión/procesamiento | 173529744660294 | 173530745735632 |
| Retorno → muestra de decisión | 2,183837 ms | 2,556849 ms |
| Edad al suspender | **1006,375455 ms** | **5,673129 ms** |
| Retorno de última lectura registrada, incluida parcial | 173530737851803 | 173530743178783 |

La última fila válida de RX-01 se completó en la operación 886, lectura 112,
evento 259. Su límite fue `173530742476457` (comparación estricta `>`).
El tick anterior, 1025, en `173530729910600`, aún veía 987,434143 ms de edad.
El siguiente tick, 1028, excedió el límite en **6,375455 ms** y suspendió.

Tras aquella fila hubo **934,892062 ms sin nuevos bytes registrados de RX-01**
hasta el inicio de la lectura de la operación 1016. Luego se conservaron cuatro
fragmentos de su fila incompleta: 128, 256, 256 y 128 bytes (operaciones 1016,
1020, 1023 y 1026). El último retorno parcial estaba a solo 11,000109 ms de la
suspensión, pero recibir bytes parciales no equivale a recibir una fila válida.
La cola ocupa **[19218, 19986)**; no se añadió LF, completó, recortó o validó.

La cabecera literal de esa cola contiene `id=17`, `local_timestamp=6864325`,
`queue_drops=0`. La última fila válida tenía `local_timestamp=5865004`:
diferencia literal **999321 µs**. Las primeras lecturas de ambas filas distan
**1001,820089 ms**. Esa correspondencia es compatible con un hueco cercano a
un segundo en las muestras representadas por RX-01; no demuestra por sí sola
la capa responsable o el instante exacto de recepción física. La cabecera parcial
**no se contabiliza como fila CSI validada**.

Las fuentes de RX-01 copian el timestamp del controlador y generan `id` localmente
por callback; el contador de drops registra problemas de la cola de aplicación.
ESP-IDF v5.4 describe ese timestamp en microsegundos y limita su precisión según
los modos de sueño. Se inspeccionaron las fuentes locales fijadas por hash/Git;
no se atestó el binario instalado. Id consecutivo y drops cero no demuestran que
el TX enviara o que RX-01 recibiera todos los paquetes RF. No se sincronizan esos
relojes con el host ni se infiere automáticamente una avería RF, USB o firmware.

## Persistencia, progreso del host y entrada interactiva

En el transporte inspeccionado, el reloj `now_ns` se toma **después** de
`raw.write/flush/fsync` y **antes** del reductor/parser y del write/fsync del
journal de operaciones. Es la muestra que usa el watchdog. No es una medida de
fin de procesamiento ni una duración aislada de fsync.

El retorno de lectura → muestra de decisión incluye durabilidad del bruto,
espera de lock, planificación y sobrecarga Python. Sus máximos antes de suspender
fueron **2,956041 ms en RX-01** y **3,146504 ms en RX-02**. No hay medición separada
de inicio/fin de fsync, duración del parser o fsync del journal de operaciones.
Por tanto, no se etiqueta todo ese tiempo como «latencia de disco».

Desde la muestra de decisión de la última fila válida de RX-01 hasta la suspensión:

- **107 ticks**;
- **27 lecturas no vacías de RX-02** y cuatro de RX-01 posteriores a esa muestra;
- máximo hueco entre operaciones: **10,926942 ms**;
- RX-02 completa las filas 26 a 31 durante el intervalo.

En toda la fase desde begin hasta suspender, el máximo hueco entre muestras de
operaciones fue **26,697716 ms**. Dentro de ese reloj no aparece un bloqueo activo
del bucle completo de un segundo que explique este watchdog. No excluye
latencias más pequeñas, problemas de entrega específicos de RX-01, buffers o
actividad no instrumentada en otras capas. No hay trazas de scheduler, resultados
de select por fd, entrada a readline o escritura a stdout para identificar una
causa más allá de esas observaciones.

Se contrastaron además los extremos UTC del lanzador: desde
`2026-11-03T16:12:14.540081+00:00` hasta `2026-11-03T16:12:25.648929+00:00`,
**11,108848 s**. Desde begin hasta la última muestra del journal transcurren
**10,965198560 s** monotónicos: diferencia **143,649440 ms**, que también incluye
arranque y finalización del proceso. En Linux `CLOCK_MONOTONIC` excluye la
suspensión del sistema; por eso los gaps monotónicos solos no la descartan.
Si UTC no tuvo un salto compensatorio, esos extremos no dejan margen para un
segundo adicional de suspensión. No se registraron `CLOCK_BOOTTIME`, eventos de
suspend o ajustes de reloj: no se convierte esa comparación en prueba absoluta
de ausencia de suspensión ni se asigna la diferencia a una causa concreta.

`operate()` usa `select(stdin)` seguido de `readline()`. En una entrada parcial,
readiness no garantiza una línea completa y readline puede bloquear; se demuestra
ese mecanismo con un **pipe sintético propio**. El modo TTY y las llamadas de
entrada reales no se registraron. Los ticks/lecturas continuos del intento no
respaldan que ese mecanismo bloqueara un segundo en el intervalo causal.
No se cambia el bucle interactivo basándose en esa hipótesis no demostrada.

Los avisos de audio se completaron después de cerrar, no durante el hueco causal:
la confirmación de cierre RX-01 se registró en `173530794910916`, la de RX-02 y
ambos cierres en `173530798302898`,
**49,450986 ms después de suspender**. Las confirmaciones de reproducción llegaron
en `173532763647996` y `173534720953651`. Esas esperas posteriores de aproximadamente
dos segundos no son una pausa del lector que explique la suspensión anterior.
La cola se conserva porque el cierre por fatal no intenta completarla para aprobar.

## Corrección mínima del informe, mediante artefacto nuevo

La apertura física **sí ocurrió**: procedencia `physical_capture`, transporte
`UART`, operaciones opened/bindings de ambos RX, una apertura/cierre por RX y
recibo de liberación de fd. El resumen de captura en consola decía
`physical_capture=true`. El auditor offline imprimía como constante
`physical_UART_opened=false`: pretendía describir su propia actividad, pero el
campo sin contexto permitía atribuirlo erróneamente a la adquisición.

Se introduce el esquema de presentación `tesis-v4-exploratory-audit-report-v2`:

```json
{
  "acquisition": {
    "physical_capture": true,
    "physical_UART_opened": true,
    "physical_UART_opened_by_receiver": {"RX-01": true, "RX-02": true}
  },
  "audit_activity": {"mode": "offline", "physical_UART_opened": false}
}
```

Se elimina el alias ambiguo de primer nivel del informe nuevo. La apertura se
deriva de evidencia reproducida; una intención física sin prueba de apertura se
informa como desconocida, no como apertura confirmada ni como ausencia demostrada.
Los PTY sintéticos siguen sin ser UART físicos.

La [herramienta de auditoría](../tools/auditar_exploratorio_v4.py) solo cambia la
presentación. En `resumen-corregido-v2.json` y `enmienda-informe.json` se entrega
la corrección separada, con hashes/rutas de los originales y significado de los
campos. **No se sobrescribieron** `summary.json`, `auditoria-compacta.json`, consola,
auditoría final, recibo o autorización. Conexión, ventanas vacías, elegibilidad y
rechazo coinciden con los originales. No cambia el capturador, el watchdog,
los parámetros, las políticas o firmware.

## Reproducción y pruebas

```bash
.venv/bin/python -B tools/diagnosticar_availability_v4.py \
  --bundle results/local/exp-v4-c02-ES-20261101T222444Z-intento-unico \
  --control results/local/preparacion-exp-v4-c02-20261101T222444Z/final-20261103T155915Z \
  --output-new /tmp/diagnostico-EXP02-nuevo.json
```

El comando audita los originales y crea exclusivamente una salida nueva. El
reproductor del resumen corregido también es offline; su código de salida 1
conserva la falta de ventanas elegibles y no indica permiso para reintentar.

**246 pruebas aprobadas, sin fallos, errores u omisiones**: las 234
anteriores más [12 específicas](../tests/test_v4_availability_diagnostic.py).
Incluyen replay histórico sin modificar archivos, clocks exactos, cola sin LF,
frontera de 1 s intacta, fila completa antes del plazo, uso del retorno en vez del
reloj posterior de procesamiento, pausa global sintética con la misma razón,
contraste UTC/monotónico con límites de atribución, readline parcial sintético y
contextos físico/sintético/desconocido del informe.
Las reconstrucciones sintéticas muestran mecanismos posibles, no nuevos hechos
físicos ni causalidad del intento.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python -B -m unittest \
  test_uart_v4 test_persistent_presence_v4 test_availability_window \
  test_controlled_v2 test_controlled_v3 test_capture_preparation \
  test_capture_boundaries test_boundary_diagnostic test_v4_line_policy \
  test_v4_startup_sequence test_v4_exploratory test_v4_availability_diagnostic -v
```

Bubblewrap continúa fallando explícitamente al crear namespaces. Los tests
directos en el entorno restringido no acreditan su aislamiento. [Verificación
versionada](DIAGNOSTICO_EXP02_AVAILABILITY.validacion.json). No se calibró el
detector ni se adquirieron nuevas mediciones. La autorización física está
consumida y no hay reintento autorizado.
