# Viabilidad del intercambio y alternativa con el equipo actual

Base: `4cd768aeea090966777e95bc7df6aded2d8afbdf`.
Estado: propuesta para revisión, sin autorización física ni ejecución preparada.

## Declaración actual del operador

Las tres ESP siguen conectadas y no han cambiado de posición. Los RX están a
cada lado de la laptop; ambos cables miden aproximadamente 20 cm. Alan no puede
confirmar que alcancen para intercambiar posiciones conservando cable y puerto.
La viabilidad del intercambio queda **dudosa**, no comprobada ni descartada.
No se ha hecho una prueba de desplazamiento ni se deduce alcance solo por la
longitud aproximada del cable.

No se prepara la ejecución A–B–A de intercambio: sin nuevos planes ejecutables,
salidas físicas, comandos de adquisición o referencias de autorización. Los
intentos anteriores y sus autorizaciones consumidas permanecen intactos.

## Alternativa preferida: sensibilidad a orientación local

Proponer una comparación de la orientación actual de RX-01 con otra orientación
que pudiera alcanzarse sin desplazar su centro marcado, desenchufar, tensar el
cable o forzar el conector. RX-02 serviría de control sin cambios. TX, laptop,
puertos, cables y firmware permanecerían fijos. Marcar posición y orientación
antes de cualquier movimiento futuro; no mover ahora para comprobarlo.

No se fija todavía un ángulo: con cables de 20 cm su viabilidad también necesita
confirmación. Si no puede girarse con holgura, esta alternativa queda pendiente;
no se sustituuye por un tirón del cable, reconexión o desplazamiento improvisado.
Antes de una futura ejecución habría que fijar un único cambio, registrar el
ángulo y el trayecto del cable, y revisar cómo comprobar su reversibilidad.

Esta comparación evaluaría dependencia de la geometría local, no el intercambio
de posiciones. Aunque el centro permanezca fijo, giran placa/antena y puede
variar el trayecto o acoplamiento del cable: no sería una medición aislada de la
antena ni demostraría pérdida RF. Un cambio reversible de filas/huecos/RSSI
apoyaría sensibilidad al montaje. Un resultado sin cambios no separaría
identidad de posición ni demostraría ausencia de dependencia espacial.

## Si se consideran desconexiones o cambios de puerto

Son alternativas conceptuales; ninguna acción de esta tabla está autorizada.

| Variante | Variables que cambiarían | Alcance de la conclusión |
|---|---|---|
| Desconectar y volver al mismo puerto, sin mover el RX | Alimentación USB del RX, nuevo arranque, estado volátil y conexión del host; cable/puerto/posición nominales permanecen | Una diferencia podría depender del arranque o conexión, sin identificar posición, placa o RF |
| Cambiar solo de puerto, manteniendo la posición si el cable lo permite | Puerto físico, posible ruta USB/controlador y condiciones de alimentación, nuevo arranque; puede cambiar el recorrido del cable | Una diferencia sugeriría dependencia del conjunto puerto/alimentación/arranque; no aislaría el controlador USB ni descartaría variación temporal |
| Intercambiar posiciones llevando cada RX su cable y conectándolo al puerto cercano del otro lado | Posición y puerto/ruta USB a la vez, alimentación/nuevo arranque y trayecto del cable; la orientación también cambiaría si no se controla | No permitiría distinguir posición de camino USB o arranque |

Ambos RX reciben alimentación por USB: desenchufarlos corta esa alimentación y
al reconectar se inicia de nuevo el firmware existente. Eso cambia ids de
callback, origen de reloj local y estado de colas; no equivale a conservar una
conexión ni a continuar el intento anterior. La ruta `/dev/ttyACM*` puede cambiar:
la asociación siempre debe verificarse por identidad by-id, conservando además
el registro del puerto físico. Un puerto físico distinto no implica por sí solo
que cambie de controlador USB; habría que comprobar su topología por metadatos.

Si el patrón siguiera a RX-01 después de un intercambio con cambio de puerto,
sería compatible con algo asociado a su identidad, incluido placa, firmware y
cable, pero no demostraría qué componente lo causa ni excluiría efectos del
arranque o de caminos USB aún no aislados. Si apareciera en la otra identidad en
la misma posición física, posición y puerto estarían confundidos: no se podría
atribuir exclusivamente al montaje. Ningún resultado de esas variantes por sí
solo demostraría pérdida RF.

Estas desconexiones y nuevos arranques requerirían una revisión del diseño y
autorización explícita específica antes de instruirlos. No se han indicado como
pasos operativos, ni se proponen compras de instrumentos.

## Comparación futura y límites comunes

Con `continuity-dual-1` sin cambios: comparar por identidad, posición marcada y
orientación las filas válidas sobre igual duración, distribución de huecos host
y locales, continuidad/reinicio de callbacks, queue_drops, perfil CSI y RSSI
(distribución descriptiva sobre filas completas válidas). Conservar brutos,
colas, cobertura temporal, servicio/read/persistencia e integridad/cierre.
Los fragmentos no se convierten en filas; RSSI solo describe muestras recibidas
y válidas, no las que no se observaron. No se modifica el perfil ni el umbral de
1 s, no se eligen recortes para mejorar el resultado ni se calibra presencia.

En un intercambio que sí preservara cable y puerto, un patrón ligado a la
identidad no separaría placa, firmware, cable y camino USB; un patrón ligado a
la posición sugeriría dependencia del montaje sin demostrar pérdida RF. Con el
equipo y alcance declarados, ese intercambio sigue sin viabilidad confirmada.

Registrar una observación futura tampoco eliminaría variación temporal del
entorno. La condición de orientación es una alternativa de menor alcance, no
un reemplazo equivalente del cruce por posición. Si no es viable ningún cambio
sin tensión, mantener el montaje; una eventual repetición estática solo mediría
repetibilidad, sin separar las causas. No se autoriza ni ejecuta tal repetición.

## Actualización posterior: giro declarado viable

Alan confirma que RX-01 puede girar en su posición sin tensar el cable. Se
prepara un [plan A–B–A de orientación para revisión](PLAN_ORIENTACION_ABA_CONTINUIDAD_R1.md),
con +90° horario propuesto como B, pendiente de confirmar ese ángulo y el plano
de apoyo antes de medir. La viabilidad del intercambio de posiciones sigue
dudosa. No se ha autorizado ni ejecutado la serie o un movimiento físico.
