# C03: integración física optativa de checkpoints

Base revisada: b3b5fc73223069a970f56c8a565abe6add39886e, rama
feat/backend-uart-presencia-v4, árbol limpio al comenzar. Se implementa la
ruta solicitada sin abrir UART, adquirir, calibrar o entrenar. Las condiciones
actuales siguen pendientes de confirmación agrupada antes de preflight.

## Selección explícita y compatibilidad

Entrada nueva: tools/campana_rx02_checkpoint.py. Si el plan no contiene
persistence_revision ni integration_revision, delega al CLI histórico sin
alterar su sesión, validación, preparación, auditoría o comportamiento físico.
Una revisión desconocida/null o integración sin persistencia falla antes de
consultar dispositivos: nunca se degrada silenciosamente a fsync histórico.
Los CLI anteriores permanecen intactos; no activan checkpoints por añadir un
campo al plan. Para C03 optativa se exige la entrada nueva.

La selección explícita requiere simultáneamente:

- persistence_revision=rx02-raw-sync-control-checkpoint-2.
- integration_revision=rx02-c03-checkpoint-entry-1.
- Conexión y grupo RX02-C03; partición completa development_future; E→S.
- output_new=results/local/piloto-rx02-r1-C03-checkpoint-r1, todavía inexistente.

La clase C03CheckpointSession usa directamente el CheckpointJournal histórico
sin cambiar algoritmo, límites o barreras. Antes de abrir, C03Journal escribe
plan/procedencia durables con ambas revisiones y hashes de 25 fuentes: las
18 históricas, checkpoint original, cinco módulos nuevos y el CLI nuevo.
Después de opened se instala el decorador antes de aceptar datos, como en su
contrato original; begin/opened retienen la garantía histórica más estricta.
Fallo de activación conserva evidencia y libera recurso, sin repetir.

La auditoría seleccionada por plan es audit_c03_checkpoints. Exige ambas
revisiones en plan/procedencia, las fuentes exactas, replay de eventos/estado,
referencias contiguas al bruto, recibo real de cierre, manifiesto completo y
runtime de persistencia explícito. Verifica checkpoint-status.json y
persistence-policy.json, hash/longitud/secuencia final y sufijo pendiente cero.
La auditoría histórica no certifica este bundle con fuentes adicionales.
El nuevo auditor tampoco convierte un bundle sin checkpoints en conforme.

Las fuentes históricas y las seis fuentes congeladas del diagnóstico físico
no se editan: así C01, C02 y RX02-DIAG-CP-R1 siguen auditándose con sus hashes
originales. Los adaptadores C03 derivan del constructor de reductor, journal y
transporte originales, con validación/procedencia/grant nuevos; heredan
apply, summary, validate_request, close_ack y selected_closed sin cambios.
La duplicación acotada de inicialización/transporte conserva compatibilidad de
fuentes; futuras correcciones deben revisarse explícitamente en ambas rutas.

## Invariantes físicos y de campaña

No cambian READY/arranque estricto, disponibilidad inicial de tres filas nuevas
en 10 s, frescura de 1 s, demoras/avisos de 60/30/30 s y margen final de 10 s.
Ventanas prospectivas de 30 s: C03-E primero, C03-S segundo y último; mínimo
120 filas, 15 por bin de 5 s y hueco máximo 500 ms. Etiquetas declaradas por
operador, barreras temporales conservadoras, sin aprobación de preámbulo por
recorte, ni entrenamiento/calibración/producción.

Se mantienen cierre de 250 ms/65536 bytes y todas las cotas de espacio/memoria.
El retorno de close y liberación de fd prueban cierre; el aviso requiere recibo
durable. No se garantizan duraciones máximas de fsync/driver ni recuperación
tras corte eléctrico. Hasta 65536 bytes de operaciones pueden perderse o
truncarse tras muerte abrupta; un prefijo sin manifiesto/replay no se aprueba.
No hay escritor asíncrono, nuevos hilos/colas, resets deliberados o reintentos.
DTR/RTS solicitados false no acreditan ausencia de transitorios eléctricos.

