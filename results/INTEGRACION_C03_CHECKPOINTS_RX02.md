# Integración optativa C03 / checkpoints — validación offline

Base local/remota comprobada b3b5fc73223069a970f56c8a565abe6add39886e,
rama feat/backend-uart-presencia-v4. Integración física preparada, sin abrir
UART, capturar, calibrar o entrenar. Condiciones actuales pendientes de una
consulta agrupada; preflight real y autorización nueva todavía no realizados.

[Contrato, plan y comandos](../docs/INTEGRACION_C03_CHECKPOINTS_RX02.md).
[Evidencia verificable](INTEGRACION_C03_CHECKPOINTS_RX02.validacion.json).
[Hashes y preservación](INTEGRACION_C03_CHECKPOINTS_RX02.hashes.json).

La entrada tools/campana_rx02_checkpoint.py selecciona C03CheckpointSession y
audit_c03_checkpoints solo con persistencia e integración explícitas. Sin campo
de persistencia/integración delega a la ruta histórica intacta. Revisiones
incompletas/desconocidas se rechazan antes de metadatos/UART.

Plan/procedencia/auditoría exigen rx02-raw-sync-control-checkpoint-2 y
rx02-c03-checkpoint-entry-1. Se usa CheckpointJournal original sin alteraciones,
con las mismas cotas, barreras, errores y garantías de cierre/durabilidad.
La procedencia durable anterior a apertura registra 25 fuentes, ambas revisiones
y el hash del plan. Runtime, política y estado final deben coincidir en auditoría.

C03 E→S, partición development_future, cobertura, frescura, etiquetas y cierre
permanecen iguales. RX-01 puede declararse desconectada y sin UART solo en esta
revisión; plan/replay/procedencia retienen ese estado, sin adaptarlo a conectada.
No se modifican fuentes históricas ni las congeladas del diagnóstico físico.
C02 conserva rechazo, etiquetas, cola, partición y autorización consumida.

## Pruebas reales de la integración

465 pruebas aprobadas en 46,849 s: las 450 previas y 15 nuevas. Cero fallos,
errores u omisiones. Bubblewrap con red aislada, /dev privado y repo/referencias/
tres fotos históricas en solo lectura. test_presence_offline excluido por ser
calibración/inferencia fuera de alcance. No se afirma nueva validación física.

Las pruebas nuevas cubren delegación histórica y rechazo de revisiones
incompletas; invariantes C03; preparación sin metadatos; declaraciones/grant
nuevos; preflight solo RX-02 sin Serial y sin sobrescribir evidencia; condiciones
y fuentes cambiadas; salida ya existente; dos ventanas sintéticas prospectivas
E→S con etiquetas, procedencia/replay/checkpoints/cierre; orden fsync bruto antes
del reductor y ticks diferidos; fallo de fsync sin manifiesto/recibo de éxito;
watchdog sin rearme; y falsificación con hashes recalculados de procedencia o
estado durable. Los tiempos del fixture son sintéticos con reloj escalonado.

Las auditorías históricas de C02 y RX02-DIAG-CP-R1 pasan después del cambio.
68 archivos protegidos (bundles/planes/autorizaciones anteriores y preparación
diagnóstica) fueron reverificados intactos. Todos los originales se conservan.

## Preparación local y siguiente paso

Plan nuevo results/local/preparacion-C03-checkpoint-r1/plan.local.json;
salida exclusiva reservada results/local/piloto-rx02-r1-C03-checkpoint-r1,
todavía inexistente. Plantilla config/piloto_rx02_C03_checkpoint2.integrated.review.json.
La preparación devuelve PREPARED_NOT_AUTHORIZED con sesión/auditor correctos.
Los PENDIENTE del plan no se rellenan sin la respuesta actual del operador.

```bash
.venv/bin/python -B tools/campana_rx02_checkpoint.py \
  --plan results/local/preparacion-C03-checkpoint-r1/plan.local.json
```

Después de recibir condiciones, únicamente --preflight-only, por metadatos,
desde terminal del operador si el entorno no ve el dispositivo. Luego se
presentará el hash/comando definitivo y se pedirá autorización nueva para un
único intento. No ejecutar --execute-after-approval en esta preparación.
La existencia de la implementación no constituye permiso físico vigente.
