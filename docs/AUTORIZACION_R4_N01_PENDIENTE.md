# R4-N01 E→S: recibo conforme, autorización nueva pendiente

Se revisó offline `preflight-r4-N01-r1.json` y su sidecar, en
`results/local/preparacion-devrep-r4-N01/`, contra `plan.confirmado-r1.json`,
declaración/montaje, boot actual, runtime pySerial, práctica humana registrada y
las 40 fuentes actuales. Coinciden hashes, identidad RX-02 y estados. RX-01 no
figura enumerada en el recibo. No se consulta USB actual ni se presume que READY
esté disponible en otra apertura.

Se conserva la comparación DEVLINKS: `raw_equal=false`,
`equal_under_revision=true`. La diferencia corresponde únicamente al orden de
sus rutas, conforme a `udev-devlinks-path-permutation-1`; ambos originales se
mantienen. No hubo copias, renombrados ni cambios del recibo.

SHA256 del plan confirmado:
`a624a507535292e5232c59603af0697b6578a88d6b9ca7e962efcd420a3fb32e`.
SHA256 del recibo:
`ba125fb9fafcf696af92498f61d8be1936cbb4875fbb220a3bf3598f374f3ae1`.
SHA256 del sidecar:
`9bd9df2c44e0e37ef2c5cef9a06e3f3aebf9c0c135082a4b280a78637176e596`.

La entrada selecciona `devrep_keyboard_prompt.operate`, con revisión explícita
`devrep-visible-keyboard-prompt-1`. El hash de esa fuente está en el conjunto
de 40 fuentes del recibo y de la solicitud, y coincide con el de la interfaz
que practicó el operador. El prompt visible y su cuenta atrás no cambian los
plazos, el reductor, la adquisición o las condiciones experimentales.

Se creó la solicitud ejecutable pendiente, no un permiso:
`results/local/preparacion-devrep-r4-N01/solicitud-autorizacion-R4-N01.json`.
SHA256 de la solicitud:
`719a47441a29d8d2e91778d4c5099a8504c9c7b524a2c9497ed72fd9412be65b`.
Fija R4-N01, E→S, solo RX-02, un intento sin reintentos, salida exclusiva, boot,
plan/recibo/sidecar/práctica/fuentes y plan runtime previsto. Hash del runtime:
`8e1b76b837ae1e67041a8bf99fac8debab771bbe8b787d4268c1af7353ef04a1`.

La especificación anterior `.pendiente.json` se conserva como historia de
preparación. El plan confirmado mantiene permiso falso y modo offline. El grant
`autorizacion-nueva-R4-N01.json` y la salida física aún no existen. La solicitud
requiere autorización humana nueva y revisión explícita del riesgo READY.

## Comando reservado hasta autorizar y registrar el permiso

Solo el operador lo ejecutará una vez desde su terminal normal Ubuntu:

```bash
cd /home/alan-monar/tesis-wifi-csi-hibrido
.venv/bin/python -B tools/ejecutar_devrep_r4_n01.py \
  --execute-after-approval \
  --authorization-file results/local/preparacion-devrep-r4-N01/autorizacion-nueva-R4-N01.json \
  --output-new results/local/devrep-rx02-r4-N01
```

La bandera no concede permiso. Antes de consultar metadatos o crear sesión se
valida el grant nuevo ligado a la solicitud. Se revalidan identidad y binding
al abrir; el permiso se consume antes del intento. Una salida existente impide
repetir. RX-01 debe permanecer desconectada. Ante fallo o ausencia de READY,
conservar evidencia, cerrar y detener sin reintentos, resets o reconexiones.
Sin calibración o entrenamiento. El agente no ejecuta la captura.

## Declaraciones exactas en sus prompts correspondientes

```text
declare RX02-DEVREP-R4-N01-E yes
declare RX02-DEVREP-R4-N01-S yes
```

Se escribe cada orden completa y se pulsa Enter cuando la condición se haya
cumplido y se hayan oído sus avisos. No hay `yes` automático.

E: salir físicamente y cerrar puerta al solicitarse E, antes de sus dos tonos
cortos; permanecer fuera hasta el tono corto final, regresar y declarar E antes
de A+210 s. S: sentarse y permanecer quieto antes de sus dos tonos cortos,
mantener la condición hasta los tres tonos largos de cierre confirmado y declarar
S antes de A+420 s. A es disponibilidad inicial real. Ante duda/incumplimiento,
usar `declare ID uncertain MOTIVO_REAL`; abort o Ctrl-C detienen.

READY exacto y disponibilidad antes de begin+10 s siguen obligatorios. READY
puede no reaparecer; ese fallo termina el único intento sin repetir.

`review_receipt`, `make_request` y `review_request` reproducidos offline; un
grant vacío se rechaza. No se llamó a `execute` ni se construyó una sesión.
220 archivos protegidos siguen idénticos, incluidos R3 y los rechazos anteriores.
Las 49 pruebas previas se conservan sin volver a ejecutarlas: no cambió código.
Revisión, hashes y comando reservado en `results/local/revision-recibo-r4-N01-r1/`.
Sin UART, captura, audio, consulta USB actual, firmware, calibración o entrenamiento.
