# R4-N01 vacío→sentado con prompt visible: preparado solo para revisión

El operador declara que completó la práctica de teclado con E y S reconocidas.
Su mensaje literal y el hash de la interfaz practicada se guardan en
`results/local/preparacion-devrep-r4-N01/practica-confirmada-r1.json`.
Es declaración humana sobre una práctica, sin etiqueta experimental o permiso
de captura. La confirmación queda ligada a la fuente exacta de la interfaz.

R3 conserva rechazo, E pendiente, S no creada, cierre RX-02 confirmado y permiso
consumido. La auditoría offline reproduce integridad y replay. R1/R2 y todas las
evidencias anteriores permanecen intactas: no se sustituye su etiqueta o permiso.

## Identidad y salida exclusivas nuevas

- Conexión y grupo: `RX02-DEVREP-R4-N01`, partición completa `development_future`.
- Slots: `RX02-DEVREP-R4-N01-E` y `RX02-DEVREP-R4-N01-S`, en ese orden.
- Salida futura: `results/local/devrep-rx02-r4-N01`; todavía no existe.
- Preparación: `results/local/preparacion-devrep-r4-N01/`.
- Plan de revisión: `config/devrep_r4_N01.review.json`; copia `plan.local.r1.json`.
- Un único intento, sin predecesor, reintentos, resets o reconexiones automáticos.
- Solo RX-02 `5C93200689`; RX-01 debe permanecer desconectada y sin abrir UART.

La entrada `tools/ejecutar_devrep_r4_n01.py` selecciona explícitamente
`devrep_keyboard_prompt.operate`. El plan fija
`operator_interface_revision=devrep-visible-keyboard-prompt-1`. La interfaz
integra el prompt «ESCRIBE AQUÍ LA DECLARACIÓN Y PULSA ENTER», cuenta atrás y
edición no bloqueante. Su fuente está en el conjunto de 40 archivos vinculados
por hashes al preflight, la solicitud y la procedencia/replay del bundle.
Una revisión ausente o distinta, cambio de interfaz o práctica incongruente
bloquean el intento; no se aplica la interfaz silenciosamente a R3.

Se conservan reductor, lector CSI, persistencia, criterios y cierre existentes.
La agenda mantiene solicitudes A+30/A+240 s, declaraciones A+210/A+420 s,
ventanas de 30 s y bandas T0 originales. A es disponibilidad inicial real.
El prompt lee el plazo ya fijado: abrirlo o redibujarlo no concede más tiempo.
READY exacto y disponibilidad antes de begin+10 s siguen obligatorios; no se
garantiza la repetición de READY y un fallo termina sin repetir.

## Siguiente acción: únicamente preflight nuevo por metadatos

Ejecutar desde la terminal normal Ubuntu:

```bash
cd /home/alan-monar/tesis-wifi-csi-hibrido
.venv/bin/python -B tools/preflight_devrep_r4.py \
  --plan results/local/preparacion-devrep-r4-N01/plan.local.r1.json \
  --confirm-current-conditions \
  --preflight-only \
  --receipt-new results/local/preparacion-devrep-r4-N01/preflight-r4-N01-r1.json
```

El prompt de preflight presenta ambiente, montaje respecto de R3, alimentación,
RX-01 desconectada, laptop/suspensión, ausencia de lectores y audibilidad desde
fuera. Escribir `CONFIRMO` solo si todas las condiciones siguen vigentes; si hay
cambios cancelar y describirlos. La práctica de teclado completada no sustituye
esas confirmaciones. Se guardarán declaración, montaje y plan confirmado nuevos.
No se copian como actuales las condiciones o recibos de R3.

La herramienta solo comprueba metadatos, identidades/unicidad, permisos, runtime,
espacio, boot y fuentes estables. Crea recibo/sidecar nuevos sin sobrescribir y
mantiene permiso falso. La ruta se valida antes de escribir confirmaciones: una
extensión `.json~`, un directorio distinto o evidencia existente se rechazan.
No abre UART, reproduce audio, lee CSI, crea etiquetas o concede autorización.

## Autorización nueva todavía pendiente

`solicitud-autorizacion-R4-N01.pendiente.json` documenta el alcance propuesto,
la salida y los nombres futuros, con permiso falso. No es una solicitud ejecutable
ni un grant. Después de revisar el recibo R4 se congelará la solicitud definitiva
`solicitud-autorizacion-R4-N01.json` con hashes del plan confirmado, recibo,
sidecar, práctica, 40 fuentes y runtime previsto; se pedirá autorización humana
nueva para ese alcance. El grant será `autorizacion-nueva-R4-N01.json`, hoy ausente.

Comando de captura reservado solo para después de esa revisión y permiso:

```bash
.venv/bin/python -B tools/ejecutar_devrep_r4_n01.py \
  --execute-after-approval \
  --authorization-file results/local/preparacion-devrep-r4-N01/autorizacion-nueva-R4-N01.json \
  --output-new results/local/devrep-rx02-r4-N01
```

El agente no lo ejecuta. La entrada comprueba el grant antes de metadatos o
sesión, revalida identidad al abrir y consume el permiso antes del intento.
Una salida existente impide repetir. Ante fallo conservar evidencia, cerrar y
detener, sin manipular placas para conseguir READY. Sin calibración/entrenamiento.

## Declaraciones previstas

```text
declare RX02-DEVREP-R4-N01-E yes
declare RX02-DEVREP-R4-N01-S yes
```

Cada una se escribe en su prompt y se envía con Enter, solo si ocurrió y se
oyeron los avisos. E exige salir físicamente, cerrar puerta y permanecer fuera
desde antes de sus dos tonos cortos hasta su tono corto final; después regresar
y declarar E antes de A+210 s. Para S, estar sentado y quieto antes de sus dos
tonos cortos, mantener la condición y esperar los tres tonos largos de cierre
confirmado antes de declarar S, antes de A+420 s. Ante duda/incumplimiento usar
`declare ID uncertain MOTIVO_REAL`; abort o Ctrl-C detienen. No hay yes implícito.

## Validación y conservación

49 pruebas offline aprobadas, cero errores/fallos/omisiones. Cubren R4 real
integrado con teclado y CSI en PTY propios: E/S, falta de Enter, READY ausente,
plazos, hashes de interfaz, procedencia/replay, checkpoints y cierre único.
Verifican rechazo de recibos/permisos R1/R2/R3, práctica incoherente, entrada
sin revisión explícita, fuentes/boot/sidecar alterados y rutas inválidas antes
de confirmar. El resto cubre teclado, redibujado, saturación y restauración.
Son pruebas sintéticas directas; no se acredita aislamiento Bubblewrap ni
rendimiento físico futuro.

Los 190 archivos protegidos se conservan por hash. Revisión, logs y preservación
en `results/local/preparacion-integracion-devrep-r4-N01-r1/`. El preflight físico,
plan confirmado definitivo, solicitud ejecutable, grant y salida siguen ausentes.
No hubo consulta USB actual, UART, captura, cambios de montaje/firmware,
calibración, entrenamiento o acceso a C04–C06 durante esta preparación.
