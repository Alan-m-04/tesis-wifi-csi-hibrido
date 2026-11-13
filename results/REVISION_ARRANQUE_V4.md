# Revisión offline del arranque v4 desde 6af037b

**Conclusión: bloqueo específico pendiente antes del plan vacío/sentado.** Se
corrigieron dos incompatibilidades de mensajes de inicialización, pero la
conexión completa sigue siendo no elegible si conserva los residuos iniciales
registrados. No se preparó otro plan E/S, no se abrió UART y no se reutilizó una
autorización. La corrección no autoriza una campaña destinada a quedar rechazada
por un problema de formato conocido y todavía sin resolver.

Base comprobada: rama `feat/backend-uart-presencia-v4`, HEAD y remoto
`6af037bb835db9b8e03a45a4ede0373b3030d663`, Git limpio al iniciar. No había otra
revisión pendiente o cambio sin registrar. Esta revisión del 1 de noviembre de
2026 conserva los informes y las políticas anteriores como historia.

## Evidencia registrada, sin reconstrucción de tiempos

Se inspeccionaron **12 brutos existentes**, RX-01/RX-02 de seis sesiones: referencia
de 60 s, intentos v1, v2, v3 sentado, v3 movimiento libre y primer v4. La herramienta
[revisar_arranque_v4.py](../tools/revisar_arranque_v4.py) solo lee archivos regulares
fijos: registra hashes, offsets, bytes y clasificación, separa por LF y conserva
colas. No importa transporte o detector. Sus relojes internos cero sirven solo
para encuadrar bytes; no se publican como tiempos de adquisición.

Los cinco registros completos previos muestran:

| RX | Orden realmente registrado alrededor de READY |
|---|---|
| RX-01 | Cabecera → READY → `wifi:ic_enable_sniffer` → retorno de `app_main()` → primera CSI. |
| RX-02 | Cabecera → `wifi:ic_enable_sniffer` → identidad/secondary → READY → retorno → primera CSI. |

En v4 **no se observó el arranque completo de RX-01**: termina después de la
cabecera con una cola `I`, sin READY ni CSI. RX-02 muestra el orden de la tabla
hasta el retorno, sin CSI. No se completó esa cola ni se atribuyó a READY.

Ejemplos con offsets desde cero y fin excluyente:

| Sesión/RX | Línea | Bytes | Contenido registrado |
|---|---:|---|---|
| v2 / RX-01 | 90 | [4403, 4435) | `I (536) wifi:ic_enable_sniffer\r\n` |
| v2 / RX-01 | 91 | [4435, 4480) | `I (539) main_task: Returned from app_main()\r\n` |
| v4 / RX-02 | 89 | [4405, 4437) | `I (526) wifi:ic_enable_sniffer\r\n` |
| v4 / RX-02 | 92 | [4624, 4669) | `I (545) main_task: Returned from app_main()\r\n` |

El v4 original conserva la suspensión `post_ready_info:RX-02`, cero slots y ambos
cierres confirmados. Su auditoría histórica sigue con integridad y replay
correctos. No se sustituyeron sus decisiones por las de una política nueva.

## Formatos iniciales y contraste de fuentes

Las clasificaciones siguientes son las de la gramática compartida histórica:

