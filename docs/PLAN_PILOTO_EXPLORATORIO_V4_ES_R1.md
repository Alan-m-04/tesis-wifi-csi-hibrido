# Plan E/S para revisión — sin autorización ni ejecución

[Plan JSON nuevo](../config/piloto_exploratorio_v4_ES_r1.review.json), conexión
`EXP-V4-C02-ES-20261101-R1`, partición única `EXP-V4-C02-ONE-CONNECTION`.
Selecciona explícitamente `v4-exploratory-1` y `v4-startup-sequence-1`.
Es un plan revisable, no una adquisición, permiso o calibración. No se reutilizan
los identificadores o la autorización consumida del primer v4.

| Orden | Slot | Condición declarada | Último |
|---|---|---|---|
| 1 | `EXP02-E` | Ambiente vacío durante la ventana y márgenes. | No |
| 2 | `EXP02-S` | Una persona sentada durante la ventana y márgenes. | Sí, declarado prospectivamente antes de solicitarlo. |

Ambas ventanas comparten una conexión por RX y un grupo de partición; no se
consideran muestras independientes para entrenamiento. No se incluyen caminata,
repeticiones, calibración, inferencia de presencia o ampliación automática.

Antes de cualquier ejecución futura siguen pendientes actor, montaje/hash,
condición, ocupación, movimiento, geometría, potencia TX, confirmación de montaje
y referencia de práctica/audibilidad. Los `PENDIENTE` permanecen intencionalmente;
se desconoce el ambiente físico actual y no se copian declaraciones antiguas como
si fueran confirmaciones nuevas. La preparación no consulta dispositivos.

Operación propuesta para revisar: laptop y receptores en la ubicación que se
declare; un operador establece la condición usando las demoras y avisos existentes.
Cada solicitud de slot es manual y prospectiva, tras disponibilidad comprobada.
Se conservan demora de salida de 60 s, aviso a los 30 s, establecimiento mínimo
de 30 s desde el resultado del aviso, gate de tres filas nuevas, ventana de 30 s
y margen final de 10 s. Cada etiqueta requiere declaración posterior del operador;
el retorno del reproductor no verifica audibilidad humana.

No se solicita el segundo slot si el primero no está completo/declarado o si hay
suspensión. No se reabre, resetea o reintenta para recuperar READY. La disponibilidad
inicial requiere ambos retornos y tres filas nuevas por RX fuera de los chunks de
arranque. Falta de READY, error/reset, discontinuidad, silencio o almacenamiento
insuficiente mantiene suspensión y cierre sin rearmado. La confirmación de ambos
cierres proviene del recibo y del estado observado de recursos.

El preámbulo anómalo permanece en el bruto y mantiene rechazada la conexión.
Solo el [auditor de la revisión nueva](ELEGIBILIDAD_EXPLORATORIA_V4_R1.md) puede
confirmar una ventana exploratoria posterior, con integridad, identidad, fronteras,
cobertura, etiqueta, almacenamiento y cierres. No hay aprobación automática para
calibración, entrenamiento o producción.

Preparación segura realizada, sin `--preflight-only` ni opción de ejecución:

```bash
.venv/bin/python -B tools/campana_presencia_uart_v4.py \
  --plan config/piloto_exploratorio_v4_ES_r1.review.json
```

Retorna `PREPARED_NOT_EXECUTED`, `physical_UART_opened=false` y
`authorization_granted=false`. La validación de ejecución rechaza el plan por
sus declaraciones pendientes. El transporte físico sigue requiriendo instrucción
nueva y explícita y una referencia de autorización nueva, ajena a este documento.
No se abrió UART ni se ejecutó preflight físico para preparar este plan.
