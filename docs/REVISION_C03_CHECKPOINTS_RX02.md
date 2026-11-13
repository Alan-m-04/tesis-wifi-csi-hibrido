# C03: revisión actual tras integración optativa

La [integración nueva](INTEGRACION_C03_CHECKPOINTS_RX02.md) añade selección
explícita de checkpoints en tools/campana_rx02_checkpoint.py, plan/procedencia/
auditoría y salida exclusiva, conservando por defecto la ruta histórica.
E→S, grupo/partición C03 y todos los criterios se mantienen. La variante nueva
puede declarar RX-01 desconectada sin falsear su estado. Las condiciones
actuales se solicitan agrupadas; no hay preflight físico ni autorización nueva.

El plan integrado es config/piloto_rx02_C03_checkpoint2.integrated.review.json;
el borrador anterior de este documento se conserva como antecedente.
No abrir UART, adquirir, calibrar o entrenar durante esta preparación.

## Antecedente: borrador previo en b3b5fc7

# C03 con checkpoints — únicamente para revisión

El diagnóstico RX02-DIAG-CP-R1 completó 240 s sin suspensión y con persistencia,
replay y cierre confirmados, conservando rechazo estricto por preámbulo. Eso
permite revisar el siguiente paso; no acredita elegibilidad de ventanas E/S.
C02 no se reemplaza ni se relabela. Su rechazo, cola, partición y autorización
consumida permanecen intactos.

El [borrador nuevo](../config/piloto_rx02_C03_checkpoint2.review.json) conserva
RX02-C03, grupo completo RX02-C03 y partición development_future; no se divide
por filas/ventanas ni se cambian C01–C06. Orden prospectivo: RX02-C03-E primero,
RX02-C03-S segundo y último. Ambas ventanas de 30 s compartirían una conexión
RX-02; no son repeticiones independientes ni un reemplazo automático.

Selecciona explícitamente persistence_revision=rx02-raw-sync-control-checkpoint-2.
Mantiene READY/arranque estricto, tres filas nuevas y disponibilidad en 10 s,
frescura de 1 s, salida 60 s, aviso a 30 s, establecimiento 30 s, margen de
etiqueta 10 s, cobertura de al menos 120 filas y 15 por bin de 5 s, hueco máximo
500 ms, cierre 250 ms/65536 bytes y todas las cotas históricas de almacenamiento.
No modifica criterios para aprobar. Permitted uses continúan todos false.

El plan está en execution_mode=offline_only, review_only=true y
authorization_granted=false. Ambiente, actor, montaje y confirmación de RX-01
permanecen PENDIENTE: no se heredan las declaraciones del diagnóstico como
confirmación futura. Actualmente RX-01 fue declarada desconectada; el contrato
de campaña histórico contempla leave_connected_fixed_uart_unopened, aún sin
confirmación. Esa disposición debe revisarse antes de cualquier integración
física; este borrador no instruye conectar RX-01 ni afirma un estado nuevo.

Solo puede ejecutarse la revisión sin dispositivos:

```bash
.venv/bin/python -B tools/revisar_campana_checkpoint_rx02.py \
  --plan config/piloto_rx02_C03_checkpoint2.review.json
```

Resultado esperado REVIEW_ONLY_NOT_AUTHORIZED. Ese comando no ofrece flags de
preflight ni ejecución, no consulta USB, no construye Serial y no consume permisos.
No se crea un plan local físico, carpeta de adquisición ni autorización C03.

Para una futura implementación debe usarse y auditarse explícitamente
rx02_checkpoint_journal.CheckpointRx02Session y audit_checkpoint_rx02 históricos,
compatibles con el contrato E/S. El CLI tools/piloto_presencia_rx02.py conserva
su sesión histórica sin checkpoints: agregar el campo al JSON no lo activa.
El CLI diagnóstico nuevo solo acepta RX02-DIAG-CP-R1 y no ejecuta C03. Falta una
entrada de campaña física optativa revisada y probada antes de dar un comando
físico concreto. No se implementa ni se ejecuta como parte de esta preparación.

Antes de cualquier intento futuro: nueva confirmación de condiciones/montaje,
disposición RX-01, alimentación/READY y audibilidad, preflight por metadatos y
autorización nueva para un único intento. Si falla, conservar, cerrar y detener;
sin reintento, reset, rearme o cambio de firmware. Sin calibración o entrenamiento.
La autorización RX02-DIAG-CP-R1 ya está consumida y no cubre C03.