| Formato registrado | Clasificación / contraste | Tratamiento en esta revisión |
|---|---|---|
| Prefijo no UTF-8 pegado a `ESP-ROM:` | `invalid_utf8`, con marcador de reset embebido. Bytes sin interpretación fiable. | Conserva rechazo; no se descarta ni se acepta como log. |
| `I (...) boot.esp32s3: Boot SPI Speed : 80MHz`, modo DIO, tamaño 16MB | `unrecognized_bytes` por el punto del tag. TAG y frases están en `bootloader_flash_config_esp32s3.c`, líneas 102, 200, 225, 256. | Fuera de la corrección mínima; conserva clasificación/motivos. Solo se observó antes de READY. |
| `I (...) wifi:...` sin espacio: tarea, versión, buffers, NVS, modo STA, TSF, PS | `unrecognized_bytes` por el formato sin espacio. Texto registrado compatible con inicialización; el cuerpo C del controlador no está disponible. | No se añade ninguna regla `wifi:.*`. Conserva motivos. No prueba un cambio posterior de configuración. |
| `wifi:ic_enable_sniffer` exacto | Mismo problema sintáctico, con orden distinto por RX verificado en cinco sesiones completas. | Solo la política nueva reconoce este patrón y controla fase, RX y repetición. |
| `main_task: Returned from app_main()` | `info`, emitido explícitamente por SDK al retornar la aplicación. | Excepción acotada por la política nueva; las anteriores no cambian. |
| Cabecera exacta y línea vacía | `neutral`. | Sin cambio; no acreditan disponibilidad. |
| `rst:...`, ROM, errores y READY incompatible | Marcadores de arranque/error/configuración, con su contexto. | No se exceptúan después de READY ni se eliminan del preámbulo. |

En v4 los prefijos anteriores a `ESP-ROM:` ocupan **[0,77)** en RX-01 y **[0,89)**
en RX-02; las primeras líneas terminan en 103 y 115 bytes. Hay **20/21 líneas
iniciales inválidas** según la gramática histórica, más la cola de RX-01. El
sniffer exacto de RX-02 se reconoce bajo la revisión nueva, pero siguen existiendo
otros motivos y el prefijo binario. Ninguno se borra. El origen de esos bytes y
su relación con la apertura/reset eléctrico siguen indeterminados.

ESP-IDF local sigue fijado en v5.4, commit
`67c1de1eebe095d554d281952fde63c16ee2dca0`. Se verificaron hashes y blobs Git de
las dos aplicaciones y las fuentes SDK inspeccionadas. Las bibliotecas precompiladas
`libpp.a`/`libnet80211.a` se fijan por hash; contienen los símbolos de sniffer y
modo promiscuo. La inspección de objetos muestra la llamada a `ieee80211_ioctl`
desde `esp_wifi_set_promiscuous`, pero **no proporciona el cuerpo C del driver**
ni demuestra exhaustivamente el instante de emisión de todos sus logs. No se
atestan bibliotecas/binarios instalados en las placas.

En ambas aplicaciones `csi_writer` imprime una cabecera y espera la cola; se crea
con prioridad 4. `ESP_TASK_MAIN_PRIO` en el SDK es 1. El orden explícito es:

- [RX-01](../firmware/csi_recv/main/app_main.c): crear cola/tarea → READY (273)
  → `wifi_csi_init()` (274) → retorno. Dentro de esa función (187–237): promiscuo
  → configuración CSI → callback → habilitar CSI.
- [RX-02](../firmware/csi_recv_02/main/app_main.c): crear cola/tarea →
  `wifi_csi_init()` (273) → comprobar canal/banda → identidad (288) → READY (290)
  → retorno. Los errores de configuración abortan antes del READY.
- SDK `app_startup.c` (206–210): llamar `app_main()` → imprimir retorno → borrar
  tarea principal. No elimina por sí mismo `csi_writer` ni ordena un reset.

No existe un bloqueo que mantenga la tarea CSI parada hasta el log de retorno.
La cabecera puede interponerse y, una vez habilitado CSI, pueden aparecer filas
antes del retorno; en RX-02 incluso antes de READY. Estas son **posibilidades
derivadas de las fuentes**, no secuencias físicas adicionales observadas aquí.
El SDK escribe logs con `vprintf`; la fila CSI propia usa varios `printf` sin
un lock común de fila. Si hay mezcla de texto dentro de una fila, se conserva y
rechaza; no se presume atomicidad ni se reconstruye una fila válida.

## Corrección mínima y pruebas

`v4-app-main-return-1` todavía suspende por el sniffer de RX-01, y por un retorno
separado de READY por cabecera, sniffer o CSI. La nueva
[política `v4-startup-sequence-1`](../docs/POLITICA_LINEAS_V4_STARTUP_SEQUENCE_V1.md)
reconoce únicamente las dos frases exactas, una vez, con orden específico por RX,
dentro de los 10 s originales y sin suspensión/cierre; el sniffer debe preceder
a toda CSI de ese RX. Espera los retornos de
ambos RX antes de disponibilidad y exige tres filas frescas después. No cambia
el perfil CSI ni su validación/continuidad, duración, cobertura o etiquetas.

