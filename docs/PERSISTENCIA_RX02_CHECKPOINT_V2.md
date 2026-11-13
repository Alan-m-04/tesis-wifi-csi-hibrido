# RX-02: revisión optativa de persistencia por checkpoints

Identificador: `rx02-raw-sync-control-checkpoint-2`. Es una revisión del camino
de persistencia, no del firmware, perfil CSI, frescura, cobertura, etiquetas o
elegibilidad. Se implementa en `src/rx02_checkpoint_journal.py`; los módulos
históricos y los planes C01–C06 permanecen intactos.

## Cambio mínimo y activación

El journal histórico escribe, flush y fsync por cada chunk y **por cada
operación**, incluidos ticks sin cambios y controles de almacenamiento. La
revisión 2 mantiene intacto el primer requisito y amortiza únicamente el
segundo. No agrega hilos de escritura/lectura, colas asíncronas, descarte de
datos, interpolación, rearme ni tolerancia de errores.

`CheckpointRx02Session` hereda el transporte, lock, control de errores y cierre
existentes. Después del `begin/opened` histórico, instala un decorador sobre el
mismo journal y mismos descriptores, antes del bucle de servicio. Exige el campo
explícito `persistence_revision` con el identificador anterior. Escribe una
política nueva durable con hashes de su fuente y del plan. Si falla la
activación, se registra el error y se cierra el recurso ya adquirido.

**El CLI físico existente no se cambia ni se activa esta variante de forma
implícita.** No se creó un plan de adquisición o autorización nuevos. Su uso
físico futuro necesita integración/revisión explícita; aquí se ejecuta solo
mediante el laboratorio PTY con datos inventados y reloj real.

## Garantías por operación

1. **Chunk bruto:** se escribe completo, se comprueba escritura corta, se hace
   flush/fsync y solo después se toma la muestra de decisión y se aplica el
   reductor. Se conservan offset, tamaño, hash, primera lectura y retorno
   originales. No se retrocede el reloj de decisión ni se declara que recibir
   un fragmento equivale a recibir una fila válida.
2. **Operaciones:** cada registro se serializa y escribe/flush en orden. El
   sufijo desde el último checkpoint exitoso queda limitado a **65.536 bytes**.
   Antes de excederlo se hace fsync del prefijo anterior; un registro individual
   de más de 16.384 bytes detiene la sesión, sin crear un bundle aprobado.
3. **Barreras explícitas:** `begin`, `opened`, `request`, `declare`,
   `interrupt`, `io_error`, `storage_error`, `reader_ended`, `close_request`
   y `closed` hacen checkpoint antes de devolver éxito. Los dos primeros se
   ejecutan inicialmente con la garantía histórica aún más estricta.
4. **Ticks y controles de espacio:** escriben/flush sin fsync propio salvo
   alcanzar la cota. Disponibilidad, T0/T1, estados de ventana y avisos emitidos
   desde ticks pueden ser **provisionales respecto de durabilidad** hasta una
   barrera posterior. No son aprobación de una captura incompleta.
5. **Cierre:** el retorno del cierre/fd y el estado del lector siguen siendo
   la prueba, no un temporizador. Se hace checkpoint antes del recibo original,
   que conserva su prefijo de operaciones y hash del bruto. La señal
   `selected_port_closed_confirmed` sigue bloqueada hasta que el recibo durable
   exista. No afirma haber cerrado RX-01.
6. **Finalización:** checkpoint de todas las operaciones, estado final nuevo
   con longitud/hash/prefijo durable y límites; después los archivos y
   manifiesto originales. No hay escritor pendiente que pueda seguir cambiando
   el bundle. La auditoría específica comprueba esas pruebas y reproduce el
   auditor/reductor histórico completo antes de certificar elegibilidad.

Los límites contractuales previos de espacio, bruto, bundle, duración de
conexión y drenaje de cierre se conservan. No se promete un máximo de tiempo
para un write, fsync, cierre del driver o planificación del sistema; la espera
de drenaje acotada no es una garantía de latencia total del sistema operativo.

