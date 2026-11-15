# Preparación diagnóstica RX-02 / checkpoints R1

Estado: preparado offline, sin autorización física, sin preflight físico.
Las tres ESP siguen desconectadas según el operador. No conectar hasta la
instrucción del siguiente paso. Las declaraciones actuales están pendientes.

Base revisada: feat/backend-uart-presencia-v4, HEAD y remoto
1bb7619f798fe92721d33b25d1e6694bae420897; árbol limpio antes de preparar.
CONTINUACION.md y contrato PERSISTENCIA_RX02_CHECKPOINT_V2.md leídos.

## Plan prospectivo

Identidad RX02-DIAG-CP-R1, grupo completo independiente diagnostic_only.
240 s desde el registro de apertura de RX-02 hasta solicitar cierre; no desde
READY ni desde una ventana seleccionada después. Fallo previo cierra temprano.
Las llamadas síncronas pueden exceder el plazo: no se garantiza duración máxima
de write/fsync/driver ni se fuerza el cierre basándose solo en un temporizador.
Una sola apertura, cero reintentos, sin resets deliberados, firmware, calibración
o entrenamiento. RX-01 permanece desconectada y su UART no se consulta ni abre.
TX-01 solo alimentada, según declaración pendiente. No se solicita ningún slot
E/S ni se declaran etiquetas. La condición ambiental es una declaración humana.

Plan revisable: config/diagnostico_checkpoints_rx02_r1.review.json.
Plan local independiente: results/local/preparacion-rx02-diagnostico-checkpoints-r1/plan.local.json.
Salida reservada, todavía inexistente: results/local/diagnostico-checkpoints-rx02-r1.
No es C03 ni reemplazo de C02. No cambia particiones o elegibilidad histórica.

## Criterios fijados antes de adquirir

- READY/arranque estricto heredado y disponibilidad inicial dentro de 10 s;
  tres filas nuevas con frescura de 1 s. El watchdog de 1 s sigue sin cambios:
  availability_gap/availability_lost detienen, sin rearme.
- Servicio sostenido: alcanzar 240 s desde apertura, disponibilidad conseguida,
  sin fatal al cierre/finalización. No mover el origen ni repetir para aprobar.
- Integridad: manifiesto con todos los archivos, hashes/tamaños, fuentes y
  referencias brutas contiguas; replay exacto de estado y eventos.
- Identidad RX-02 5C93200689/by-id, configuración 115200 y evidencias de espacio
  verificadas por el auditor; mismo perfil CSI y las mismas políticas históricas.
- Checkpoints: bruto completo write/flush/fsync antes del reductor; operaciones
  con sufijo máximo 65536 bytes, barreras de control y pendiente final cero;
  hash/longitud y última secuencia durable comprobados por auditor específico.
- Cierre: exactamente una apertura y un cierre, fd liberado, lector detenido,
  recibo durable y señal subordinada al recibo. Cola sin LF se conserva, no es CSI.
  El drenaje conserva 250 ms/65536 bytes; no garantiza la latencia del driver.
- Calidad estricta de conexión se informa por separado. Un preámbulo rechazado
  no se recorta ni se convierte en calidad conforme por completar el servicio.
  Sin ventanas no se evalúa cobertura E/S de 500 ms/120 filas/15 por bin; esos
  umbrales se mantienen idénticos y no se usan para aprobar una ventana inexistente.
- Permitted uses: calibración=false, entrenamiento=false, producción=false.
  El diagnóstico no acredita causa única de C02, estabilidad general o precisión.

Pueden perderse/truncarse hasta 65536 bytes de operaciones tras caída abrupta;
no hay garantía temporal de fsync ni recuperación tras corte eléctrico. Sin
manifiesto íntegro y replay no se aprueba un prefijo parcial.

## Separación de código y evidencia

Las 18 fuentes históricas de auditoría permanecen intactas. El paquete nuevo
src/rx02_diagnostic deriva explícitamente de contract/journal/uart/checkpoint
RX-02 de 1bb7619. Es una bifurcación deliberada para no cambiar los hashes que
exigen C01/C02: cambia contrato, dependencias, esquema y procedencia; conserva
el algoritmo de checkpoints y el ciclo de transporte/cierre. No hay parche de
globales ni suplantación temporal de un identificador C01 dentro del runtime.
El nuevo manifiesto registra también las seis fuentes diagnósticas nuevas.
La duplicación debe mantenerse revisada frente a cualquier futura corrección;
no constituye una migración de los CLI históricos.

originales-antes.json fija hashes de bundles, autorizaciones y planes C01/C02.
No se copian autorizaciones consumidas al plan diagnóstico. La autorización
física futura deberá ser explícita y vincularse al hash del plan final.

## Secuencia pendiente, un paso cada vez

1. Recibir en un mensaje las condiciones actuales solicitadas y completar el
   plan sin inventarlas. Confirmar RX-01 desconectada, potencia TX conocida o
   desconocida, montaje, ocupación, laptop, lectores ausentes y audio.
2. Dar instrucción concreta para conectar TX-01 y RX-02 una sola vez según esa
   alimentación, dejando RX-01 desconectada. Conectar alimentación provoca el
   arranque normal; no pedir reset posterior para recuperar READY. El software
   solicita DTR/RTS false, pero no promete ausencia de transitorios eléctricos.
