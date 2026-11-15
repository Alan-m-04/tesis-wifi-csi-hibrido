# R3-N01 E→S: recibo conforme y solicitud de autorización nueva

Se revisa el recibo real
`results/local/preparacion-devrep-r3-N01/preflight-r3-N01-r2.json` y su sidecar
contra `plan.confirmado-r1.json`, referencias de declaración/montaje, boot actual,
runtime local pySerial y las 39 fuentes actuales. Coinciden los hashes,
identidades y estados. Las dos lecturas difieren solo en el orden de DEVLINKS;
se conserva `raw_equal=false`, `equal_under_revision=true` conforme a la revisión
registrada. No se consulta USB actual ni se acredita disponibilidad futura de READY.

El ejecutor revisado fija el nombre de recibo `preflight-r3-N01-r1.json`. Para
mantener intactas todas las fuentes cubiertas por el recibo se crean copias byte
a byte del recibo r2 y su sidecar en esos nombres r1, previamente inexistentes.
Ambos originales r2 se conservan. No son otro preflight o evidencia nueva de
dispositivo; la correspondencia explícita de origen/destino está en
`results/local/revision-recibo-r3-N01-r2/vinculacion-r2-a-rutas-fijas-r1.json`.

SHA256 del recibo original y copia:
`a516b7855fcb3632ea0ca48ba41da5d7a6b9fa4993e9c9ba0791dd32e7d08fb9`.
SHA256 del sidecar original y copia:
`40dd7279481cdf42c442a02e59365692d026cd9f20668cfb6fc775afb7f27098`.
SHA256 del plan confirmado:
`37d54cefcc016230dac32cb98d85bcfd5a536ef42cdf0ea1db23ad67d8898977`.

Se crea exclusivamente una solicitud pendiente, no un permiso:
`results/local/preparacion-devrep-r3-N01/solicitud-autorizacion-R3-N01.json`.
Fija R3-N01, orden E→S, un intento sin reintentos, salida exclusiva, hashes de
plan/recibo/sidecar y fuentes, boot y riesgo READY. SHA256 de la solicitud:
`6be33e3a018738c7d8d9d40f2c48f26904770f4304228777f2e0356242ad2d14`.
SHA256 del plan runtime previsto tras autorización:
`a911e0e4c64dd95966948c7d14f2a6b74540c1a0376e6c66d78cfa85cfbd783f`.

El plan confirmado conserva modo offline, permiso falso y ejecutor deshabilitado.
El grant `autorizacion-nueva-R3-N01.json` y la salida física aún no existen.
La transición administrativa a runtime solo se usa tras permiso humano nuevo
vinculado a la solicitud. No cambia las condiciones, datos, agenda o criterios.

## Comando reservado para después de autorizar y registrar el permiso

Solo el operador lo lanzará desde su terminal normal Ubuntu:

```bash
cd /home/alan-monar/tesis-wifi-csi-hibrido
.venv/bin/python -B tools/ejecutar_devrep_r3_n01.py \
  --execute-after-approval \
  --authorization-file results/local/preparacion-devrep-r3-N01/autorizacion-nueva-R3-N01.json \
  --output-new results/local/devrep-rx02-r3-N01
```

No ejecutar hasta que exista la autorización humana nueva y se registre el grant.
La bandera no otorga permiso. La entrada rechaza ausencia o incongruencia del
grant antes de consultar metadatos o construir sesión. Comprueba de nuevo la
identidad justo antes de abrir y el binding del descriptor; consume el único
permiso antes del intento y una salida existente impide reabrir. No se continúa
a otro ID o a R1/R2. El agente no ejecuta la captura desde su entorno.

## Declaraciones y avisos

```text
declare RX02-DEVREP-R3-N01-E yes
declare RX02-DEVREP-R3-N01-S yes
```

Se escriben por separado en el prompt del slot correspondiente, solo si ocurrió
la condición y se oyeron sus avisos. Las solicitudes son automáticas; no escribir
`slot` ni esperar instrucciones de chat. A es la disponibilidad inicial real.

1. Solicitud E en A+30 s: salir físicamente, cerrar puerta y estar fuera antes
   de los dos tonos cortos. Permanecer fuera durante establecimiento y ventana.
2. Un tono corto, T1(E)+10 s, termina E: regresar y declarar E en terminal antes
   de A+210 s. No esperar los tres tonos largos para regresar.
3. Sentarse y quedarse quieto en la marca; solicitud S en A+240 s. Estar ya
   sentado antes de sus dos tonos cortos y mantener la condición.
4. Un tono corto termina S y conduce al cierre; esperar los tres tonos largos
   de cierre confirmado de RX-02 y declarar S en el prompt antes de A+420 s.
5. Ocho tonos rápidos indican fallo. Ante incumplimiento/duda declarar solo el
   slot solicitado con `declare ID uncertain MOTIVO_REAL`; `abort` o Ctrl-C
   detienen. Conservar el resultado y comprobar cierre, sin relanzar, resetear
   o reconectar para conseguir READY.

READY exacto y disponibilidad antes de begin+10 s siguen obligatorios. Puede
no reaparecer READY: el único intento se detiene y no se repite. Los sonidos
no acreditan verdad física ni crean etiquetas; la declaración será veraz.

## Comprobaciones realizadas

`review_receipt`, `make_request` y `review_request` reproducidos offline sobre
los artefactos actuales. El grant ausente bloquea antes de metadatos/sesión.
139 archivos protegidos permanecen idénticos. Se conservan rechazos y permisos
consumidos R1/R2. Los logs de validación previa de 26 pruebas R3 siguen intactos;
no se modificó código ni se repitieron pruebas sintéticas en esta revisión.
Revisión, hashes y comando reservado en `results/local/revision-recibo-r3-N01-r2/`.
Sin UART, adquisición, audio, reset, reconexión, firmware, calibración o entrenamiento.
