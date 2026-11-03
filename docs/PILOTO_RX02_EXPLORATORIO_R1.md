# Piloto prospectivo TX-01 / RX-02, revisión 1

Contrato definido antes de implementar y antes de adquirir. Base:
`9b28addc221468ed1c38e6480a6cf153e5a00c70`. Estado: preparación offline;
sin autorización física vigente, sin A–A ni adquisiciones nuevas.

## Decisión prospectiva y alcance

`presence_rx02_persistent_1` usa exclusivamente RX-02, USB serial
`5C93200689`, ruta `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5C93200689-if00`.
TX-01 y el perfil CSI original permanecen iguales. Nunca sustituir RX-02 por
RX-01, resolver por número tty ni abrir un segundo receptor como alternativa.

Esto modifica expresamente, sólo para este piloto nuevo, la preferencia de
RX-01 como entrada primaria descrita en `DETECTOR_PRESENCIA_RUVIEW.md`.
La selección se fija por los diagnósticos de continuidad, sin resultados de
presencia: A1/B/A2 registraron 296/291/291 filas en RX-02 y ninguna incidencia
de silencio >1 s; RX-01 registró 294/213/201 y 0/2/2 incidencias. A2 no
reprodujo A1: no se atribuye causalidad a la orientación. Es una selección
exploratoria condicionada por esa evidencia, no validación de un detector ni
estimación imparcial de todos los receptores. No se reclasifica historia.

La ausencia de incidencias >1 s no garantiza cobertura de presencia: en A2,
RX-02 tuvo un hueco host de **612.338620 ms** (local **600.020 ms**), superior
al límite de cobertura de 500 ms. Ese límite se conserva. Un hueco semejante
dentro de una ventana futura impediría su elegibilidad aunque no activase
el watchdog de 1 s. Fuente: `results/COMPARACION_ANTENA_ABA_R3.resumen.json`,
`phases.A2.receivers.RX-02`; se cita el diagnóstico sin recalificar sus datos.

## Resultados separados y controles invariables

La conexión completa, su preámbulo, cada ventana y su elegibilidad exploratoria
son resultados distintos. La revisión `rx02-exploratory-1` conserva la gramática
`v4-startup-sequence-1` aplicada a RX-02: sniffer antes de READY cuando aparece,
retorno exacto de app_main después de READY y tres filas nuevas posteriores
a la barrera de arranque. No exige un retorno ficticio de RX-01.

Los bytes desconocidos del preámbulo se conservan íntegros, con offsets, tiempos,
hashes y referencias; quedan anómalos/no interpretados y la conexión completa
no es conforme. Nunca pasan por CSI válido. Una ventana prospectiva sólo puede
ser candidata si el preámbulo está sellado estrictamente antes de T0 y ninguna
anomalía la alcanza o queda sin localizar fuera de ella. El replay, identidad,
almacenamiento, etiqueta humana y cierre confirmado siguen siendo obligatorios.

Se reutilizan sin reducir los parámetros POLICY y STORAGE de v4: disponibilidad
inicial 10 s, frescura 1 s sin rearme, 3 filas nuevas, ventana 30 s, espera de
salida 60 s, aviso inicial a los 30 s y al menos 30 s después de su reproducción,
cola de etiqueta 10 s; >=120 filas, >=15 por cada bin de 5 s, hueco máximo
500 ms incluidos bordes. Reserva 32 MiB, libre inicial 100 MiB, bruto <64 MiB,
bundle <256 MiB, conexión <3600 s. Drenaje de cierre <=250 ms / 65536 bytes.
Resets, errores, discontinuidades, perfil incorrecto, texto posterior genérico,
pérdida de disponibilidad, fallos de audio/transporte/almacenamiento suspenden.

Una conexión persistente por repetición; una apertura y un cierre de RX-02.
La confirmación `selected_port_closed_confirmed` se refiere sólo a RX-02 y
se anuncia después del recibo durable; no afirma que se haya cerrado RX-01.
El mismo patrón sonoro final de tres tonos largos se identifica con este
nuevo nombre. La captura preserva entrada y no vacía buffers, reinicia,
reconecta ni reintenta para obtener READY.

Elegibilidad exploratoria no autoriza calibración, entrenamiento ni producción.
El adaptador/modelo histórico con RX-01 primario tampoco se ejecuta aquí.

## Plan operativo para revisión

