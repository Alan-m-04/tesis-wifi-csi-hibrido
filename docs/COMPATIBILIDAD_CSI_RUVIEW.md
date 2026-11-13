# Correspondencia CSI ESP32-S3 / RuView

Segundo hito, 24 de octubre de 2026. Rama `feat/compatibilidad-csi-ruview` creada desde `74d612a87fa02021a30a7a034595e4aa5575dbb7`, con árbol inicial limpio. **La conversión compleja elemental es demostrable; el transporte ADR-018 directo no conserva la semántica de esta captura.** No se implementa UDP, geometría artificial, adaptador de producción ni entrenamiento.

## Fuentes y alcance de la demostración

Se fijan los archivos, tamaños, SHA-256 y enlaces permanentes en [FUENTES_CSI_RUVIEW.json](FUENTES_CSI_RUVIEW.json). No se usó `main` flotante para decidir el contrato.

| Referencia | Evidencia inspeccionada |
|---|---|
| E1 | [ESP-IDF instalado, commit 67c1de1, guía CSI, líneas 2210–2264](https://github.com/espressif/esp-idf/blob/67c1de1eebe095d554d281952fde63c16ee2dca0/docs/en/api-guides/wifi.rst#L2210) y [guía publicada v5.4 para ESP32-S3](https://docs.espressif.com/projects/esp-idf/en/v5.4/esp32s3/api-guides/wifi.html#wi-fi-channel-state-information) |
| E2 | [Tipos nativos del mismo IDF, líneas 37–133](https://github.com/espressif/esp-idf/blob/67c1de1eebe095d554d281952fde63c16ee2dca0/components/esp_wifi/include/local/esp_wifi_types_native.h#L37): metadatos, configuración y buffer |
| F | Fuentes locales `firmware/csi_recv/main/app_main.c` y `firmware/csi_recv_02/main/app_main.c`, callback/escritor 138–185 y configuración S3 225–233; SHA del inventario base conservados |
| C | `src/capture_csi.py` y `src/capture_csi_multi.py`, copias base intactas; lectura por bloque 158–159 y exportación 219 |
| D | Siete archivos físicos de referencia fijados en `data/dual_60s_20261024.manifest.json`; estadísticas y hashes en `results/auditoria_csi_ruview.json` |
| R1 | [ADR-018, tabla y pseudocódigo 35–95](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/docs/adr/ADR-018-esp32-dev-implementation.md#L35) |
| R2 | [Serializador efectivo, csi_collector.c 154–280](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/firmware/esp32-csi-node/main/csi_collector.c#L154), configuración S3 678–686 |
| R3 | [Parser Rust hardware 225–304](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/v2/crates/wifi-densepose-hardware/src/esp32_parser.rs#L225) y [conversión a fase](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/v2/crates/wifi-densepose-hardware/src/csi_frame.rs#L22) |
| R4 | [Parser efectivo del servidor Rust 3708–3798](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/v2/crates/wifi-densepose-sensing-server/src/main.rs#L3708) |
| R5 | [Parser Python binario archivado 133–274](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/archive/v1/src/hardware/csi_extractor.py#L133), distinto del parser textual de esa clase/módulo |
| R6 | [Recorder Python 21–83](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/scripts/record-csi-udp.py#L21) y [conversor JSONL/RVCSI 127–147](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/scripts/esp32_jsonl_to_rvcsi.py#L127) |
| R7 | [JavaScript graph 542–571](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/scripts/csi-graph-visualizer.js#L542), [spectrogram 99–124](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/scripts/csi-spectrogram.js#L99) y [UI pose-fusion 286–304](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/ui/pose-fusion/js/csi-simulator.js#L286) |

Checkout separado: `/home/alan-monar/auditorias-externas/ruview-fefb0f918eef`, HEAD detached `fefb0f918eefa7db6daef8cc83787fc7d6f74187`. Licencia raíz MIT. No se ejecutaron instaladores ni se instalaron dependencias. Solo se reutilizan dos funciones Python puras revisadas de R6 para pruebas, con licencia adjunta; las CLI de sockets no se importan ni ejecutan. IDF instalado: `67c1de1eebe095d554d281952fde63c16ee2dca0`, v5.4, inspeccionado sin modificarlo. El driver Wi-Fi no ofrece aquí una implementación pública completa de sus cálculos PHY: no se afirma haber verificado sus coeficientes internos.

## Complejos, LTF, índices y escala

**Comprobado documentalmente y en el camino fuente:** E1 define dos int8 por respuesta: imaginario primero y real después. F copia `info->buf` con `memcpy`, lo mantiene en `int8_t[]` y recorre sus posiciones de 0 a `len-1` al imprimir; C conserva los campos. Por tanto, la interpretación matemática del par es `z[k] = data[2*k+1] + j*data[2*k]`. No es una calibración de fase RF. Las pruebas con signos, cuatro cuadrantes, -128/127 y conjugación evitan que una prueba solo de amplitud oculte un error.

**Modelo documentado condicionado, no inferencia solo por tamaño:** las 583 filas duales contienen `sig_mode=1`, `bandwidth(cwb)=0`, `secondary_channel=0`, `stbc=0`, `mcs=0`, `ant=0`, `len=256` y `first_word_invalid=0`. La rama S3 de F habilita LLTF y HT-LTF (además de STBC-HT-LTF2, que no aporta bloque en paquetes sin STBC). E1 prescribe para esas condiciones LLTF seguido de HT-LTF: 128 bytes por bloque, 64 pares cada uno, **dos respuestas de entrenamiento de la misma rejilla**, no dos antenas ni 128 frecuencias distintas. El modelo restringido `documented_ht20_layout` exige los metadatos y configuración explícitos antes de comprobar la longitud. No escribe etiquetas retrospectivas en las capturas ni certifica qué binario estaba instalado.

En cada bloque HT20 sin canal secundario, el orden de índices de E1 es `0..31,-32..-1`. No se aplica fftshift ni se elimina DC sin registro. Los roles nominales son:

| Bloque | Activas sin DC | Pilotos | Datos | DC/guardas del buffer de 64 |
|---|---|---|---|---|
| LLTF | -26..-1,+1..+26 (52) | -21,-7,+7,+21 | 48 | DC=0; guardas -32..-27,+27..+31 (11) |
| HT-LTF | -28..-1,+1..+28 (56) | -21,-7,+7,+21 | 52 | DC=0; guardas -32..-29,+29..+31 (7) |

Estos son índices/roles nominales de la documentación, no una demostración física de cada tono. No se deducen a partir de ceros observados. E1 advierte que en STBC el índice 0 de HT/STBC puede contener información CSD, no respuesta de canal: aquel caso queda fuera del modelo. HT40, otros canales secundarios, STBC o LTF deshabilitados requieren otra tabla; no se reinterpretan con esta geometría.

`first_word_invalid=true` invalida **cuatro bytes iniciales**, es decir, dos pares globales, no cuatro subportadoras por bloque. El helper mantiene las posiciones como desconocidas (`None`), sin rellenar ceros ni desplazar índices. En estos datos duales todas las banderas son 0. Los pares exactamente cero tienen amplitud cero y fase no medible; una fase numérica `atan2(0,0)=0` no constituye evidencia de fase.

**Configuración y límites de recuperación:** E2 define `ltf_merge_en=true` como generación HT-LTF mediante promedio de LLTF y HT-LTF. No habilita una segunda antena ni convierte los dos bloques en frecuencias consecutivas. `channel_filter_en=true` suaviza subportadoras adyacentes; deshabilitarlo preserva su independencia según la API. Ambos RX propios usan merge y filtro activos, `manu_scale=false`, `shift=0`: escalado automático, sin factor por muestra exportado. Con `manu_scale=true`, `shift` controla el desplazamiento manual a izquierda según la API; no es una normalización intercambiable con autoescala y no permite recuperar pérdidas por cuantización/saturación. RuView R2 mantiene merge y autoescala, pero configura el filtro en **false**. Los datos no son equivalentes por configuración; no es posible deshacer el filtrado ni recuperar el HT-LTF previo al promedio de forma demostrada. `smoothing=1` en rx_ctrl es recomendación/metadato del paquete, no prueba del valor de `channel_filter_en`. El valor int8 no representa ganancia de canal calibrada ni escala absoluta comparable entre sesiones, RX o modelos. El filtro exacto, AGC y factor automático quedan pendientes de evidencia PHY/calibración.

F describe la configuración de las fuentes verificadas, y la cabecera READY/los metadatos corroboran parte del perfil; no se ha leído firmware de las placas ni se posee una atestación de hash del binario que produjo la sesión. La segmentación LTF es un modelo sólidamente documentado y consistente con el registro, pero esa asociación histórica no se promueve a prueba del firmware instalado.

## ADR-018 y parsers efectivos: contratos distintos

| Camino auditado | Contrato complejo y tamaño | Discrepancias y consecuencias |
|---|---|---|
| ADR-018 R1 | Cabecera LE de 20 bytes, payload rotulado I/Q, pseudocódigo copia `info->buf` | El rótulo I/Q contradice Im/Re de E1; usa `rx_ctrl.ant` como número de antenas aunque es índice (nuestro 0 sería inválido). Rotula frecuencia Hz con ejemplo 2412, pero código almacena MHz. No basta usar el documento como especificación efectiva. |
| Serializador real R2 | Fija antenas=1; `n_sub=len/2`; copia Im/Re sin permutar | Conserva pares de distintos LTF bajo una sola cuenta. Frecuencia MHz. Secuencia propia de serialización, no TX. Bytes 18/19 pasan de reservados a PPDU/flags según configuración; si hay primer word inválido, pone los primeros cuatro bytes a cero y flag bit5. Se pierde valor bruto si no se guarda aparte. |
| Rust hardware R3 | Lee primero como I/real y segundo como Q/imag; `atan2(q,i)` | Copia literal R2 da `z'=j*conj(z)`, fase `pi/2-phi`, amplitud igual. Genera índices simétricos sin DC en lugar del orden FFT por LTF. Para HT/legacy, cuenta >64 implica 40 MHz; nuestros 128 pares HT20 se clasificarían incorrectamente. Timestamp creado al parsear. |
| Rust servidor R4 | Cabecera 20, pares int8, primera componente real, `atan2(q,i)` | Mismo intercambio frente a E1. Preserva PPDU/flags, no transmite reloj RX en cabecera. No asumir que comparte toda la lógica del parser hardware; incluso normaliza RSSI positivo a negativo. |
| Python binario archivado R5 | Primera componente I/real, segunda Q/imag, NumPy `arctan2(q,i)` | Mismo error de fase si recibe copia cruda Im/Re; cuenta 128 lleva a 40 MHz y otros tamaños a 80/160 MHz por heurística. No es el parser textual `CSI_DATA:...`, que tampoco acepta nuestro CSV de 26 campos. No se ejecutó ni instaló NumPy. |
| Python recorder R6 | 20 bytes, int8, amplitud redondeada a 2 decimales y `iq_hex` exacto | No calcula fase: amplitud no certifica convención. Impone `n_sub<=256`, distinto del Rust hardware actual (hasta 1024 pares totales, 4 antenas). Dos funciones puras reales de este archivo sí se probaron offline. Timestamp nuevo del recorder no conserva el instante histórico. |
| Python conversor JSONL→RVCSI R6 | Interpreta `iq_hex` como Im/Re y hace `I=real,Q=imag`, fase correcta | **No coincide con R3/R4/R5**. Intercambiar los bytes antes de este conversor desharía la corrección. Mantiene cuenta de pares como subportadoras, fija banda a 20 MHz sin validarla por metadatos, descarta noise_floor y aplica política propia de degradación sin resolver LTF. Inspeccionado, no ejecutado. |
| JS graph R7 | UDP 20 bytes, pares int8 con signo, amplitud sin fase | No detecta permuta/conjugación. Solo recorre `nSubcarriers`, sin separar antenas/LTF. Su ruta hex comienza en offset 2, perdiendo el primer par y dejando el último sin completar en ese contrato. No es validación de fase. |
| JS spectrogram R7 | Declara cabecera de 20 bytes pero RSSI @5 y tamaño @8; lee payload sin convertir signo | Incompatible con ADR-018 efectivo, aunque coincide el magic. @5 real es cuenta de antenas y @8 frecuencia; int8 negativos leídos como unsigned alteran incluso amplitud. No elegir esta ruta para la base. |
| JS UI pose-fusion R7 | Lee cuenta @8; pares int16 LE real/imag, 4 bytes por par; amplitud /2048 | Incompatible con cuenta @6 e int8 de R2. La fase local `atan2(imag,real)` no repara offsets/tamaño incorrectos. No se demuestra compatibilidad visual de esta UI. |

Ejemplo sintético explícito: bytes `[-4,3]` representan `3-4j`, amplitud 5 y fase -0,927295 rad. R3/R4/R5 los leen como `-4+3j`, amplitud 5 y fase 2,498092 rad. Tampoco la conjugación se detecta por amplitud. Una permuta por pares serviría para el contrato real/imag de estos parsers, pero sería incorrecta para el conversor R6 que ya interpreta Im/Re. No se aprueba una permuta universal ni se produce un paquete de captura real.

La anchura real proviene de `rx_ctrl.cwb`, no de `len`, cantidad de pares ni magnitudes. Byte 19 bw40=0 no resuelve la heurística HT/legacy en R3/R5, que sigue usando la cuenta. El `ant=0` recibido es selección de antena, no cero antenas; tampoco los dos USB forman una captura coherente de dos antenas.

## Tabla por campo del registro original y CSV

Los destinos siguientes son **evaluación de correspondencia**, no un adaptador ya implementado. «Lateral» significa metadato que debe conservarse junto al bruto, con vínculo por hash/sesión/fila: la cabecera ADR-018 no lo contiene. E1/E2/F/C/D y R1–R7 se definen arriba. Nunca sustituir «no disponible» por cero inventado.

| Campo | Origen | Interpretación | Destino candidato | Transformación demostrable | Información perdida si solo ADR-018 | Evidencia |
|---|---|---|---|---|---|---|
| type | Escritor RX | Literal CSI_DATA | Lateral/esquema | Validar literal | Tipo CSV original | F,C,D |
| id | callback_id++ tras filtro MAC | Contador local RX; incrementa incluso ante descarte posterior | Secuencia local + lateral | uint32 solo si se declara semántica | Diferencia con secuencia serializada RuView y con TX | F,R2 |
| mac | info->mac | Fuente del paquete; TX fijo | Lateral | Conservar seis bytes | Fuente no está en ADR-018 | E2,F,D |
| rssi | rx_ctrl.rssi | int8 dBm del paquete | Byte16 | int8 con signo, sin normalizar | Resolución/calibración no mejoran | E2,F,R2,R4 |
| rate | rx_ctrl.rate | Codificación PHY solo válida non-HT; aquí sig_mode=1 | Lateral | Conservar 11 como bruto, no Mbps | Metadato bruto; no tasa HT demostrada | E2,D |
| sig_mode | rx_ctrl.sig_mode | 1=HT, 0=non-HT | Lateral; PPDU @18 categoría 0 | HT y legacy comparten categoría upstream | Distinción HT/non-HT | E2,R2 |
| mcs | rx_ctrl.mcs | MCS HT observado 0 | Lateral | Entero original | Modulación/codificación | E2,D |
| bandwidth | rx_ctrl.cwb | 0=20 MHz,1=40 MHz | Lateral autoritativo; flag bit0 | Mantener 20 MHz explícitos | Heurística downstream puede contradecirlo | E2,R3,R5 |
| smoothing | rx_ctrl.smoothing | Recomendación PHY, no valor de filtro CSI | Lateral | Sin inferir filtro efectivo | Recomendación original | E2,F |
| not_sounding | rx_ctrl.not_sounding | 1=no sounding PPDU | Lateral | Sin inversión semántica inadvertida | Condición del entrenamiento | E2 |
| aggregation | rx_ctrl.aggregation | 0=MPDU,1=AMPDU | Lateral | Entero original | Condición de agregación | E2 |
| stbc | rx_ctrl.stbc | 0=sin STBC aquí | Flag bit2 + lateral | Booleano solo para flag | Valor/semántica original y bloques | E1,E2,R2 |
| fec_coding | rx_ctrl.fec_coding | LDPC en HT | Flag bit3 + lateral | Contrato define LDPC; serializador auditado no lo rellena | Se pierde si solo se confía en flags upstream | E2,R2 |
| sgi | rx_ctrl.sgi | 0=GI largo,1=corto | Lateral | Sin cambio | Guard interval | E2 |
| noise_floor | rx_ctrl.noise_floor | int8 dBm | Byte17 | Signo conservado; no SNR CSI calibrado | SNR solo resta aproximada si consumidor la usa | E2,R5 |
| ampdu_cnt | rx_ctrl.ampdu_cnt | Número de subframes AMPDU | Lateral | Sin cambio | Conteo | E2 |
| channel | rx_ctrl.channel | Canal primario observado 11 | Frecuencia @8 + lateral | 2412+5*(11-1)=2462 MHz | Número original si no se guarda; no ancho | E2,R2,R6 |
| secondary_channel | rx_ctrl.secondary_channel | 0=ninguno;1=arriba;2=abajo | Lateral | Sin cambio | Ubicación secundaria | E1,E2 |
| local_timestamp | rx_ctrl.timestamp | Recepción local uint32 microsegundos | Lateral autoritativo | Preservar entero/wrap; no convertir a UTC sin ancla | Reloj RX completo ausente de ADR-018 | E2,F,D |
| ant | rx_ctrl.ant | Índice 0/1, no número de antenas | Lateral; cuenta separada | Nunca escribir directamente en n_antennas | Selección original | E2,R1,R2 |
| sig_len | rx_ctrl.sig_len | Longitud paquete incluido FCS, aquí 47 | Lateral | No confundir con longitud CSI | Longitud del paquete | E2,D |
| rx_state | rx_ctrl.rx_state | 0=sin error; otros códigos no públicos | Calidad y lateral | Rechazar/informar según validador | Estado de recepción | E2,C |
| len | info->len | Bytes totales de CSI, aquí 256 | Lateral; cantidad de pares como dato distinto | Verificar lista y LTF antes de n_sub | Fronteras y nombres LTF | E1,F,R2 |
| first_word_invalid | info->first_word_invalid | Primeros cuatro bytes inválidos | Máscara lateral; upstream bit5 si sanitiza | Marcar dos pares, conservar bruto | Sanitización upstream reemplaza valores por 0 | E1,E2,R2 |
| queue_drops | Contador firmware | Rechazos por tamaño/cola desde callbacks filtrados | Lateral/calidad | Conservar incremento y reinicios | Descartes locales; no mide pérdida RF | F,C |
| data | info->buf int8 | Im,Re por par, LTF concatenados | Complejos offline + bruto; contrato consumidor explícito | Re+jIm, sin normalizar ni forzar geometría | Fase errónea si permuta equivocada; LTF/guardas/escala sin lateral | E1,F,R2–R7 |
| session_id | Capturador | Aquí literal genérico captura | Identidad externa y lateral | Vincular a run global+hash, no renombrar original | Sesión global ausente de ADR-018 | C,D |
| receiver_id | Capturador | RX-01 o RX-02 | Lateral; node_id requiere tabla explícita | Conservar rol/serie, no derivar de ttyACM | Identidad textual | C,D |
| usb_serial | Identidad USB verificada históricamente | 5C93199744 / 5C93200689 | Tabla node_id→USB y lateral | Mapeo futuro versionado, no unión como antenas | Identidad física USB | C,D |
| host_timestamp_utc | Capturador tras read | Hora UTC de lectura del bloque | Lateral; no timestamp de RF | Preservar texto/offset; varias filas pueden compartirlo | Recorder/parser RuView crean tiempo nuevo | C,R3,R5,R6 |
| host_monotonic_ns | Capturador tras read | Entero ns host por bloque | Lateral entero/string sin float | Mantener igualdad y precisión; no interpolar | Tiempo/epoch monotónico ausente; JSON JS Number puede redondear enteros grandes | C,D |

E2 también contiene `dmac`, `hdr`, `payload`, `payload_len`, `rx_seq`; F no los exporta. No se puede reconstruir la secuencia TX, demostrar emparejamiento RF entre RX ni recuperar cabeceras/payload a partir del contador local o de CSI parecido. La configuración merge/filtro/autoescala tampoco viaja por fila: debe identificarse en el manifiesto de la ejecución con firmware verificable.

## Relojes y evidencia real

Los 292 y 291 timestamps host de esta referencia son distintos dentro de cada RX (ningún grupo repetido observado). **Eso no es una garantía del formato:** C toma un solo par host UTC/monotónico por `read`; todas las filas de ese bloque lo comparten. Una prueba sintética verifica tres filas con el mismo timestamp y aceptación offline sin interpolación. No se asignan tiempos individuales ficticios ni se estima sincronización RF por el inicio común. El reloj uint32 local puede envolver cada 4294,967296 s y solo es preciso según E2 si no hay modem/light sleep; las fuentes llaman WIFI_PS_NONE, sin demostrar externamente el estado físico de aquella sesión.

No se alinean IDs iguales entre placas, ni se convierten sus relojes a uno común. Los intervalos observados ~196–400 ms no prueban pérdidas de TX ni latencia unidireccional. La tasa media de la ventana solicitada es 4,867/4,850 Hz; no se remuestrea a 20,100 u otra frecuencia requerida por modelos.

## Ruta mínima respaldada y bloqueos

Respaldado ahora: **bruto/CSV propio intacto → validación estricta y metadatos originales → interpretación compleja offline Im/Re, máscara explícita y modelo LTF condicionado**. Guardar configuración, hash de firmware, receptor, sesión y reloj junto al dato. Se pueden ensayar contratos de fase offline; no afirmar que RuView o un modelo funciona con estos datos.

Para integrar después hay que elegir un único consumidor efectivo y su revisión. Para R3/R4/R5 se necesita un contrato explícito Re/Im y corregir/reemplazar la inferencia de banda/índices; para R6 conversor se conservan bytes Im/Re. En cualquiera de las rutas faltan preservación lateral verificable, decisión explícita sobre bloques/guardas/DC/pilotos, tratamiento de merge/filtro/escala, tiempo de adquisición en replay e identidades. No se seleccionan 56 tonos a ciegas ni se hacen pasar dos LTF por antenas. El recorder R6 puede conservar bytes para inspección, pero su timestamp nuevo y cuenta de pares no bastan para una reproducción científica de esta sesión.

Pendiente de demostración física: relación binario/configuración por sesión, respuesta por tono y calibración/escala, fase RF estable, eventual sincronización si el algoritmo la exige. Pendiente de software: ejecutar contratos con runtimes reales JS/Rust y dependencias aprobadas; evaluar el consumidor elegido con su geometría real. Node y rustc no están disponibles aquí y no se instalaron. No hay modelo con pesos/compatibilidad validados ni campaña etiquetada suficiente; este hito mantiene el alcance del anteproyecto y el firmware ESP-IDF v5.4 sin modificaciones.
