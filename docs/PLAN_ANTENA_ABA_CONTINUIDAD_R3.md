# A–B–A r3: articulación de la antena externa de RX-01

Base Git `4cd768aeea090966777e95bc7df6aded2d8afbdf`. **Plan para revisión y
autorización futura; sin ejecución.** Protocolo [continuity-dual-1](CONTRATO_CONTINUIDAD_DUAL_1.md)
intacto. Esta revisión elige una intervención concreta y conserva los borradores
[r1](PLAN_ORIENTACION_ABA_CONTINUIDAD_R1.md) y [r2](PLAN_ORIENTACION_ABA_CONTINUIDAD_R2.md)
sin sobrescribirlos. No se ejecutarán sus JSON de giro de placa.

## Identidad e intervención

La [asociación confirmada](ASOCIACION_RX_FOTOS_CONFIRMADA_R1.md) identifica RX-01,
serie `5C93199744`, en `02_23_17 PM.jpg`, conectado al hub marrón; RX-02,
`5C93200689`, en `02_23_29 PM.jpg`, directamente a laptop. No cambiar ese cableado.
Las fotos identifican el montaje declarado, pero no certifican por sí solas el
estado A1 que habrá justo antes de medir.

Alan confirma articulación propia de la antena RX-01 y posibilidad de inclinarla
90° sin desenroscar. Se moverá **solo el cuerpo móvil de esa antena alrededor de
su articulación**. No se giran la placa, la base roscada/conector RF, el coaxial
ni el conector USB. No se ajusta otro eje para facilitar el cambio.

Quedan fijos placa/soporte, base/conector y punto de articulación RX-01, recorrido
y bucle del coaxial, cable/puerto USB, conjunto completo RX-02 (antena y cables
incluidos), TX, laptop, hub y objetos próximos. El extremo móvil de la antena
describe necesariamente un arco: no se promete mantener fijo todo el elemento
radiante ni aislar polarización de posición del cuerpo móvil.

## Definición y documentación previa de A1 y B

Antes de cualquier adquisición, completar el registro de montaje r3 sin mover
la antena: marcar en el soporte o croquis la ubicación de base/articulación, la
placa y los recorridos de coaxial/USB; usar referencias fijas de la mesa/laptop.
Describir el eje de la articulación, la dirección base→punta del cuerpo móvil
y su inclinación inicial. Registrar una vista lateral o croquis con esas
referencias; una foto oblicua sin referencia no mide por sí sola un ángulo.

**A1:** posición actual documentada de la antena, definida como 0° relativo.
No ponerla primero en otra postura «más conveniente». Confirmar antes de medir
que el registro representa su estado actual y que las partes fijas no cambiaron.

**B:** inclinación de **90° respecto de la dirección A1**, en el plano natural de
la articulación. El sentido propuesto se fija **hacia arriba, alejando el cuerpo
móvil de la superficie de apoyo**, con base, articulación y conexiones inmóviles.
No es +90° horario de placa visto desde arriba, ni un giro de la rosca o del
conector. Registrar en el croquis la dirección B perpendicular a A1 y el sentido
de movimiento antes de A1; no elegir entre sentidos tras ver resultados.

Si la articulación en su montaje actual no permite ese sentido/plano de 90° sin
tensión, obstáculos o desplazamiento de partes fijas, **detener la preparación
antes de A1 e informar el impedimento**. No girar la base, cambiar la postura A1,
recolocar el coaxial o usar otro ángulo para hacerlo viable: se revisaría el plan.
La declaración «90° sin desenroscar» no se toma como verificación automática de
todos esos requisitos. No efectuar una prueba de movimiento ahora.

**A2:** retorno por la misma articulación y recorrido angular inverso a las marcas
de A1. Documentar coincidencia con el eje inicial y conservación de placa, base,
coaxial y USB. No corregir ninguna pieza durante los 60 s.

## Tres intentos separados propuestos

| Orden | Identificador | Antena externa RX-01 | Duración común | Salida nueva reservada |
|---|---|---|---|---|
| 1 | CONT-ANT-ABA-R3-A1 | A actual documentada | 60 s | `results/local/continuidad-antena-aba-r3-A1` |
| 2 | CONT-ANT-ABA-R3-B | 90° relativo a A1, sentido fijado antes | 60 s | `results/local/continuidad-antena-aba-r3-B` |
| 3 | CONT-ANT-ABA-R3-A2 | Regreso a A inicial | 60 s | `results/local/continuidad-antena-aba-r3-A2` |

Cada intento tiene una sola apertura por RX y cierre comprobado de ambos:
tres aperturas por RX en total, separadas, sin reintentos ni reconexión USB.
Cada salida debe ser nueva; no reutilizar directorios ni completar intentos
fallidos con otra captura. Los 171/296 históricos no son el A1 de esta serie.
No hay slots o etiquetas de presencia ni autorización consumida nueva.

