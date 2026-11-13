# presence_persistent_v4 — contrato previo al código

Base: `51246df4f288ede695b81f8eca8336820e6cb126`. Diseño fijado antes de implementar. Solo memoria y PTY; sin autorización física, UART, calibración ni firmware nuevo. v1/v2/v3 y sus resultados no se modifican. Este contrato es una propuesta ejecutable offline para revisión, no permiso de campaña.

## Disponibilidad y fallos

Una sola conexión por identidad RX-01/5C93199744 y RX-02/5C93200689. READY estricto heredado (fuente, tag, canal 11, HT20, UART0=115200) una sola vez por conexión; después tres filas válidas consecutivas en ambos RX antes de A+10 s. No se solicita otro READY ni se supone que reabrir lo produzca. Si no se observa, se suspende y se cierra, sin reset o reconexión.

Para cada slot solicitado expresamente, demora mínima de 60 s: aviso de establecimiento a solicitud+30 s, seguido de al menos 30 s reales del reloj host para salir o adoptar S/W. Un aviso retrasado retrasa el inicio permitido; nunca lo adelanta. Al abrir el gate del slot se borran únicamente las referencias de su racha, nunca bytes ni continuidad. Se requieren tres filas NUEVAS por RX, primera lectura >= apertura del gate, callback +1, reloj uint32 con delta en [1,10000000] µs y descartes constantes; última LF de cada RX con edad <=1 s. El gate tiene un único plazo de 10 s, sin reiniciarlo. La decisión real fija T0 y T1=T0+30 s; T0 no se retrocede.

**Diferencia explícita de v4:** una vez lograda disponibilidad inicial, >1 s sin fila válida en cualquiera de los RX es pérdida de disponibilidad y suspende toda la conexión, también entre ventanas y durante la demora. No se presenta como desconexión física demostrada. v3 sigue sin umbral de silencio host dentro de su ventana. El criterio v4 es operativo, pendiente de comprobar, no calibración RF. Los huecos de callback, reloj local fuera de regla, cambios de descartes, READY duplicado/conflictivo, mensajes de reset/error, formato inválido posterior a READY, lector terminado, excepciones, fallo de almacenamiento/aviso/cierre e interrupciones suspenden sin rearmar. Un reset anterior al primer READY se conserva como arranque; un residuo inválido rechaza conexión y no se borra aunque posteriormente exista disponibilidad.

Los chunks se procesan completos antes de decidir; un reset al final del chunk impide usar su tercera fila. Las lecturas no bloqueantes se serializan en un único bucle; no hay colas de publicación de lectores. Evidencia con tiempos imposibles, regresión o publicación tardía contradictoria suspende y nunca cambia T0. Ningún timeout, fallo o etiqueta incierta genera reintento ni ventana sustitutiva. Se mantienen slots fallidos/no iniciados y se suspenden los siguientes.

## Registro íntegro y fronteras

Dos brutos append-only, uno por RX, desde apertura hasta fin de lectura. Cada lectura referencia RX, offset, longitud, SHA-256, inicio/retorno monotónicos; índices de líneas incluyen primera/última lectura y hash de TODOS sus bytes. Se conservan preámbulo, huecos entre slots, cabeceras, errores, filas fuera de ventana y colas finales. No se concatenan sesiones, exportan brutos recortados o eligen intervalos anteriores.

Cada slot referencia el mismo ID de conexión, su gate, evidencia de disponibilidad y T0/T1 inmutables. Inclusión: primera lectura >=T0 y retorno LF<T1. Filas que cruzan T0, terminan exactamente en T1 o después quedan registradas y excluidas. Los registros de eventos y el índice se derivan del bruto; un auditor vuelve a recorrer operaciones y bytes y comprueba hashes, offsets, resultados y manifiesto. La integridad auditada no prueba bytes que el driver nunca entregó, tiempo RF o ausencia física de reset sin indicadores observables.

En T1 no se cierran ni purgan puertos: continúa el mismo flujo. Una línea que cruza T1 queda completa en el bruto y fuera del slot. Para cerrar definitivamente se pide terminar solo una línea pendiente por RX, como máximo 250 ms/65536 bytes adicionales, sin retrasar T1; al agotar el límite se conserva la cola y se rechaza la parada. Un aborto cierra inmediatamente sin esperar LF. No se vacían buffers ni se pulsa reset.

## Cuatro calidades y etiqueta declarada

- `connection`: formato/continuidad de TODA la conexión, fallos y parada. Un fallo posterior no cambia los datos de una ventana anterior, pero impide declarar conexión global conforme o elegibilidad final de campaña.
- `window`: existencia, fronteras, formato/continuidad y finalización efectiva de cada intervalo; no acredita etiqueta ni cobertura suficiente. Una ventana puede tener datos conformes y conexión rechazada; se muestran ambos estados.
- `coverage`: por RX, mínimo una fila para el contrato básico; indicador piloto adicional fijo >=120 filas, >=15 en cada uno de seis bins de 5 s y huecos interiores/bordes <=500 ms. Los límites son prospectivos de v4 para revisión, no criterios aplicados a v3 ni demostración de observación RF continua. Timestamps repetidos se conservan, sin relleno.
- `label`: intención E/S/W, actor, montaje/hash y declaración posterior de establecimiento antes del aviso y continuidad hasta el aviso de fin. La escritura posterior no da la hora de transición. Sin declaración: pendiente; pérdida de aviso, entrada tardía, conversación/desviación relevante o duda: incierta. El software no deduce ocupación del CSI ni convierte el temporizador en verdad física.