Seis conexiones nuevas C01–C06, cada una con vacío (E) y una persona sentada
(S), orden ES, SE, ES, SE, ES, SE: seis repeticiones por condición. C01–C03
se reservan prospectivamente para desarrollo futuro; C04–C06 para evaluación
futura sellada. Nunca dividir filas/ventanas de una conexión entre particiones.
No elegir ni reemplazar conexiones según sus resultados: conservar fallos y
etiquetas inciertas, detener la campaña ante fallo y revisar antes de continuar.
Una nueva ejecución de reemplazo necesitaría otro plan y autorización.

Propuesta para RX-01, **pendiente de confirmación del operador**: dejarlo
conectado e inmóvil como está, sin lector UART. No se declara apagado ni
radio silenciosa; su alimentación/radio y el montaje son condiciones del piloto.
No se desconecta, mueve, cambia de puerto ni modifica firmware automáticamente.

Antes de la primera conexión: revisar esta selección y particiones, confirmar
la propuesta de RX-01, fijar montaje/fotos/antenas/coaxiales, alimentación TX y
laptop, tapa y suspensión AC/batería, ausencia de lectores, ambiente/ocupación,
ruta de salida nueva y audibilidad desde fuera. PRUEBA02 es sólo antecedente;
no sustituye las declaraciones actuales. Completar una copia local del plan
de la conexión, preflight sólo por metadatos y solicitar autorización nueva.

Durante cada conexión autorizada: esperar disponibilidad; solicitar manualmente
el primer slot. Para E, salir/cerrar antes del aviso inicial de los 30 s y
mantener vacío hasta el aviso final; para S, permanecer sentado e inmóvil desde
antes del aviso inicial hasta el final. El aviso final de un slot no último
deja abierto RX-02. Declarar condición establecida/mantenida y avisos oídos;
cualquier duda se declara uncertain. Solicitar el segundo slot con `last`.
El cierre ocurre después del aviso final; completar la declaración pendiente.
Auditar integridad, replay, elegibilidad y cierre antes de preparar otra conexión.

## Archivos, comandos y pasos concretos

El manifiesto `config/piloto_rx02_r1.campaign.review.json` fija los seis planes,
salidas nuevas y particiones. Cada `*.review.json` está en `offline_only`,
con declaraciones pendientes y `authorization_granted=false`.

| Conexión | Slots manuales, en orden | Partición futura | Salida nueva propuesta |
|---|---|---|---|
| RX02-C01 | RX02-C01-E; RX02-C01-S last | desarrollo | results/local/piloto-rx02-r1-C01 |
| RX02-C02 | RX02-C02-S; RX02-C02-E last | desarrollo | results/local/piloto-rx02-r1-C02 |
| RX02-C03 | RX02-C03-E; RX02-C03-S last | desarrollo | results/local/piloto-rx02-r1-C03 |
| RX02-C04 | RX02-C04-S; RX02-C04-E last | evaluación sellada | results/local/piloto-rx02-r1-C04 |
| RX02-C05 | RX02-C05-E; RX02-C05-S last | evaluación sellada | results/local/piloto-rx02-r1-C05 |
| RX02-C06 | RX02-C06-S; RX02-C06-E last | evaluación sellada | results/local/piloto-rx02-r1-C06 |

Desde la raíz del repositorio, preparación sin descubrir dispositivos ni abrir
UART (único modo ejecutado durante este desarrollo):

```bash
.venv/bin/python -B tools/piloto_presencia_rx02.py \
  --plan config/piloto_rx02_r1_C01.review.json
```

Para una futura operación: copiar el plan de C01 a
`config/piloto_rx02_r1_C01.local.json`. Completar declaraciones actuales,
montaje y audibilidad; confirmar explícitamente
`unused_receiver.operator_confirmation=confirmed_current`. La selección,
slots, particiones, perfil y umbrales quedan fijos. Cambiar
`execution_mode` a `physical_after_approval` sólo para preparar su revisión;
eso no concede autorización. C02–C06 requieren sus propias copias y revisión.

Preflight futuro, sólo metadatos de RX-02; no ejecutado en esta preparación:

```bash
.venv/bin/python -B tools/piloto_presencia_rx02.py \
  --plan config/piloto_rx02_r1_C01.local.json --preflight-only
```

No basta con que un preflight histórico haya pasado. Antes de cada conexión,
confirmar declaraciones vigentes y ausencia de otros lectores, y obtener una
autorización explícita nueva. Ante falta de READY dentro de 10 s se suspende;
no resetear/reconectar para fabricar un nuevo arranque. El runtime conserva
la entrada y solicita DTR/RTS false, sin demostrar ausencia de transitorios
eléctricos ni atestiguar el firmware instalado.

