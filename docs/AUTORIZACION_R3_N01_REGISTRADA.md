# R3-N01 E→S: permiso registrado; ejecución exclusiva del operador

El usuario autorizó explícitamente un único intento R3-N01 E→S con el plan y
comando presentados, solo RX-02 y RX-01 desconectada. Ordena conservar evidencia,
cerrar y detener ante fallo o ausencia de READY, sin reintentos, resets o
reconexiones. Sin calibración ni entrenamiento. No se solicita otro permiso
para este alcance y el agente no ejecuta la captura desde su entorno.

La autorización y el mensaje literal quedan en
`results/local/preparacion-devrep-r3-N01/autorizacion-nueva-R3-N01.json`.
SHA256 del grant:
`f9a540ac567dc522ba9da36bd7e96c511313da9bda962bba164cc28894acf10d`.
Está vinculado a la solicitud ya presentada, SHA256
`6be33e3a018738c7d8d9d40f2c48f26904770f4304228777f2e0356242ad2d14`.

Se validaron offline el grant, la entrada completa, el plan confirmado, recibo,
sidecar, boot y las 39 fuentes actuales. La salida física sigue inexistente y el
permiso aún no se ha consumido. El plan preparado permanece intacto: el ejecutor
construye la transición administrativa a runtime solo después de validar el
grant. El consumo se registra antes del intento de apertura en el futuro bundle;
el grant original conserva su estado al emitirse.

## Comando definitivo, una sola ejecución desde la terminal Ubuntu del operador

```bash
cd /home/alan-monar/tesis-wifi-csi-hibrido
.venv/bin/python -B tools/ejecutar_devrep_r3_n01.py \
  --execute-after-approval \
  --authorization-file results/local/preparacion-devrep-r3-N01/autorizacion-nueva-R3-N01.json \
  --output-new results/local/devrep-rx02-r3-N01
```

Avisos y declaraciones exactas permanecen en
[la guía presentada](AUTORIZACION_R3_N01_PENDIENTE.md#declaraciones-y-avisos).
Solicitudes automáticas: salir físicamente y cerrar puerta para E, regresar solo
tras su tono corto final para declarar E en terminal; permanecer sentado y quieto
para S y esperar el cierre confirmado. Declarar lo realmente ocurrido.

Validación y preservación en `results/local/registro-autorizacion-r3-N01-r1/` y
`autorizacion-nueva-R3-N01.validacion.json`. Los 149 archivos protegidos siguen
idénticos; rechazos y permisos consumidos R1/R2 intactos. No se repitieron pruebas
sintéticas ni se cambiaron fuentes. Sin consulta USB actual, UART, captura, audio,
reset, reconexión, firmware, calibración o entrenamiento durante este registro.