La revisión conserva un límite deliberado: un sniffer posterior a READY en RX-02,
otro texto, ANSI, duplicados, retorno tardío, mensajes fuera de orden o una fila
mezclada siguen suspendiendo. Las fuentes disponibles no justifican aceptar
genéricamente esas variantes. No se modifica la gramática compartida, las
plantillas o las dos políticas anteriores; plan/procedencia/auditor siguen
seleccionando explícitamente la revisión de cada bundle.

[22 pruebas nuevas](../tests/test_v4_startup_sequence.py) distinguen los órdenes
registrados de las reconstrucciones sintéticas: cortes de byte, LF/CRLF,
cabeceras y CSI interpuestos, CSI previo a READY de RX-02, gate/timeout, órdenes
incompatibles, repeticiones, ANSI/texto añadido, resets/errores/READY incorrecto,
todos los campos del perfil fijo, gaps/reinicio de contador/reloj/drops, línea
excesiva/mezclada y cola. Incluyen dos ventanas PTY completas y el adaptador serial
sobre PTY propios; bundles nuevos se auditan y metadatos inconsistentes se rechazan.

El análisis de los 12 brutos y su reducción con relojes sintéticos es una prueba
offline de conservación/rechazo, **no replay histórico ni evidencia física de la
política nueva**. El único replay del intento v4 usa su política histórica. Las
dos ventanas elegibles de las pruebas son exclusivamente sintéticas; no entrenan,
calibran o validan un detector de presencia.

Pasaron **210 pruebas, cero fallos, errores u omisiones, 17,344 s**:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python -B -m unittest \
  test_uart_v4 test_persistent_presence_v4 test_availability_window \
  test_controlled_v2 test_controlled_v3 test_capture_preparation \
  test_capture_boundaries test_boundary_diagnostic test_v4_line_policy \
  test_v4_startup_sequence -v
```

La inspección de formatos se reproduce, con salida nueva exclusivamente:

```bash
.venv/bin/python -B tools/revisar_arranque_v4.py --output-new /tmp/revision-arranque-nueva.json
```

Bubblewrap vuelve a fallar con código 1 al crear namespaces. Las pruebas directas
en el entorno restringido no acreditan aislamiento Bubblewrap; no se cambió el
wrapper. No fue necesaria compilación de firmware ni pruebas de modelos/gráficos.

## Preservación y bloqueo concreto

Se verificaron **2355 archivos previos intactos** por tamaño y SHA-256: datos,
resultados locales, fuentes firmware, protocolos/políticas anteriores y plantillas,
incluidas las autorizaciones consumidas. Artefactos separados en
`results/local/revision-arranque-v4-20261101/`: inventario de formatos con bytes,
fuentes/hashes e inspección de bibliotecas, logs de pruebas, auditoría histórica y
manifiestos de preservación. [Resumen versionado](REVISION_ARRANQUE_V4.validacion.json).

Falta resolver el contrato del **preámbulo completo** antes de preparar una nueva
conexión destinada a ventanas E/S elegibles. La regla de elegibilidad actual
requiere conexión conforme; los prefijos binarios y demás formatos iniciales
registrados la impiden, aunque READY/ventana pasaran después. Aceptar ese prefijo
sin una interpretación verificable o descartarlo solo para aprobar no es una
corrección justificada. Los archivos existentes no permiten demostrar su causa
ni una forma autorizada de evitar que se repita.

Se necesita una decisión técnica separada y explícita sobre ese preámbulo, con
pruebas que conserven bytes y detección de anomalías, o una investigación física
específica autorizada en otra sesión. No se traslada ese problema sin resolver a
una campaña E/S ni se generan nuevas autorizaciones. Montaje, audibilidad y
binario instalado tampoco se reconfirman con esta revisión. No hubo UART,
captura, reset, reconexión, cambio de firmware o calibración del detector.
