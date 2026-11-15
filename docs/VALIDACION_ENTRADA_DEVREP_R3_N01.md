# R3-N01: entrada validada offline; solo preflight para el operador

El operador confirma su conducta futura: para E saldrá físicamente, cerrará la
puerta, permanecerá fuera hasta el tono corto final y después regresará para
declarar E en la terminal; para S permanecerá sentado y quieto. Su mensaje exacto
se conserva en `results/local/preparacion-devrep-r3-N01/declaracion-prospectiva-ES-r1.json`.
No es una etiqueta experimental ni confirma por sí solo las demás condiciones.
El operador expresa que todavía no autoriza captura; no se creó permiso ni solicitud.

Se añade una entrada aislada `src/rx02_devrep_r3_n01/`, con agenda, reductor,
journal, persistencia, transporte, criterios y prueba de cierre derivados de R2.
Solo admite R3-N01, E→S, partición completa `development_future`, salida nueva
`results/local/devrep-rx02-r3-N01`, sin predecesor o reintentos. R1/R2 siguen
detenidas; sus fuentes, rechazos, notas y autorizaciones consumidas se conservan.
El borrador anterior permanece intacto; se añade `plan.local.r1.json` offline,
sin permiso y con condiciones pendientes. La salida física no se crea.

`tools/ejecutar_devrep_r3_n01.py` sin opciones solo valida ese plan y devuelve
`ENTRY_VALIDATED_OFFLINE_PREFLIGHT_PENDING`, sin USB o Serial. La entrada futura
comprueba permiso nuevo y vinculaciones antes de consultar metadatos o construir
sesión; no se invocó esa ruta. No existen el grant, solicitud ni recibo R3 físicos.
Los grants/recibos de pruebas son sintéticos y temporales, nunca permisos reales.

## Único comando entregado: preflight por metadatos

Ejecutar en la terminal normal de Ubuntu:

```bash
cd /home/alan-monar/tesis-wifi-csi-hibrido
.venv/bin/python -B tools/preflight_devrep_r3.py \
  --plan results/local/preparacion-devrep-r3-N01/plan.local.r1.json \
  --confirm-current-conditions \
  --preflight-only \
  --receipt-new results/local/preparacion-devrep-r3-N01/preflight-r3-N01-r1.json
```

El prompt presenta explícitamente las condiciones actuales de ambiente, montaje,
geometría, alimentación, RX-01 desconectada, suspensión, lectores y avisos desde
fuera. Solo si todas siguen vigentes escribir `CONFIRMO`; ante cambios cancelar
y describirlos. El prompt dice expresamente que no autoriza captura. No se presume
una respuesta por silencio. Se conserva la declaración textual mostrada y la
respuesta, fecha y boot; se escriben archivos nuevos de declaración, montaje y
`plan.confirmado-r1.json`, con hashes. El borrador de entrada no se modifica.

Después comprueba solo metadatos: by-id, serie/VID/PID/bus, unicidad por sysfs/udev,
permisos efectivos y ausencia RX-01; runtime pySerial por hash/versión; espacio,
boot, plan y fuentes estables. El recibo fija todas las fuentes de la entrada R3.
La comparación DEVLINKS conserva la revisión exacta previamente validada y ambos
valores originales. Genera recibo y sidecar nuevos sin sobrescribir. READY,
reinicio MCU, exclusividad futura y verdad física no quedan acreditados.

Si falta una condición o cambia boot/plan/referencia, rechaza. Recibos, sidecar,
confirmaciones o salida existentes no se borran ni reemplazan. Un fallo exige
revisar sus artefactos antes de otro comando. No usar sudo, chmod, reset o reconexión.

El preflight carece de opción de captura y no construye Serial, abre UART, lee CSI,
reproduce audio o crea etiquetas. Incluso si obtiene `PREFLIGHT_METADATA_ONLY`,
mantiene `authorization_granted=false` y `acquisition_executor_enabled=false`.
El recibo se revisará antes de preparar una solicitud nueva y pedir autorización.

## Verificación y límites

26 pruebas R3 offline aprobadas, sin fallos, errores u omisiones. Verifican entrada,
hashes, boot, manipulación de recibos/sidecar, rechazo de permisos/recibos R1/R2,
confirmación terminal y preservación de archivos, preflight sin captura y agenda
E/S con replay/checkpoints sobre PTY propios. Se comprueba cierre único, parada
por READY o declaración E faltantes y cambio de identidad antes de abrir. No hay
ensayo físico, audibilidad medida ni garantía de obtener READY en otra apertura.
Son pruebas directas; no se acredita aislamiento Bubblewrap.

La ejecución adicional de 47 pruebas R3/R2 produjo un fallo del test histórico R2
`test_identity_change_immediately_before_open_blocks_before_serial`: su última
aserción presupone que la salida R2-N01 aún no existe. Ese bundle ahora existe por
el intento físico rechazado, y se conserva. Las otras 46 pruebas pasaron; no se
modificó el test histórico ni se borró el bundle para satisfacer la aserción.
La auditoría offline R2 se reproduce además con sus fuentes intactas.

Logs, derivación, revisión offline y hashes de preservación en
`results/local/validacion-entrada-devrep-r3-N01-r1/`. No se ejecutó el preflight
físico desde el agente, abrió UART o adquirió datos. Sin calibración, entrenamiento,
firmware, cambios de montaje ni acceso a C04–C06.