## Interrupciones y fallos

**Salida normal o interrupción gestionada:** antes de crear un manifiesto
completo se sincronizan los datos y operaciones disponibles y se conserva su
replay. Una interrupción activa conserva su rechazo; no termina una ventana
o etiqueta por el operador. El recibo se refiere al cierre real y no convierte
el resultado en conforme.

**Muerte abrupta del proceso o caída de energía:** puede quedar un prefijo
incompleto, un registro truncado y bruto durable por delante del journal.
Hasta 65.536 bytes de operaciones posteriores al último checkpoint exitoso
pueden no haber alcanzado almacenamiento estable. El último checkpoint no se
publica como watermark durable independiente en cada barrera; no se promete
reconstruir su frontera desde un directorio incompleto. La cota se refiere al
sufijo de operaciones, no al tiempo transcurrido o a la supervivencia de todo
el namespace/directorio tras pérdida eléctrica. Las garantías dependen de que
kernel/filesystem/dispositivo honren fsync; se conserva el comportamiento de
creación/directorios de la base y no se garantiza recuperación tras corte de
energía. **Sin manifiesto final íntegro y replay no hay bundle elegible.**
No se completa un JSON, una fila o un LF para recuperarlo como aprobado.

La prueba con SIGKILL demuestra preservación observable y ausencia de aprobación
tras **muerte de proceso**, no simula pérdida de alimentación o caché del disco.

**Error de escritura/fsync/espacio, escritura corta o agotamiento de recursos:**
se detiene la aceptación y se libera RX-02. Si el error impide hacer durable
el cierre, no se crea recibo/señal de cierre confirmado ni manifiesto de éxito,
aunque el fd se haya liberado. Los archivos parciales se conservan. Un chunk
que supera una cota de historia se guarda/fsync primero y se conserva su
referencia en `resource-limit.json` cuando el almacenamiento aún funciona;
no se aplica al reductor ni se elimina del bruto. No hay reintento automático.

## Memoria y trabajo acotados

No existe una cola nueva de entrada o persistencia. Se mantienen cotas explícitas
de 16.384 bytes por chunk/registro, 65.536 bytes de sufijo de operaciones,
25.000 líneas retenidas, 100.000 eventos y 500.000 operaciones por sesión.
Se reserva conservadoramente el peor número de líneas que puede añadir un
chunk, antes de expandirlo en estructuras. Alcanzar una cota detiene, nunca
elimina historia para seguir adquiriendo. Estas son cotas de recursos del nuevo
runtime; no cambian umbrales CSI ni permiten aprobar datos históricos distintos.

El techo es por tamaños/cuentas de estructuras, no una promesa de RSS exacto
en bytes para todas las versiones de Python. El resumen final y la auditoría
siguen materializando estructuras bajo los límites de conexión/bundle, fuera
del servicio UART. El ensayo registra RSS, CPU, fds, hilos, tamaños y cuentas;
no extrapola un pico observado a una garantía general del sistema.

## Trazabilidad y compatibilidad

El formato de bytes y registros conserva el schema RX-02 v1. Los archivos
adicionales `persistence-policy.json` y `checkpoint-status.json` quedan cubiertos
por el manifiesto final. Para reclamar la revisión 2 se exige
`audit_checkpoint_rx02`: valida revisión, fuentes, límites, contador final,
hash/longitud de operaciones y ausencia de sufijo pendiente, además de la
auditoría histórica sin cambios. El auditor histórico por sí solo puede
comprobar formato/replay, pero no certifica la nueva política de durabilidad.

C01 y C02 se auditan exclusivamente con sus fuentes/contrato históricos y
conservan sus rechazos, etiquetas, colas, cierres y autorizaciones consumidas.
La variante nueva no se aplica retrospectivamente ni habilita una adquisición.