3. Desde la terminal del operador, exclusivamente metadatos:

   .venv/bin/python -B tools/diagnostico_checkpoints_rx02.py --plan results/local/preparacion-rx02-diagnostico-checkpoints-r1/plan.local.json --preflight-only

   Este comando todavía rechaza declaraciones pendientes. No ejecutarlo ahora.
   Guarda preflight.json nuevo y no lo sobrescribe. No construye Serial ni
   lee UART. La adquisición vuelve a comparar las identidades y condiciones;
   un cambio aborta. El preflight no demuestra recepción futura de READY.
4. Revisar el resultado; presentar plan final, hash y comando exacto con
   autorización concreta para un único intento. No solicitar esa autorización
   antes de disponer de condiciones y preflight revisados.
5. Solo tras autorización humana, registrar autorización nueva y preparar la
   invocación --execute-after-approval --authorization-reference RX02-DIAG-CP-R1:HASH
   --output-new results/local/diagnostico-checkpoints-rx02-r1.
   HASH es el SHA256 del plan final autorizado: no es un comando listo ahora.
   El CLI rechaza authorization_granted=false, referencia distinta, condiciones
   cambiadas, preflight ausente y salida existente. Consume antes de abrir y
   no hay opción CLI para backend sintético, otro ID, otra salida o reintento.
6. Observar continuidad sin manipular placas; Ctrl-C solicita interrupción y
   conserva rechazo, sin repetir. Revisar recibo real antes de desconectar.
7. Auditar offline y documentar todos los rechazos, colas y límites.

La única invocación lista ahora es preparación sin acceso a metadatos:

.venv/bin/python -B tools/diagnostico_checkpoints_rx02.py --plan results/local/preparacion-rx02-diagnostico-checkpoints-r1/plan.local.json

## Verificación offline de esta preparación

444 pruebas aprobadas: 433 históricas y 11 diagnósticas, cero fallos, errores u
omisiones; 44,107 s. Bubblewrap activo con /dev privado, red aislada, repo y
solo tres fotografías históricas externas montados en lectura. Se indicó la
referencia física ya existente; no se adquirieron datos. El primer pase
439/1 error/3 omisiones se conserva en pruebas-primer-pase.json: acceso a fotos
y variable de referencia ausentes en el wrapper genérico, resueltos al montar
las entradas precisas sin modificar las pruebas ni sus criterios.

El caso sintético de duración usa PTY propio y reloj escalonado: representa
240 s lógicos y 1200 filas inventadas; no es un ensayo físico ni una medición
real de cuatro minutos de rendimiento. Incluye el bucle del nuevo lanzador,
checkpoint final, replay y cierre; también se probaron fallo de fsync,
watchdog, cierre temprano, datos alterados y barreras de autorización/preflight.

38 archivos protegidos reverificados sin cambios (incluyen bundles, planes y
autorizaciones C01/C02). Ningún archivo previamente versionado se modificó.
Las clases de reductor, transporte, notificador y checkpoints derivadas se
compararon por AST y conservan sus algoritmos. No se hizo commit ni push.
HEAD/remoto siguen en 1bb7619f798fe92721d33b25d1e6694bae420897.

Evidencias: pruebas.json, pruebas.stdout.txt, pruebas.stderr.txt,
verificacion-offline.json, fuentes-plan-sha256.json y originales-antes.json en
results/local/preparacion-rx02-diagnostico-checkpoints-r1/.
Continúan pendientes condiciones, conexión indicada al operador, preflight
por metadatos y autorización humana nueva. No existe aún directorio de
adquisición ni recibo de autorización diagnóstica consumida.

## Actualización: condiciones actuales recibidas

Alan reconfirma posiciones/antenas anteriores, TX a algo más de 2 m y RX-02 a
la derecha; solo y sentado quieto unos cinco minutos; puerta/ventanas cerradas,
sin ventilador ni terceros. Laptop enchufada y abierta, suspensión desactivada,
otros lectores cerrados; misma salida y volumen de PRUEBA02. TX se alimentará
con cargador de pared y RX-02 con USB directo; RX-01 permanecerá desconectada.
Sin cambios declarados de firmware, cables, puertos o antenas. Potencia TX no
medida: no se interpreta como comprobada. Estas son declaraciones humanas.

Se completa solo plan.local.json; la plantilla review y el plan previo se
conservan. execution_mode=physical_after_approval habilita la validación de las
condiciones para preflight; authorization_granted=false y estado
conditions_complete_not_authorized mantienen bloqueada la adquisición.
No se ha ejecutado preflight ni abierto UART. Se verifica que intentar ejecutar
sin grant rechaza antes de consultar metadatos o construir una sesión.

Siguiente paso: indicar al operador conectar TX-01 al cargador de pared y
RX-02 al USB directo previsto, dejando RX-01 desconectada y los lectores
cerrados. Esperar confirmación de conexión antes de dar el comando de preflight
por metadatos. No pedir reset ni reconexión posterior para recuperar READY.

## Cierre posterior del único intento físico autorizado

El operador ejecutó el intento y reportó DIAGNOSTICO_EXIT_CODE=0. La auditoría
offline confirma 240,007883569 s hasta inicio de cierre, 1190 filas, integridad/
replay, 76 checkpoints, pendiente cero, cola cero y cierre RX-02 confirmado.
La calidad estricta sigue rechazada por preámbulo; autorización consumida, sin
permiso físico restante. Resultado y comparación con C02 en
results/RX02_DIAG_CP_R1.md. 450 pruebas aisladas aprobadas, sin omisiones.
Los estados anteriores se conservan como historia; el grant capturado no
autoriza otro intento. C03 solo tiene un borrador offline nuevo para revisión.