Todas las ventanas que compartan conexión, visita y montaje deben agruparse en la misma partición futura. Son intervalos independientes en tiempo y referencias, **no sesiones estadísticamente independientes**. No se reutiliza automáticamente el reparto antiguo 12/6 de sesiones sobre filas de una conexión persistente. No se calibra el detector.

## Operación individual y avisos

Laptop y RX permanecen dentro, con el montaje y cables existentes, sin nuevos equipos o control remoto. El operador solicita un solo slot desde la laptop; dispone de 60 s o más para salir en E o establecer S/W. La laptop emite dos tonos cortos al aviso de establecimiento; la condición debe existir entonces y mantenerse hasta el aviso de fin. No se usa el sonido como estímulo durante [T0,T1).

El fin de ventana se registra al alcanzar T1. Tras un margen de 10 s se emite un tono corto: **VENTANA TERMINADA, CONEXIÓN TODAVÍA ABIERTA**. Permite regresar a declarar y solicitar el siguiente slot; no es autorización de sustituir uno fallido. En un slot marcado último antes de iniciarlo, tras ese margen se solicita cierre, sin inferir que haya ocurrido.

**Tres tonos largos: AMBOS PUERTOS CERRADOS CONFIRMADOS.** Solo después de detener las lecturas, ejecutar cierre de ambos recursos, comprobar su estado real cerrado y persistir un recibo con las dos confirmaciones y hashes. Un tiempo agotado, un hilo/proceso terminado o T1 no prueban cierre. Si un cierre falla se intenta el otro una sola vez, se conserva el fallo y NO se emite ese aviso. Ocho tonos rápidos indican fallo; aun con cierre logrado se distingue cierre confirmado de éxito de campaña. Aviso reproducido por software no significa oído: audibilidad desde el punto exterior/silla/recorrido y discriminación de patrones siguen pendientes físicos, sin UART.

La implementación offline usa recursos PTY propios e identifica toda evidencia como sintética. No acepta rutas UART ni ofrece backend físico. La promoción a transporte físico requiere revisión de identidades USB, apertura sin flush/DTR/RTS, persistencia/almacenamiento y autorización nueva. No se automatizan los 18 slots, no hay servidor o dashboard. El plan concreto de revisión y los resultados de pruebas se añadirán al finalizar.

## Implementación entregada y revisión

El [plan concreto de revisión](PLAN_REVISION_CAMPAÑA_PERSISTENTE_V4.md) describe operación local, ejemplo sintético, práctica manual y particiones por conexión. [Resultados reales de las verificaciones](../results/PRESENCIA_PERSISTENTE_V4.md).

- `persistent_presence_v4.py`: máquina de estados pura, contrato fijo, slots solicitados de uno en uno, cobertura y declaraciones separadas.
- `presence_v4_journal.py`: brutos/operaciones append-only con flush/fsync, recibo de cierre enlazado al prefijo del journal, manifiesto final y replay de entradas/bytes. Los eventos derivados y el resumen deben coincidir; rehashear un resultado falso no basta para aprobarlo.
- `presence_v4_pty.py`: un bucle lector no bloqueante, dos PTY propios, sin rutas de dispositivos físicos; cierre una sola vez por RX y confirmación mediante `fstat`/`EBADF` tras `os.close`. El cleanup de recursos sintéticos del fixture no se publica como un segundo intento de cierre del protocolo.
- `presence_v4_audio.py`: WAV distintos y reproductor opcional en un hilo independiente del lector. Un retorno satisfactorio solo acredita software de reproducción, nunca audición humana.
- `tools/campana_presencia_v4.py`: preparación por defecto sin dispositivos, demo PTY explícita, práctica de operador PTY local, exportación de sonidos sin reproducir y auditoría offline. La demo solo automatiza entradas del fixture sintético, no slots físicos.

Mensajes informativos no neutrales después de READY también suspenden v4, sin atribuirles una causa física. Al iniciar, una racha caducada se descarta como evidencia de disponibilidad, conservando sus bytes. Tras la disponibilidad inicial, el watchdog permanece activo entre slots. Cobertura piloto insuficiente o etiqueta incierta suspenden, pero se informan aparte de formato/continuidad de la conexión y de la calidad de los datos de ventana. Un fallo de almacenamiento impide emitir éxito/recibo durable y aun así se intentan ambos cierres.

El fin de ventana no tiene política de parada UART: las lecturas continúan hasta la siguiente solicitud o cierre de conexión. La política de 250 ms/65536 bytes se aplica únicamente al cierre final. No se promete tiempo real duro, sincronización RF, identificación causal de cada reset, recuperación de bytes no entregados por el driver o duración infinita sin límites de almacenamiento/memoria. Antes de promover transporte real se revisará el presupuesto del host para toda la visita y se fijarán huellas de configuración/código/montaje.
