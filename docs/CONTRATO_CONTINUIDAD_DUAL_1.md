# Diagnóstico dual de continuidad — continuity-dual-1

Contrato definido antes de implementar, desde 6450919618a8003a488c32e9d1925b84a9a80db3.
Preparación offline: no hay autorización física vigente. Es un diagnóstico
independiente de la campaña de presencia y de las políticas v4; no modifica sus
watchdogs, rechazos, datos ni autorizaciones consumidas.

- Una apertura preservando entrada por RX, identidades by-id y perfil CSI
  existentes. Sin comandos al dispositivo, resets, flush, reconexiones o
  reintentos. Las solicitudes DTR/RTS false no garantizan ausencia de transitorios.
- Duración nominal de observación dual de 60 s desde que ambos lectores están
  activos, con marcador y deadline explícitos. Se registra por separado el
  arranque anterior y cuándo queda abierto cada RX; RX-01 se drena mientras se
  abre RX-02. Si no se completa esa apertura dentro de 60 s se detiene (un open
  del sistema no es cancelable desde Python). No se espera READY ni se rearma
  un detector. Un error al abrir o adquirir detiene ambos.
- Cada RX tiene un lector independiente no bloqueante, sin stdin, que registra
  servicio, inicio/retorno de lectura y relojes MONOTONIC, BOOTTIME y REALTIME.
  Persistencia y análisis se serializan; sus esperas quedan medidas. No se
  interpreta el tiempo del host como tiempo RF de recepción.
- Más de 1 s desde apertura/última fila CSI completa y válida produce una
  incidencia, incluso si llegan bytes sin LF. Se conserva hasta recuperación o
  cierre, sin terminar por silencio ni aprobar calidad. Se distingue toda línea
  LF de una fila válida del perfil. Textos, resets, errores de firmware, perfiles
  incorrectos, saltos/reinicios de callback, reloj local y descartes se registran;
  no se aceptan como CSI ni se borran. El diagnóstico puede seguir observándolos.
- Errores de transporte, identidad o almacenamiento detienen adquisición y
  cierran ambos recursos una sola vez. Límites de almacenamiento heredados
  intactos: 100 MiB iniciales, reserva 32 MiB, brutos 64 MiB, bundle 256 MiB.
  Un bloque ya leído se conserva antes de comprobar su cruce del límite.
- Sin drenaje posterior al plazo: se conserva cualquier bloque cuya lectura ya
  había empezado, identificado por sus tiempos, y cualquier cola sin LF con
  offset, longitud, hash y referencias de lectura. No se completa artificialmente.
- Brutos, ledger append-only, metadatos, plan, autorización consumida, recibo de
  cierre, informe y manifiesto se crean exclusivamente en una salida nueva.
  Fsync antes de declarar persistencia; si falla no se promete integridad. El
  cierre confirmado exige fd y pipes realmente liberados para ambos RX.
- Un auditor offline verifica hashes, cobertura exacta del bruto por lecturas,
  orden/referencias y reproducción del informe. Integridad y cierre son resultados
  separados de finalización nominal; **nunca hay aprobación de calidad**, ventanas
  elegibles, etiquetas de presencia, calibración, entrenamiento o producción.

El intervalo entre callbacks válidos se compara por separado en MONOTONIC y en
el reloj local de 32 bits (microsegundos, módulo 2^32). Se informan diferencias de
id y queue_drops, sin llamar a sus saltos pérdida RF. Un hueco de servicio del
lector puede incluir planificación del host, espera de almacenamiento o CPU;
BOOTTIME−MONOTONIC ayuda a identificar una suspensión del sistema y REALTIME
puede mostrar ajustes de reloj. No mide dónde se acumularon bytes antes de read.
Sin instrumentación adicional no se distinguen con certeza ausencia de TX/RF,
callback, tarea/cola del firmware, UART, USB/driver y planificación del host.
Contadores de callbacks contiguos tampoco prueban continuidad RF.

Validación exigida antes de solicitar autorización: PTY propios con silencio y
recuperación, fragmentación sin LF, fallo de un RX y cierre de ambos; negativos
de identidad, almacenamiento, trazabilidad y reintento. Las pruebas sintéticas
no son evidencia física ni modifican resultados históricos.