Los tres planes `config/continuidad_antena_aba_r3_{A1,B,A2}.review.json` y el
registro `config/continuidad_antena_aba_r3.montaje.review.json` son para revisión.
Las declaraciones PENDIENTE bloquean ejecución; no se ha creado comando físico,
orquestador automático o directorio de adquisición para esta serie. El registro
de montaje completado se conservará como artefacto nuevo y su hash se referenciará
en las declaraciones de los tres planes antes de abrir UART.

## Pasos futuros, solo tras autorización explícita

1. Resolver y documentar A1/B, ausencia de tensión y partes fijas. Confirmar
   alimentación actual, tapa/suspensión de laptop, ausencia de lectores/capturas
   y ambiente/contexto del operador. Mantener iguales esos factores en los tres
   intentos; no son etiquetas de presencia. Si no se puede confirmar inmovilidad
   de base/coaxial/placa, parar y comunicarlo, sin adquirir A1.
2. Con ambos UART cerrados, realizar únicamente preflight por metadatos. Mantener
   manos apartadas y 30 s de quietud antes de cada intento, también antes de A1;
   esa pausa queda fuera de los 60 s y no modifica el umbral CSI.
3. Ejecutar únicamente A1, sin tocar nada durante la adquisición. Esperar salida
   del proceso y verificar integridad/replay, duración, ausencia de fallo de
   transporte/almacenamiento y `both_ports_closed_confirmed=true`. Si falla alguna
   comprobación, detener la serie y conservar todo, sin repetir ni inclinar.
4. Solo después de ambos cierres, con el movimiento autorizado: cambiar únicamente
   la articulación móvil hasta B predefinida. No usar el coaxial o conector como
   palanca. Comprobar las referencias de todas las piezas fijas y registrar el
   resultado antes de medir B. Si aparece tensión o alguna parte fija se mueve,
   detener la preparación e informar; no continuar B ni recolocar para ocultarlo.
5. Aplicar la misma quietud/preflight y ejecutar B una sola vez. Verificar
   integridad y ambos cierres antes de tocar de nuevo la antena. Un silencio >1 s
   se registra y permite observar recuperación según continuity-dual-1; no es
   motivo para repetir B ni aprobación de calidad.
6. Solo con ambos cierres confirmados: regresar por la articulación a A1 y
   documentar A2. Si el retorno exige tensión o mueve base/coaxial, detener la
   preparación de A2 y comunicarlo. Aplicar la misma quietud/preflight, ejecutar
   A2 una sola vez y comprobar sus dos cierres. Conservar los tres bundles separados.
7. Ante fallo o cierre no confirmado no avanzar automáticamente ni hacer una
   reconexión/reset para resolverlo. Si una fase presenta al revisarse errores
   posteriores al arranque, perfil incompatible o discontinuidades, conservarlos
   y revisar antes de continuar; no cambiar la política de adquisición.

No desconectar USB o RF, resetear, pedir READY, cambiar firmware o puertos. Los
UART se reabren entre sesiones; el backend no garantiza ausencia de transitorios
eléctricos o arranque al abrir. Se conservan todos los bytes de inicio, errores,
lecturas y colas. No concatenar relojes locales o ids entre sesiones.

## Comparación offline fijada antes de adquirir

Comparar por identidad y A1/B/A2: filas completas y cobertura por 10 s; edades
de primera/última fila; distribución de huecos host/local (n, media, mediana,
p95/p99, máximo e histograma), incidencias >1 s y recuperación; ids/callbacks,
saltos/reinicios y queue_drops; RSSI descriptivo (n, mediana, p10/p90, rango) y
perfil CSI; bytes, fragmentos, servicio/read/persistencia/procesamiento y relojes.
Mostrar B frente a **ambos A** y la evolución paralela de RX-02. No rellenar
muestras, contar cabeceras incompletas o elegir recortes para mejorar el resultado.

RSSI solo describe filas recibidas y válidas; poblaciones con huecos diferentes
pueden estar sesgadas. Un cambio reversible en B con RX-02 estable apoyaría
dependencia de esta geometría de antena bajo las condiciones registradas; no
demostraría pérdida RF, polarización como única causa o qué capa produjo los
huecos históricos. A1/A2 diferentes o un cambio paralelo en RX-02 introducirían
alternativas temporales/comunes. Tres sesiones ordenadas no ofrecen replicación
de la serie ni demuestran precisión, significación o generalización.

Se mantienen perfil CSI, almacenamiento, incidencias de 1 s, watchdog v4 y
todos los resultados/rechazos anteriores. No se producen ventanas elegibles,
etiquetas, calibración, entrenamiento o producción. No se propone comprar equipo.

## Estado al presentar el plan

Confirmados por el operador: identidad fotográfica, articulación propia y giro
de 90° sin desenroscar. Pendientes antes de ejecutar: registro A1 y B con plano/
sentido definidos, confirmación de base/coaxial/placa fijos sin tensión para esa
maniobra, declaraciones actuales y autorización explícita para los tres intentos
y los dos movimientos entre ellos. Si la geometría no cumple esas condiciones,
la preparación se detiene; no se declara viable por observar solo las fotos.
No se abrió UART, movió equipo o ejecutó captura durante esta actualización.
