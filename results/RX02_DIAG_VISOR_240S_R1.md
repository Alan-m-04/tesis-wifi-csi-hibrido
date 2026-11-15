# RX02-DIAG-VISOR-240S-R1 — auditoría offline

El operador ejecutó el único intento autorizado el 10 de noviembre de 2026.
El diagnóstico alcanzó los 240 s, con integridad, replay y cierre confirmados.
El bruto conserva **1.192 filas CSI completas**. La **calidad estricta de la
conexión quedó rechazada por el preámbulo**. El plan tiene cero ventanas y
etiquetas, con calibración, entrenamiento y producción deshabilitados.

## Adquisición, persistencia y cierre

| Hito desde `opened` | Tiempo |
| --- | ---: |
| Retorno host de READY | 0,564641474 s |
| Retorno host de la primera fila CSI | 0,779123344 s |
| Disponibilidad inicial del reductor | 1,172849039 s |
| Solicitud de cierre | 240,000924888 s |
| Inicio de cierre | 240,003543760 s |
| Cierre confirmado | 240,005564743 s |

El recibo acredita una apertura, un cierre, lector detenido y descriptores
liberados. El capturador salió con código 0. La confirmación de reproducción
del aviso quedó 1,947 s después del cierre y corresponde al reproductor de
software. La audibilidad sigue sin comprobación humana registrada. El permiso
`RX02-DIAG-VISOR-240S-R1:8f4420bc9af3…` quedó consumido, con reintento deshabilitado.

El auditor reprodujo el estado, los eventos y el recibo, con el mismo resultado
que `audit-native.json`. Verificó 13 archivos del bundle, incluido el manifiesto,
**1.003.914 bytes brutos**, **7.929 lecturas con datos** y **48.610 operaciones**.
Se comprobaron tamaño y SHA-256 de cada referencia de lectura y de las 1.284
líneas, con cobertura contigua del bruto y **cero bytes de cola final**. El
journal terminó con **78 checkpoints**, última secuencia durable 48.609 y cero
bytes pendientes. El SHA-256 del bruto es
`778138fd890b2c9f022283085f7a396c75bee1c89196e56fefcf95264723dde4`.

## Filas y huecos

Se registraron IDs de callback consecutivos **0–1.191**, con `queue_drops=0`
en todas las filas y cero errores de continuidad del parser. La primera y
última fila quedaron separadas por 239,192 s en el reloj host, a una cadencia
de **4,979 Hz** calculada entre esos extremos. Los huecos se calcularon entre
retornos host de lecturas que completan filas y, por separado, entre marcas
locales de RX-02. Las marcas locales conservan su diferencia módulo 2³².

| Entre filas consecutivas | Mediana | p95 | p99 | Máximo | >500 ms | >1 s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Retorno host | 199,994 ms | 215,409 ms | 221,761 ms | 614,783 ms | 1 | 0 |
| Reloj local RX-02 | 199,997 ms | 202,512 ms | 204,392 ms | 601,971 ms | 1 | 0 |

Los cuatro intervalos que superaron 250 ms en cualquiera de los dos relojes
ocurrieron entre IDs contiguos y con `queue_drops` estable en cero.

| IDs | Retorno host | Reloj local RX-02 |
| --- | ---: | ---: |
| 819 → 820 | 397,965 ms | 399,991 ms |
| 850 → 851 | 405,162 ms | 400,039 ms |
| 999 → 1.000 | 614,783 ms | 601,971 ms |
| 1.031 → 1.032 | 388,065 ms | 396,144 ms |

El hueco mayor se situó entre 200,961 s y 201,576 s desde la apertura. Dentro
de él quedaron **114 ticks de servicio** y seis retornos de chunks. La primera
lectura de la fila 1.000 comenzó 549,239 ms después del retorno que completó
la fila 999. El hueco aparece en el registro de adquisición y en el reloj
local, con el bucle host activo. Los relojes y contadores disponibles no
identifican la causa ni permiten cuantificar pérdidas de tramas antes del
callback. Dentro del bruto, el replay confirma continuidad de bytes y filas
consecutivas.

## Rechazo de calidad estricta

El journal conserva `format:RX-02` **20 veces** y `preamble_anomaly:RX-02`
**una vez**. Antes de READY, en la línea 91, el parser clasificó 20 líneas
inválidas. Una contenía UTF-8 inválido y 19 quedaron como `unrecognized_bytes`.
El preámbulo sellado registró 87 anomalías: esas 20 líneas, 66 líneas
informativas fuera de las excepciones exactas y un marcador de arranque en la
línea 3. El registro acredita la recepción del marcador antes de READY. El
disparador del arranque queda indeterminado.

Los dos mensajes de inicialización admitidos por la política conservaron su
clasificación en las líneas 89 y 92. A partir de la primera fila CSI, las
1.192 líneas restantes fueron filas CSI. El reductor registró cero fallos y
cero suspensiones. El rechazo del preámbulo quedó intacto al completar el
servicio y verificar el cierre.

## Contadores del visor y conservación del registro

| Contador guardado | Valor |
| --- | ---: |
| Filas CSI procesadas por el visor | 1.192 |
| Filas expulsadas del buffer visual | 1.184 |
| Filas conservadas en la última instantánea | 8 (IDs 1.184–1.191) |
| Líneas inválidas según el contador del visor | 21 |
| Operaciones recorridas por el visor | 48.610 |
| Bytes brutos recorridos por el visor | 1.003.914 |
| Bytes de journal pendientes al terminar | 0 |

Las 21 líneas del contador corresponden a las 20 inválidas y al marcador de
arranque. Se repitió offline la extracción LLTF de las 1.192 filas CSI sin
errores de decodificación. Las ocho referencias finales coinciden con el
bruto. El contador de 1.184 expulsiones mide la rotación del buffer de ocho
filas y puede incluir filas ya mostradas. El navegador no guarda un conteo
de cuántas filas llegó a presentar. El observador recorrió todas las filas y
bytes auditados y terminó con cero atraso. Los descartes del buffer dejaron
el registro íntegro.

## Evidencia

La consolidación y su arnés reproducible están en
`results/local/consolidacion-rx02-visor-240s-r1/`. `evidencia.json` incluye los
inventarios y hashes del bundle, del visor y de la preparación, los límites de
tiempo, las referencias a las líneas de preámbulo y el detalle de los cuatro
huecos. Los inventarios de entrada se verificaron antes y después. Los dos
preflights, la declaración y los recibos se conservaron. La auditoría trabajó
con los archivos guardados, con C04–C06 reservadas y sin nuevas capturas.
