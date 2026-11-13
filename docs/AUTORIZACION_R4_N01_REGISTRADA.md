# R4-N01 E→S: permiso registrado para una ejecución del operador

El usuario autoriza explícitamente un único intento R4-N01 E→S con el plan y
comando presentados, solo RX-02 y RX-01 desconectada. Ante fallo o ausencia de
READY: conservar evidencia, cerrar y detener. Sin reintentos, resets,
reconexiones, calibración o entrenamiento. El agente no ejecuta la captura.

El grant y el mensaje literal se conservan en
`results/local/preparacion-devrep-r4-N01/autorizacion-nueva-R4-N01.json`.
SHA256 del grant:
`936f6e505f90d4661db65649979a49da4883bd3dfcf4f9b666d5da474163b1e6`.
Vinculado a la solicitud presentada, SHA256
`719a47441a29d8d2e91778d4c5099a8504c9c7b524a2c9497ed72fd9412be65b`.

Se validaron offline el grant y la vinculación completa de entrada: plan
confirmado, recibo/sidecar, práctica, boot y las 40 fuentes actuales. Se mantiene
la selección explícita de `devrep_keyboard_prompt.operate`. La salida física
sigue inexistente y el permiso no se ha consumido al registrarlo. El consumo
efectivo quedará en el futuro `authorization-consumed.json`, antes del intento
de apertura. El grant original conservará su estado histórico al emitirse.

El plan confirmado no se modifica. El ejecutor deriva su transición administrativa
a runtime después de validar el grant; plazos, criterios y condiciones permanecen
los presentados. No se requiere otro permiso para este mismo alcance.

## Comando definitivo: una vez desde la terminal normal Ubuntu del operador

```bash
cd /home/alan-monar/tesis-wifi-csi-hibrido
.venv/bin/python -B tools/ejecutar_devrep_r4_n01.py \
  --execute-after-approval \
  --authorization-file results/local/preparacion-devrep-r4-N01/autorizacion-nueva-R4-N01.json \
  --output-new results/local/devrep-rx02-r4-N01
```

La [guía presentada](AUTORIZACION_R4_N01_PENDIENTE.md) conserva avisos y
declaraciones exactas E/S. Escribir la orden completa en su prompt y pulsar Enter,
declarando solo lo ocurrido. E requiere salir físicamente, cerrar la puerta y
permanecer fuera hasta el tono corto final; después regresar para declarar E.
S requiere permanecer sentado y quieto hasta el cierre confirmado.

Validación y preservación en `results/local/registro-autorizacion-r4-N01-r1/`
y `autorizacion-nueva-R4-N01.validacion.json`. Los 227 archivos protegidos
permanecen idénticos, incluidos R3 y los rechazos/permisos consumidos anteriores.
No se modificaron fuentes ni se repitieron pruebas sintéticas. Sin consulta USB
actual, UART, captura, audio, movimientos, firmware, calibración o entrenamiento.
