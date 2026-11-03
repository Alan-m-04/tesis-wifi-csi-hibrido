# Plan para revisión: CONT-DUAL-01, 60 s, un único intento

Preparado desde 6450919618a8003a488c32e9d1925b84a9a80db3, sin autorización
física vigente. Contrato: [continuity-dual-1](CONTRATO_CONTINUIDAD_DUAL_1.md).
Es independiente de EXP02, de la campaña de presencia y de v4. No crea slots,
etiquetas, ventanas elegibles ni datos aprobados para modelos. El rechazo de
EXP02 y su autorización consumida permanecen intactos.

## Declaraciones y conexiones

Usar la copia local nueva `config/continuidad_dual_60s_r1.local.json`, procedente
del [plan revisable](../config/continuidad_dual_60s_r1.review.json). Alan es el
operador propuesto. Las condiciones de EXP02 son históricas: antes de autorizar,
confirmar el montaje actual, alimentación, suspensión y otros lectores, y
describir el ambiente actual en `declarations`. No hay condición de presencia
que establecer ni avisos sonoros; PRUEBA02 sigue siendo solo una declaración
histórica de otro protocolo. No mover equipos para imponer una etiqueta.

RX-01: by-id `usb-1a86_USB_Single_Serial_5C93199744-if00`.
RX-02: by-id `usb-1a86_USB_Single_Serial_5C93200689-if00`.
115200, perfil CSI existente, sin cambios de firmware. No resetear, reconectar
ni abrir un monitor para obtener READY. Si no están conectados, detener la
preparación y revisar con el operador; este plan no instruye una reconexión.

## Revisión sin apertura

Desde la raíz del repositorio, con `.venv` existente:

```bash
.venv/bin/python -B tools/diagnostico_continuidad_dual.py \
  --plan config/continuidad_dual_60s_r1.local.json
```

Preflight opcional en el terminal normal del operador, exclusivamente
udev/stat/permisos; no construye Serial, abre UART ni cambia permisos:

```bash
.venv/bin/python -B tools/diagnostico_continuidad_dual.py \
  --plan config/continuidad_dual_60s_r1.local.json --preflight-only
```

La ejecución vuelve a verificar metadatos antes y después de cada apertura y
contrasta el fd real. Un fallo detiene; no se cambia a ttyUSB por su número.
El preflight no demuestra que el dispositivo vaya a seguir presente al abrir.

## Comando reservado hasta recibir autorización explícita nueva

Salida nueva y exclusiva: `results/local/continuidad-dual-01-60s-intento-unico`.
No existe todavía, y nunca debe reutilizarse, ni siquiera ante un fallo. El
siguiente comando **no se ha ejecutado**:

```bash
.venv/bin/python -B tools/diagnostico_continuidad_dual.py \
  --plan config/continuidad_dual_60s_r1.local.json \
  --output-new results/local/continuidad-dual-01-60s-intento-unico \
  --execute-after-approval \
  --authorization-reference CONT-DUAL-01-60S-UNICO
```

La referencia registra la aprobación humana; escribir una cadena no la concede.
Los campos PENDIENTE bloquean ejecución aun con la opción anterior. La salida
registra la autorización consumida antes de abrir; ninguna autorización previa
se reutiliza.

No se teclea nada durante la observación. RX-01 empieza a drenar inmediatamente
después de su apertura mientras se abre RX-02. Con ambos abiertos y sus hilos
iniciados se fija el inicio/deadline de los 60 s comunes. El arranque anterior
también se conserva y se informa, sin recortarlo. MONOTONIC define la duración;
BOOTTIME y REALTIME permiten comparar suspensión/ajustes de reloj. Una pausa del
sistema puede alargar el tiempo de pared; los hilos no garantizan planificación
en tiempo real. El bloqueo indefinido del kernel/almacenamiento no es cancelable
con seguridad desde Python; no se promete plazo máximo de cierre en tal caso.

Un hueco >1 s sin fila CSI completa y válida queda como incidencia y puede
recuperarse varias veces; bytes sin LF y texto no cuentan como recuperación.
Resets, errores de firmware, perfiles incorrectos y discontinuidades se conservan
y reportan mientras continúa la observación, sin rearme ni aprobación. Un fallo
de transporte, identidad o almacenamiento detiene ambos. Ctrl-C pide cierre;
no usar kill -9, que impide recibo de cierre. Nunca relanzar para mejorar resultado.

Al deadline se dejan de iniciar lecturas, se espera a los lectores ya iniciados
y se cierran ambos recursos una vez. No hay drenaje para completar LF. Los
últimos bloques y colas quedan íntegros; sus tiempos permiten reconocer cruces
del deadline. Solo entonces se imprime el resultado. Cierre no confirmado o
fallo de integridad se reportan como tales; no hay recuperación automática.

## Artefactos y lectura posterior

`plan.json`, `metadata.json` (identidades, fuentes y commit),
`authorization-consumed.json`, `rx-01.serial.log`, `rx-02.serial.log`,
`ledger.jsonl`, `closure.json`, `report.json`, `manifest.json`. Ante fallo de
finalización se intenta crear además `finalization-failure.json`, sin sobrescribir
evidencia; no se asegura que pueda persistirse en un almacenamiento averiado.

```bash
.venv/bin/python -B tools/diagnostico_continuidad_dual.py \
  --audit results/local/continuidad-dual-01-60s-intento-unico
```

El auditor no abre dispositivos ni corrige datos. El informe da líneas completas,
filas válidas, todos los intervalos entre filas por retorno del host y reloj
local, diferencias de callbacks y queue_drops, incidentes/recuperación, tiempos
máximos de servicio/read/persistencia/análisis, y cola con hash/offset/referencias.
El ledger aporta tiempos MONOTONIC/BOOTTIME/REALTIME por servicio/lectura y
persistencia del bruto; duración de fsync del ledger no está aislada y contribuye
a los huecos de servicio. Varias filas de una lectura comparten su tiempo de
retorno: no es el instante RF ni prueba de recepción simultánea.

Los lectores no esperan stdin, sonido ni confirmaciones de ventanas. Comparten
un bloqueo de persistencia: una demora de disco puede afectar ambos, medible
como espera antes de persistir y hueco de servicio. Diferencia de BOOTTIME y
MONOTONIC es indicio de suspensión, sujeta al muestreo no simultáneo; REALTIME
también cambia por ajuste del reloj. Saltos de callback/queue_drops son señales
del firmware, no secuencias TX. Sin trazas adicionales sigue incierta la
localización causal entre RF/TX, callback, cola/tarea, UART, USB/driver y host.
En las dos fuentes actuales el id se incrementa después del filtro MAC/buffer;
`queue_drops` aumenta tanto por longitud no representable como por cola llena.
Ni un id contiguo prueba que el TX no perdió paquetes, ni una diferencia de
queue_drops localiza una pérdida RF. La fuente inspeccionada tampoco atestigua
por sí sola el binario instalado. Los bytes aún pendientes en el dispositivo,
driver o kernel al cerrar no están medidos; se conserva toda cola **leída**.

Código de salida 0 significa finalización nominal, integridad/replay y cierre,
**nunca aprobación de calidad**. Todas las salidas mantienen `quality_approval=false`
y usos de calibración, entrenamiento y producción prohibidos.
