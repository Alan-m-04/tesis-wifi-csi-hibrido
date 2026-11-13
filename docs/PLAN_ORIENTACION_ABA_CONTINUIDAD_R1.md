# Orientación RX-01: comparación A–B–A para revisión

Base Git: `4cd768aeea090966777e95bc7df6aded2d8afbdf`.
Estado: **preparado para revisión, sin autorización ni ejecución**.
Protocolo sin cambios: [continuity-dual-1](CONTRATO_CONTINUIDAD_DUAL_1.md).
Se conserva el [diagnóstico anterior](../results/DIAGNOSTICO_CONTINUIDAD_DUAL_01_R1.md)
y su autorización consumida. El intercambio de posiciones sigue con viabilidad
dudosa; este plan estudia orientación y no requiere ese intercambio.

Alan confirma que RX-01 puede girar en su posición sin tensar el cable. Esa
declaración todavía no confirma un ángulo concreto o el plano de apoyo. No se
han movido equipos para verificarlo ni abierto UART durante la preparación.

## Condiciones A y B que se fijarán antes de medir

**A:** orientación actual, definida como 0° relativo. Marcar en el soporte o en
un croquis el centro C de la placa y una flecha desde el centro del conector USB
hacia el extremo opuesto. Registrar también el contorno, altura, cara visible y
orientación respecto de un borde fijo de la laptop. No suponer que los nombres
de la placa identifican con precisión el centro de la antena.

**B propuesta r1:** giro de RX-01 de **+90° horario visto desde arriba**,
alrededor del centro C, con mismo soporte, altura y cara visible. Esta definición
presupone apoyo horizontal y holgura para ese ángulo. Ambos puntos quedan
**pendientes de confirmación sin efectuar el giro ahora**. Dibujar de antemano
la flecha B perpendicular a la flecha A; registrar el ángulo y sentido por escrito.
Si el montaje es vertical, +90° no es viable o hay duda, revisar la definición
antes de A1; no elegir otro ángulo a partir de los resultados.

**A de regreso:** volver a la marca y flecha A iniciales, sin desconectar ni
intercambiar dispositivos. Documentar cualquier desviación de centro, altura,
apoyo, orientación o recorrido de cable; no corregirla durante una adquisición.

RX-02 conserva su posición y orientación como control. TX, laptop, cables y
puertos físicos permanecen iguales. Cada RX mantiene su cable y su identidad:
RX-01 `5C93199744`, RX-02 `5C93200689`, con las rutas by-id originales. Registrar
manualmente qué puerto físico usa cada cable; by-id verifica identidad pero no
demuestra por sí solo continuidad del puerto físico entre intentos.

El giro puede mover el centro radiante de la antena aunque el centro de la placa
permanezca fijo. El cable sigue siendo el mismo, pero puede variar su curva
local. Se registran esos cambios: no se promete aislar exclusivamente polarización
o ángulo de antena. Si exige tensión, desplazar laptop/TX/RX-02, desenchufar o
forzar conectores, no se aplica B y la serie queda pendiente de revisión.

## Tres intentos independientes propuestos

| Orden | Identificador | Orientación RX-01 | RX-02 | Observación dual | Salida nueva reservada |
|---|---|---|---|---|---|
| 1 | CONT-ORI-ABA-R1-A1 | A inicial, 0° | Fijo | 60 s comunes | `results/local/continuidad-orientacion-aba-r1-A1` |
| 2 | CONT-ORI-ABA-R1-B | B, +90° horario propuesto | Fijo | 60 s comunes | `results/local/continuidad-orientacion-aba-r1-B` |
| 3 | CONT-ORI-ABA-R1-A2 | A restaurada, 0° | Fijo | 60 s comunes | `results/local/continuidad-orientacion-aba-r1-A2` |

Las tres salidas aún no existen. Son sesiones diagnósticas, no slots ni etiquetas
de presencia. Cada sesión abre una sola vez cada RX y comprueba ambos cierres:
tres aperturas por RX en total, una por intento, sin reintentos de fases fallidas.
No hay conexión UART persistente que cruce los cambios físicos ni bucle automático
que ejecute los tres intentos.

Planes revisables separados, con declaraciones PENDIENTE que bloquean ejecución:

- `config/continuidad_orientacion_aba_r1_A1.review.json`
- `config/continuidad_orientacion_aba_r1_B.review.json`
- `config/continuidad_orientacion_aba_r1_A2.review.json`

No se modifica `config/continuidad_dual_60s_r1.local.json`, usado por el intento
anterior. Estos archivos nuevos no contienen referencias de autorización y no
se han creado directorios de captura, marcadores consumidos o comandos ejecutables
para la serie. Una eventual autorización tendrá que cubrir los tres intentos
por nombre y los dos cambios de orientación; la confirmación de holgura no la
concede. El plan se presenta primero, sin solicitar ejecución todavía.

## Secuencia futura, condicionada a revisión y autorización

1. Confirmar plano y ángulo B, marcas A/B, identidad/cable/puerto físico y ausencia
   de tensión. Confirmar ambiente actual, alimentación de TX/RX/laptop, tapa,
   suspensión y ausencia de otros lectores/capturas. Completar los tres planes
   conservando esas declaraciones y la fecha real. No reutilizar declaraciones
   históricas como si fueran comprobaciones actuales.
2. Registrar A inicial y el contexto del operador. Mantener durante las tres
   adquisiciones el mismo lugar y postura del operador, puerta/ventanas y demás
   condiciones declaradas, sin etiquetarlas como presencia experimental. Las
   manos se apartan de los equipos antes de observar.