**Formato futuro de ejecución, no autorizado ni ejecutado ahora:**

```bash
.venv/bin/python -B tools/piloto_presencia_rx02.py \
  --plan config/piloto_rx02_r1_C01.local.json \
  --output-new results/local/piloto-rx02-r1-C01 \
  --execute-after-approval --authorization-reference REFERENCIA-NUEVA-DEL-OPERADOR
```

Una vez disponible RX-02, para C01 se usarían estas órdenes, cada una en su
momento, sin pegarlas en bloque:

1. `slot RX02-C01-E`; salir y cerrar antes de los dos tonos cortos.
2. Volver tras el tono corto final. Si se cumplieron establecimiento,
   mantenimiento y escucha: `declare RX02-C01-E yes`; en caso de duda,
   `declare RX02-C01-E uncertain MOTIVO` y detener.
3. `slot RX02-C01-S last`; adoptar sentado antes del aviso inicial y mantener
   la condición hasta el final.
4. Tras el aviso final, confirmar cierre de RX-02 (tres tonos largos y recibo),
   y `declare RX02-C01-S yes` sólo si corresponde. Ante fallo se conserva todo
   y no se continúa a otra conexión.

Las otras conexiones usan sus IDs y el orden de la tabla. `yes` es declaración
humana, nunca medición automática de la verdad de presencia. El programa sigue
leyendo UART cuando sólo ha llegado parte de una orden; no espera bloqueado
un LF del operador. No solicita slots automáticamente ni sustituye rechazos.

Auditoría offline posterior, en el mismo código versionado que creó el bundle:

```bash
.venv/bin/python -B tools/piloto_presencia_rx02.py \
  --audit results/local/piloto-rx02-r1-C01
```

Guardar stdout y revisar **por separado** conexión completa, preámbulo,
dos ventanas, elegibilidad exploratoria y recibo de cierre. Una conexión con
preámbulo anómalo nunca obtiene `connection.quality_ok=true`, aunque sus dos
ventanas posteriores puedan ser exploratorias. Integridad/replay por sí solos
no bastan para afirmar elegibilidad. La autorización queda consumida antes del
intento de apertura y se conserva incluso si éste falla. Las salidas se crean
exclusivamente, sin sobrescribir bundles existentes. Los hashes permiten
detectar alteraciones y reproducir decisiones; no son una firma de autenticidad
del operador ni una medición de fenómenos eléctricos.

No se dispone de RX-01 como control concurrente en este piloto; no se extrapola
la comparación dual anterior a la clasificación de presencia. Seis conexiones
son un piloto pequeño, temporalmente ordenado y del mismo montaje/persona;
no acreditan generalización a otros días, personas, habitaciones o equipos.
La partición futura se conserva aunque una conexión falle. No se inspecciona
la evaluación para ajustar umbrales ni se entrenan/calibran modelos ahora.

La implementación añade módulos RX-02 propios y hereda el procesamiento,
watchdog, etiquetas, lectura/persistencia y límites de v4. Sólo inicialización
de topología, cierre, resumen de elegibilidad y schema/auditoría son específicos.
Los módulos, planes, bundles, rechazos y autorizaciones duales se conservan.
No se ha abierto UART para elaborar este contrato.

## Verificación offline de esta revisión

310 pruebas pasaron: 31 específicas de RX-02 y 279 de regresión de captura,
arranque, elegibilidad, auditoría y diagnósticos existentes. Incluyen un solo
PTY con pySerial, entrada encolada antes de abrir, dos slots manuales, dos
etiquetas y cierre; fallos de apertura/identidad/lectura/cierre/almacenamiento;
órdenes parciales sin LF; preámbulo anómalo, fronteras e incertidumbre temporal,
frescura, cobertura insuficiente, resets/errores/perfiles/discontinuidades y
alteraciones de brutos, replay, fuentes y recibo. Todas son pruebas sintéticas,
sin adquirir, ajustar umbrales ni usar presencia física para seleccionar RX-02.

Inventario y hashes: `results/PREPARACION_PILOTO_RX02_R1.json`. Se comprobaron
2.855 archivos históricos contra un inventario previo, sin diferencias. No se
ejecutó el preflight USB real en esta preparación ni se verificaron condiciones
ambientales actuales. Conclusión: **variante offline verificada y plan listo
para revisión; adquisición aún bloqueada por declaraciones actuales,
confirmación del manejo de RX-01 y autorización explícita nueva**.
