# Revisión r2: placa, antena externa y cables

Base Git: `4cd768aeea090966777e95bc7df6aded2d8afbdf`; revisión documental
posterior al [borrador r1](PLAN_ORIENTACION_ABA_CONTINUIDAD_R1.md), que se conserva
intacto junto a sus tres JSON revisables. **No aplicar el giro de placa de r1
como si definiera una orientación de antena.** Esta r2 queda para revisión,
con la maniobra B pendiente de definición y sin autorización de ejecución.

## Fuentes inspeccionadas y lo que permiten observar

Se localizaron exactamente dos coincidencias y se abrieron ambas:

- `/home/alan-monar/Downloads/ChatGPT Image Nov 3, 2026, 02_23_17 PM.jpg`
- `/home/alan-monar/Downloads/ChatGPT Image Nov 3, 2026, 02_23_29 PM.jpg`

Las imágenes aportadas por el operador muestran placas sobre soportes claros,
cables USB azules y antenas externas negras separadas de la placa, conectadas
por coaxial fino. La primera muestra un arco del coaxial; la segunda, un bucle
visible y la antena próxima al borde de la pantalla en el encuadre. Ambas tienen
objetos cercanos que forman parte del montaje y no deben reorganizarse durante
la comparación. La proximidad observada no identifica la causa de los huecos.

La declaración del operador confirma antenas externas en ambos RX y ausencia
de movimientos. No se distinguen etiquetas físicas suficientes para asociar
cada foto con RX-01/RX-02. Tampoco las fotos prueban el ángulo tridimensional,
longitudes libres, tolerancia de articulación, estado eléctrico de conectores,
selección RF efectiva o apertura/cierre UART. Los nombres no se usan como
prueba del momento de adquisición. Fotografías y brutos se mantienen sin editar;
sus hashes están registrados localmente en
`results/local/revision-orientacion-aba-r2/fuentes-antes.json`.

## Separación obligatoria de componentes

| Componente | Qué registrar en A1, B y A2 | Qué no se debe inferir |
|---|---|---|
| Placa RX-01 y soporte | Centro C, altura, cara, flecha USB→extremo opuesto, posición respecto de laptop y objetos | La flecha de la placa no es el eje de la antena externa |
| Antena externa RX-01 | Ubicación de base, eje base→punta, altura, inclinación y dirección respecto de una referencia fija; posición de articulación si existe | Un aspecto similar en una foto no garantiza igual orientación 3D o polarización efectiva |
| Coaxial fino y conexiones RF | Puntos de conexión, recorrido, bucle/curvas y holgura; conectores permanecen conectados | El coaxial no es una correa para girar placa o antena; la holgura USB no acredita holgura del coaxial |
| Cable y puerto USB RX-01 | Mismo cable/puerto físico y recorrido, con cualquier desviación anotada | Igual by-id no prueba que el puerto físico no haya cambiado |
| Conjunto RX-02 | Placa, antena, coaxial, USB y puerto se conservan como control | Mantener solo la placa RX-02 no basta si se desplaza su antena o cable |

Girar la placa dejando quieta su antena podría modificar su entorno y la curva
del coaxial/USB; no sería una comparación de orientación de antena. Girar ambos
conjuntamente cambiaría placa y antena y posiblemente ambos cables. En ninguno
de esos casos debe atribuirse el resultado exclusivamente al ángulo de antena.
La confirmación anterior de que RX-01 puede girar sin tensión no se extiende
automáticamente al coaxial y a su antena externa.

## Elegir una sola intervención B antes de cualquier medición

**Opción preferida si el objetivo es orientación de la antena:** placa y soporte
fijos, USB/puerto fijos, base y conexiones RF fijas; cambiar únicamente el ángulo
de la antena en una articulación propia, si existe y se confirma que permite
hacerlo sin girar el conector ni tirar/retorcer el coaxial. El operador todavía
no ha confirmado esa articulación. No se interpreta una pieza roscada como una
articulación ni se instruye aflojar o apretar conexiones RF.

A1 sería el eje y la posición actuales de esa antena; B, una inclinación o giro
con eje, sentido y ángulo concretos registrados previamente; A2, regreso a la
misma marca y articulación A. No se hereda el +90° horario de la placa propuesto
en r1: un cambio de inclinación de antena y un giro en planta son intervenciones
distintas. No se ha elegido ni confirmado un ángulo de antena a partir de las
fotos. Si la maniobra desplaza base, coaxial o soporte, debe revisarse como cambio
de geometría conjunta antes de autorizar, sin presentarlo como cambio aislado.

