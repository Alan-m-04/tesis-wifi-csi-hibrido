# R3-N01: revisión independiente después de R2-N01 rechazado

R2-N01 conserva rechazo, serie detenida y autorización consumida. La auditoría
offline actual reproduce 23.662 operaciones, manifiesto y resumen. E conserva
`label.status=pending` y `declaration_ns=null`; S no llegó a crearse. La agenda
registra `missing_declaration_by_deadline` y `fatal=interrupt`. RX-02 tiene cierre
confirmado y lector detenido, con prueba
`pyserial_close_returned_and_all_fds_released`. Es evidencia del cierre histórico.

La [nota posterior](../results/local/devrep-rx02-r2-N01-declaracion-posterior-r1/NOTA.md)
declara que el operador permaneció dentro y no cumplió vacío. Se verificaron sus
hashes. No reemplaza la etiqueta faltante ni permite reclasificar E como sentado.
R1/D01 conserva también su rechazo. Ninguna de esas series continúa automáticamente.

La revisión y preservación están en
`results/local/revision-continuacion-devrep-r3-N01/`. Se verifican 102 archivos
protegidos, incluidas evidencias, notas, preparación y fuentes anteriores.

## Borrador nuevo, todavía sin entrada ejecutable ni autorización

Se prepara [un plan solo para revisión](../config/devrep_r3_N01.review.json), con
copia local `results/local/preparacion-devrep-r3-N01/plan.review.json`:

- ID y grupo de partición: `RX02-DEVREP-R3-N01`, en `development_future`.
- Orden prospectivo: vacío → sentado, un único intento, sin reintentos.
- Salida nueva: `results/local/devrep-rx02-r3-N01`; el directorio no se crea.
- `predecessor=null`: preparación independiente, sin reanudar R1/R2.
- Solo RX-02, serie `5C93200689`, 115200 baudios; RX-01 sin abrir.
- Criterios, agenda, persistencia, errores y brutos históricos preservados.
- Permiso falso, modo offline, ejecutor deshabilitado y condiciones `PENDIENTE`.

El operador eligió E→S y expresó que esta vez saldrá físicamente. Eso registra su
intención futura; no confirma por sí solo ambiente, montaje, audibilidad o etiquetas.
El borrador R3 no es aceptado por los ejecutores R1/R2. Antes de adquirir requiere
una entrada R3 específica, con preflight y replay revisados y validados offline.
No se habilita una captura cambiando el ID o los flags del ejecutor anterior.

## Dos declaraciones exactas, solo después de cumplir cada condición

```text
declare RX02-DEVREP-R3-N01-E yes
declare RX02-DEVREP-R3-N01-S yes
```

Se introducirán por separado, en el prompt correspondiente de la terminal del
operador, nunca anticipadas ni por chat. `yes` afirma que se estableció y mantuvo
la condición y que se oyeron los avisos. No responder por defecto. Ante duda o
incumplimiento, usar únicamente la línea del slot solicitado:

```text
declare RX02-DEVREP-R3-N01-E uncertain MOTIVO_REAL
declare RX02-DEVREP-R3-N01-S uncertain MOTIVO_REAL
```

La falta, demora o incertidumbre conserva el rechazo y detiene el intento; no se
repara retrospectivamente. `abort` o Ctrl-C detienen; no relanzar para obtener READY.

## Secuencia prevista de avisos y condiciones

La agenda se conserva del código inspeccionado. A es `initial_available`, después
de READY y disponibilidad inicial reales; no es el instante de pulsar Enter.
Las solicitudes son automáticas, sin escribir `slot` ni esperar órdenes por chat.

1. **A+30 s, solicitud E:** salir físicamente de inmediato; dejar laptop y RX
   dentro. El cuarto debe estar vacío antes de los dos tonos cortos de E.
2. **Unos 30 s después de la solicitud E:** dos tonos cortos de establecimiento.
   Permanecer fuera. No indican el final ni el inicio exacto de la ventana CSI.
   El gate espera al menos solicitud+60 s y fin de reproducción+30 s, y exige
   filas frescas. T0 debe caer entre A+90 y A+120 s; la ventana dura 30 s.
3. **T1(E)+10 s:** un tono corto de fin de E, con conexión todavía abierta.
   Solo entonces regresar, atender el prompt e introducir la declaración E
   veraz antes de A+210 s. No permanecer fuera esperando los tres tonos largos:
   son el cierre de la conexión, que llegará después de S.
4. Tras declarar E, sentarse y quedarse quieto en la marca. **A+240 s, solicitud
   S:** mantener sentado. Unos 30 s después suenan dos tonos cortos; estar ya
   sentado antes de ellos y mantener la condición. T0 debe caer entre A+300 y
   A+330 s; la ventana dura 30 s.
5. **T1(S)+10 s:** un tono corto de fin de ventana y solicitud de cierre.
   Mantener sentado hasta los **tres tonos largos de cierre confirmado de RX-02**;
   atender el prompt y declarar S veraz antes de A+420 s. El aviso de cierre se
   emite solo con prueba de cierre; transcurrir un tiempo no lo confirma.
6. **Ocho tonos rápidos:** fallo; seguir la parada, conservar el bundle y comprobar
   su recibo de cierre. No volver a abrir, resetear o reconectar para repetir.

La solicitud de cierre tiene techo A+390 s. Los tiempos exactos quedan en los
eventos; el sonido no mide verdad física ni crea una etiqueta. Los patrones se
inspeccionaron en `presence_v4_audio.py` y la agenda/reductor en
`rx02_devrep/coordinator.py`, `rx02_devrep_r2_n01/contract.py` y
`persistent_presence_v4.py`; no se reprodujo audio durante esta revisión.

## Requisitos que faltan antes de solicitar autorización ejecutable

1. Confirmación actual del operador: solo, puerta/ventanas cerradas, sin ventilador;
   montaje, antenas, coaxiales, cables, marca sentada y geometría; alimentación de
   TX/RX, RX-01 desconectada; laptop enchufada/abierta, suspensión desactivada y
   otros lectores cerrados. Confirmar que distingue los avisos desde fuera.
2. Declaración y referencia de montaje nuevas ligadas por hashes al boot actual.
   Las confirmaciones antiguas de R2-N01 no se transfieren automáticamente.
3. Implementación y validación offline de entrada/preflight/replay exclusivos R3,
   sin alterar las fuentes históricas que auditan R1/R2.
4. Preflight nuevo solo por metadatos: by-id/serie/VID/PID, unicidad, permisos,
   disposición RX-01, runtime pySerial, espacio, boot y fuentes estables. No
   reutilizar el recibo de R2-N01 ni dar por aprobados esos requisitos ahora.
5. Solicitud de autorización nueva con hashes del plan definitivo, recibo y fuentes;
   revisión explícita del riesgo READY. Sigue siendo obligatorio READY exacto y
   disponibilidad antes de begin+10 s; no se garantiza su repetición.
6. Autorización humana explícita para un único intento R3-N01 con salida exclusiva,
   sin reintentos, tras presentar y revisar esos artefactos. La solicitud y el
   grant ejecutables aún no se crean: faltan los requisitos anteriores.

La confirmación de condiciones solicitada en conversación no es permiso para
capturar. Este turno solo lee registros, reproduce la auditoría y escribe nuevos
artefactos de revisión. Sin consultas USB actuales, UART, audio, captura, reset,
reconexión, firmware, calibración, entrenamiento ni acceso a la reserva C04–C06.