3. Antes de cada intento, comprobar que ambos UART están cerrados y solo realizar
   preflight por metadatos. Tras cualquier manipulación esperar **30 s de quietud**
   antes de abrir; aplicar también 30 s antes de A1. Esta pausa operacional queda
   fuera de los 60 s de registro y no modifica la política CSI/disponibilidad.
4. Ejecutar únicamente A1 cuando corresponda a la autorización futura. No tocar
   equipos durante los 60 s. El inicio común se fija cuando ambos lectores se
   inician; el arranque previo también se conserva.
5. Esperar la terminación del proceso y revisar integridad/replay, duración común,
   ausencia de fallo de transporte/almacenamiento y `both_ports_closed_confirmed=true`.
   Si falta cierre comprobado o integridad, detener la serie sin girar y revisar
   offline. No repetir A1. Un silencio >1 s es una incidencia observacional que
   permite recuperación; por sí solo no habilita reintento ni aprueba calidad.
6. Solo después de esos cierres y con el cambio físico autorizado: girar RX-01
   desde la marca A a la marca B previamente definida. Registrar centro, flecha,
   altura y cable, y cualquier desviación. No mover el resto. Si aparece tensión,
   detener la preparación de B; no desenchufar para resolverla.
7. Aplicar la misma espera/preflight y realizar únicamente B. Revisar y confirmar
   ambos cierres e integridad antes de cualquier otro movimiento. No cambiar B
   para obtener más filas o reducir huecos.
8. Solo con esos cierres y el cambio autorizado: devolver RX-01 a las marcas A,
   registrar el retorno, aplicar la misma espera/preflight y realizar únicamente
   A2. Verificar sus dos cierres; conservar los tres bundles por separado.
9. Ante un fallo no avanzar automáticamente ni completar la fase con otra captura.
   Si se detecta al revisar una fase reset posterior al arranque, error de firmware,
   perfil incompatible o discontinuidad, conservarlo y revisar antes de continuar.
   Durante la observación rige el comportamiento actual de continuity-dual-1;
   no se añaden excepciones ni se modifica su productor.

Los puertos USB permanecen conectados y alimentando los RX entre intentos. Se
cierran/reabren únicamente los UART entre sesiones. La apertura existente solicita
DTR/RTS false y preserva entrada, pero no garantiza ausencia de transitorios o
arranque eléctrico. Si aparecen logs de arranque se conservan; no resetear,
reconectar ni intentar obtener READY. Tampoco se concatenan ids/relojes locales
entre sesiones: pueden haber cambiado su origen. La comparación tiene ese límite
adicional de nuevas aperturas y orden temporal A1–B–A2.

## Comparación offline prevista antes de adquirir

| Variable | Comparación por sesión e identidad |
|---|---|
| Filas y cobertura | Filas completas válidas sobre los mismos 60 s; conteos por bins prospectivos de 10 s, primera/última fila y edades de borde |
| Huecos host/local | n, mediana, media, p95/p99, máximo e histograma; incidentes >1 s y recuperación; diferencias locales módulo 2^32 por RX |
| Callbacks y descartes | Id inicial/final y diferencias entre vecinos, saltos/reinicios; valores y cambios de queue_drops, sin llamarlos pérdida RF |
| RSSI | n, mediana, p10/p90 y rango sobre filas completas válidas, por identidad y sesión; no rellenar muestras ausentes |
| Perfil CSI | MAC fuente, canal, ancho, sig_mode/mcs/stbc, rx_state, len y first_word_invalid; configuración y binario declarado, sin cambiarlos |
| Transporte/host | Bytes leídos, bloques y referencias por fila, servicio, duración de read, espera/persistencia/procesamiento, relojes host y colas |
| Integridad y montaje | Auditoría, cierre, identidad/cable/puerto, marcas/ángulo y desviaciones de contexto |

Comparar RX-01 B con **ambos** A1 y A2; no seleccionar solo el A que convenga.
Mostrar A1–B, B–A2 y A1–A2, y la evolución paralela de RX-02. Una diferencia
descriptiva B menos el promedio de A1/A2, si se presenta, conserva también los
tres valores originales y no constituye prueba estadística de causalidad.
Los 171/296 históricos son antecedentes separados, no el A1 de esta serie.

RSSI representa únicamente muestras recibidas y válidas; poblaciones con huecos
distintos pueden estar sesgadas. No convertir igualdad de RSSI en igualdad de
recepción, ni menor conteo en pérdida RF. Los fragmentos de cabecera o colas sin
LF nunca cuentan como filas completas.

Un cambio de RX-01 en B que revierta en A2, con RX-02 relativamente estable,
respaldaría sensibilidad a la geometría local bajo estas condiciones. Un cambio
paralelo en RX-02 o discrepancia A1/A2 debilitaría esa lectura por deriva temporal
o cambios comunes. No observar diferencia con tres sesiones no demuestra ausencia
de efecto: son tres observaciones ordenadas, sin replicación de la serie ni
aleatorización, y no justifican significación, precisión o generalización.

Este diseño no intercambia identidades entre posiciones, no separa placa,
firmware, cable y camino USB, y no identifica una capa RF/driver/cola/USB causal.
No altera el watchdog v4 o resultados anteriores, ni permite ventanas elegibles,
calibración, entrenamiento o producción. No requiere comprar instrumentos.

## Estado de revisión

Confirmado: el operador declara viable girar RX-01 sin tensión. Pendiente:
confirmar plano horizontal y +90° horario, registrar marcas/ángulo y contexto
actual, revisar este plan y después obtener autorización explícita nueva. No se
solicita esa autorización en esta entrega. No se ha ejecutado preflight físico,
abierto UART, movido equipos ni capturado durante la preparación.