**Opción distinta si se quiere estudiar la placa:** conservar antena externa y
base en sus marcas y definir un giro de placa, documentando cualquier cambio
de coaxial/USB. Su viabilidad depende ahora de ambos cables. No se da por viable
el +90° de r1. El resultado evaluaría esa geometría de placa/cables con antena
externa fija; no equivaldría a estudiar orientación de antena.

No se mezclan ambas opciones en una serie ni se escoge la que produzca más filas.
La selección de componente, eje y ángulo debe cerrarse antes de A1. Si ninguna
es viable sin tensión, no se prepara una maniobra sustitutiva mediante desconexión.
No se proponen compras de instrumentos.

## Estructura A–B–A conservada, ejecución todavía pendiente

Se mantienen tres intentos independientes propuestos de 60 s con
`continuity-dual-1` sin cambios: A1 inicial, B definido antes de medir y A2 de
regreso. Cada uno tendrá una apertura por RX y su propio bundle nuevo. Los nombres,
planes y registros de montaje definitivos de r2 se prepararán una vez resueltas
las preguntas físicas; no se crean ahora JSON de ejecución, referencias de
autorización ni salidas de captura. Los JSON r1 conservan PENDIENTE y permanecen
bloqueados; no se completarán para ejecutar una intervención nueva sin revisión.

Los movimientos futuros, si se autorizan, ocurrirán exclusivamente entre intentos,
después de terminar el proceso y verificar integridad/replay y cierre de ambos
UART. RX-02 completo, TX, laptop y objetos cercanos permanecen fijos. Las pausas
operacionales de 30 s propuestas en r1 se aplicarían por igual antes de cada
intento, fuera del registro y sin modificar el umbral de incidencias.

Antes y después de la maniobra se registra placa, antena, base, articulación,
coaxial y USB por separado. La eventual instrucción física debe indicar qué pieza
se toca y qué marcas se conservan; no basta con «girar RX-01». Durante los 60 s
no se toca ningún componente. Si algo exige desconectar, cambia de posición
involuntariamente o aparece tensión, se detiene la preparación de la fase y se
revisa, sin reconexiones o reintentos para mejorar datos.

## Comparación y límites que siguen vigentes

Comparar por identidad y condición A1/B/A2 filas completas válidas, cobertura,
huecos host/local, incidentes y recuperación, ids/callbacks, queue_drops, RSSI,
perfil y tiempos de read/servicio/persistencia. Mostrar ambos A y el control
RX-02; conservar brutos, arranque y colas sin LF, sin contarlas como filas.
No concatenar relojes/ids entre intentos ni calibrar presencia con estos datos.

Un cambio reversible con RX-02 estable respaldaría dependencia de la geometría
que realmente se haya modificado. Coaxial, conectores, base y objetos próximos
son posibles factores si varían. No demuestra pérdida RF ni identifica placa,
firmware, cable, camino USB, filtrado o driver como causa de los 171/296 históricos.
Tres sesiones ordenadas siguen sujetas a deriva temporal, nuevas aperturas UART
y cambios de arranque no excluidos eléctricamente. No se alteran perfil CSI,
watchdog v4, resultados históricos o autorizaciones consumidas.

## Información pendiente para cerrar la revisión

1. **Resuelto:** asociación [confirmada por metadatos y seguimiento visual](ASOCIACION_RX_FOTOS_CONFIRMADA_R1.md):
   RX-01 = `02_23_17 PM` (hub marrón), RX-02 = `02_23_29 PM` (directo a laptop).
   El operador declara que no movió ni desconectó nada.
2. Indicar si la antena RX-01 tiene articulación propia utilizable sin tocar
   conexiones RF o tirar del coaxial, y qué parte puede moverse sin tensión.
3. Elegir placa o antena como intervención, fijar eje/sentido/ángulo y marcas
   reales antes de A1. La holgura de cada componente aún no se ha verificado.

No hay autorización física vigente para esta serie. No se ha ejecutado preflight,
abierto UART, movido equipos, desconectado antenas, modificado firmware o realizado
capturas durante esta revisión.