Solo en esta revisión C03 se admite declarar RX-01
remain_disconnected_uart_unopened. El plan, procedencia y replay conservan esa
disposición real sin transformarla en conectada ni fabricar cierre/lectura.
También se conserva la disposición histórica conectada/fija con UART cerrada
si se declarase explícitamente. El borrador nuevo propone desconectada; falta
confirmación actual. RX-01 no se consulta por USB ni abre en el preflight.

C02 sigue rechazada por availability_gap:RX-02, etiqueta pending, cola de349
bytes, partición y autorización consumida; no se reemplaza o reclasifica.
El diagnóstico de 240 s conserva su resultado, rechazo de preámbulo y permiso
consumido. Ninguna de esas autorizaciones habilita C03.

## Plan, salida y comandos para revisión

Plantilla nueva: config/piloto_rx02_C03_checkpoint2.integrated.review.json.
Plan local nuevo: results/local/preparacion-C03-checkpoint-r1/plan.local.json.
Salida exclusiva reservada, sin crear: results/local/piloto-rx02-r1-C03-checkpoint-r1.
La plantilla de revisión anterior y los planes C01–C06 se conservan intactos.
El plan local tiene execution_mode=physical_after_approval para validar sus
condiciones futuras, pero authorization_granted=false y ninguna autorización
física registrada. Las declaraciones PENDIENTE son intencionales.

Comando concreto y seguro para revisar la selección, sin metadatos ni UART:

```bash
.venv/bin/python -B tools/campana_rx02_checkpoint.py \
  --plan results/local/preparacion-C03-checkpoint-r1/plan.local.json
```

Debe devolver PREPARED_NOT_AUTHORIZED, C03CheckpointSession y
audit_c03_checkpoints, ambas revisiones, hash del plan y salida exclusiva.

Tras completar condiciones actuales, el único paso físico preparatorio será
este preflight por metadatos (todavía no ejecutado):

```bash
.venv/bin/python -B tools/campana_rx02_checkpoint.py \
  --plan results/local/preparacion-C03-checkpoint-r1/plan.local.json \
  --preflight-only
```

Rechaza declaraciones pendientes; verifica identidad by-id/udev/stat/permisos
RX-02 y guarda preflight.json nuevo. No construye Serial, hace ioctl, lee CSI,
resetea o modifica dispositivos. El recibo enlaza condiciones, revisiones y
fuentes. No se sobrescribe. Si este entorno no ve los nodos, se ejecutará desde
la terminal del operador y se revisarán stdout/código de retorno.

Solo después de revisar el preflight se presentará el comando físico final
con hash y se solicitará autorización nueva. Su forma será:

```text
.venv/bin/python -B tools/campana_rx02_checkpoint.py
  --plan results/local/preparacion-C03-checkpoint-r1/plan.local.json
  --execute-after-approval
  --authorization-reference RX02-C03-CHECKPOINT-R1:SHA_DEL_PLAN_FINAL_AUTORIZADO
  --output-new results/local/piloto-rx02-r1-C03-checkpoint-r1
```

Esta forma no es una autorización ni un comando listo para ejecutar: el hash
exacto no puede fijarse antes de recibir las condiciones actuales. La entrada
rechaza grant false, review_only true, estado no autorizado, referencia distinta,
preflight ausente/cambiado, identidad cambiada y salida existente/alternativa.
El constructor físico repite el gate de grant/ref antes de consultar USB y la
sesión consume el permiso antes de intentar abrir. No se crea dossier físico
ni se cambia el grant durante esta preparación.

La operación futura reutiliza los mismos comandos manuales slot/declare/close/
abort del CLI histórico; no solicita automáticamente E/S. Una sola apertura;
slot RX02-C03-E, declaración humana posterior, slot RX02-C03-S last y declaración
posterior solo cuando corresponda. Esto no se ejecuta en esta preparación.

## Condiciones solicitadas en una única consulta

Estado actual de conexiones/reset/cambios y RX-01; montaje/distancia/antenas;
alimentación y potencia TX medida o desconocida; posibilidad de E vacío primero
y S sentado último con salida, demoras y avisos, ambiente/terceros; laptop,
suspensión, lectores y audibilidad PRUEBA02. No se pide manipular placas antes
de esa respuesta. El plan se completará con declaraciones humanas, sin inventar
ni dar por vigentes automáticamente las del diagnóstico.
