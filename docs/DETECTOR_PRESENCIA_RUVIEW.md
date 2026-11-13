# Selección de detector de presencia RuView y operatividad

**Decisión:** seleccionar el componente Rust **`wifi-densepose-calibration::PresenceSpecialist`**, aislado, para un futuro adaptador **offline** de media/varianza de amplitud. Estado: **seleccionado para integración; bloqueado para afirmar presencia validada**. No se ejecutó el detector, ajustó calibración, entrenó un modelo ni produjo puntuaciones nuevas sobre la sesión quieta. Ningún UART abierto ni captura nueva.

La dependencia sigue en **`fefb0f918eefa7db6daef8cc83787fc7d6f74187`**, licencia raíz MIT; el crate wasm-edge declara MIT OR Apache-2.0. Se inspeccionó el checkout local limpio y se contrastaron **31 archivos con los blobs Git de ese commit**. [Inventario de fuentes y hashes](DETECTOR_PRESENCIA_RUVIEW.fuentes.json). No se necesita otra versión para esta selección; no se actualizó ni instaló la dependencia.

## Rutas ejecutables inspeccionadas

Son implementaciones con funciones/clases y puntos de llamada, no promesas de documentación. «Ejecutable» no significa que hayan sido compiladas o validadas aquí. Las funciones Rust requieren compilación; `cargo`/`rustc` no están disponibles en el PATH observado y no se instalaron.

| Ruta del commit fijado | Tipo e interfaz efectiva | Calibración, tiempo y dependencias | Decisión |
|---|---|---|---|
| `harness/ruview/src/devices/esp32.js`: `parsePacket`, `SpectrumCollector` | Parser/estadísticas, **no detector de presencia cruda**. También decodifica flags/puntuaciones ya emitidos por firmware. Node y `node:dgram`. | El puente local ejecuta solo funciones en memoria y conserva tiempos/máscaras en el canónico. Leer un flag no calcula presencia desde nuestras amplitudes. | Mantener el puente existente como representación, sin atribuirle un detector que no contiene. |
| `scripts/c6-presence-watcher.py` | Puente heurístico de un `feature_state` de 60 bytes, magic `0xC5110006`, CRC y bit `PRESENCE_VALID`; recibe `presence_score` **ya calculado**. Python estándar, UDP/HAP/archivo de estado. | ON/OFF 0.40/0.20, liberación por 5 s sin paquetes; ocupación promedia 3 s con 0.30/0.15. El contrato declara ventanas de firmware de 100 ms/1 s. No recibe nuestro CSV ni genera esa puntuación desde él. | Bloqueado: nuestras fuentes no emiten ese paquete/score; requeriría otra fuente/firmware. No flashear para hacerlo funcionar. |
| `scripts/through-wall-detector.js`: `ChannelBaseline`, `ThroughWallDetector` | Heurística de desviación por tono: Welford y media de z absolutos, ponderación/coherencia entre canales. Node estándar; CLI UDP o replay. | Baseline inicial 30 s por defecto, mínimo 5 filas/canal; sigma mínima 0.1; umbral 2.5 y racha 3. Diseñado para hopping 1,3,5,6,9,11. La clave de baseline es canal, no RX. Parser `iq_hex` empieza en byte 2. | No elegir el sistema multifrecuencia: solo tenemos canal 11, RX distintos y LTF/máscaras laterales. No inventar canales, emparejamiento o el par perdido por ese parser. |
| `firmware/esp32-csi-node/main/edge_processing.c`: `process_frame` | Heurística **en firmware RuView**, no pesos entrenados. IQ interpretado Re/Im, fase desenvuelta, top-K por varianza, presencia = energía de fase reciente con histéresis. C/ESP-IDF, FreeRTOS, pipeline/ring/NVS propios. | Energía usa últimas ≤20 fases, empieza con ≥10; auto-calibración 1200 frames, umbral media+3 sigma (mínimo 0.01), provisional 0.05; histéresis 0.5 y salida tras 5 frames bajos. Mide tasa por ventanas pero la acota a **8–60 Hz** para filtros; defaults C6 8/S3 20. A 5 filas/s, 1200 serían ~240 s y 20 ~4 s, sin preservar el supuesto temporal de origen. | No ejecutar/flashear: fase/IQ y rejilla requieren adaptación, ~5/s queda bajo el piso del estimador y faltan 1200 frames vacíos continuos. La existencia de este algoritmo no significa que nuestras placas lo tengan. |
| `wifi-densepose-wasm-edge/src/occupancy.rs`: `OccupancyDetector::process_frame` | Heurística de amplitud por grupos de cuatro tonos llamados «zonas»; usa longitud de fases para limitar entrada, sin procesar sus valores. Rust/no_std/libm. | Máximo 32 tonos, baseline de **200 frames**, EMA 0.15 por llamada, umbral relativo 0.02/0.01 y emisión cada 10 frames. A ~5/s son ~40 s antes de salir de calibración; una ventana de 150 filas no alcanza. | No elegir: no hay mapeo demostrado tono→zona espacial, necesita selección de 32/máscaras y baseline adicional. No reinterpretar grupos como mapa físico ni reducir 200 para caber en 30 s. |
| `bld_hvac_presence.rs`: `HvacPresenceDetector::process_frame`; `tools/ruview-mcp/.../presence-now.ts` | Consumidores de presencia ya estimada. HVAC recibe `presence_score`/motion; MCP devuelve `fetchVitals().presence`. Rust/libm o TypeScript/zod/servicio HTTP. | HVAC umbral 0.5, llegada 200 frames y salida 6000 (comentarios asumen 20 Hz: 10 s/5 min; a 5/s serían 40 s/20 min). MCP no calibra ni extrae CSI. | No son una ruta primaria desde nuestro CSV. No inventar el score de entrada ni tratar respuesta API como validación. |
| `archive/v1/src/sensing/classifier.py`: `PresenceClassifier` y `RssiFeatureExtractor` | Heurística Python de **RSSI**, regla de varianza ≥0.5 dBm²; movimiento por energía ≥0.1. Extractor NumPy/SciPy, imports `v1.src...` del archivo histórico. | Ventana reciente 30 s y ≥4 muestras; estima tasa de timestamps con fallback 10 Hz; FFT usa malla uniforme/bandas hasta 3 Hz. No aprendizaje ni baseline vacío explícito en el clasificador. | RSSI se conserva y podría ser comparador futuro, pero amplitud CSI no es RSSI. Umbral empírico/FFT y confianza de «quieto» no se validan con nuestros ~5/s irregulares. Restaurar imports/aislar solo la regla sería otra adaptación. No se elige un detector de varianza RSSI como evidencia de presencia quieta. |
| `wifi-densepose-signal/src/motion.rs`: `MotionDetector::detect_human` | Heurística, sin pesos entrenados: `CsiFeatures` de amplitud, fase, correlación y Doppler opcional; combina indicadores, EMA y umbral. | Por defecto 0.8 presencia, 0.3 movimiento, 0.1 amplitud, 0.05 fase, smoothing 0.9/historia 100 llamadas. `calibrate` fija una varianza de referencia; adaptación opcional tras 10 llamadas. Depende del crate signal/core, ndarray, FFT, chrono/serde y más crates del workspace. | Más supuestos que el head de dos estadísticas: fase no calibrada y unidades/umbrales empíricos incompatibles sin demostrar. 100 llamadas serían unos 20 s solo si se llama una vez por fila a 5/s. |
| `wifi-densepose-sensing-server/src/main.rs`: `extract_features_from_frame`, `raw_classify`, `smooth_and_classify_node` | Heurística completa de amplitudes/historia por nodo; umbrales de score 0.04/0.12/0.25. Servidor Tokio/UDP/WebSocket/HTTP, no consumidor directo del CSV. | Historia 100 frames; ruta de nodo mide tasa de llegada y usa EMA temporal ~0.6154 s, baseline ~33.28 s, warmup 5 s y debounce 0.4 s. Hay otras rutas con alpha/rachas por frame: no confundirlas. Replay acelerado medido con `Instant::now()` no conserva el reloj registrado. | No instalar el servidor para el primer detector. «Motion/breathing band power» allí divide mitades de tonos; no demuestra banda temporal. Mezcla más rasgos y supuestos de escala. |
| `mediatek_heuristic.rs`: `DeviceHistory::observe` | Heurística por dispositivo para snapshots MediaTek de amplitud media; sin pesos aprendidos. Rust/std, integrado al servidor; pico aceptado pero sin uso en decisión. | Ventana temporal 10 s, retención 10 s y ausencia confirmada 3 s; CV 0.05/desviación baseline 0.08, EMA baseline 0.02 **por muestra**, confianza <0.3 ⇒ desconocido. Baseline nace de primera muestra y deriva aunque haya ocupación; umbrales proceden de otra fuente/escala. | Es una alternativa dimensionalmente posible con adaptador/reloj real, pero introduce baseline ocupado posible, histéresis y umbrales empíricos no calibrados aquí. Se prefiere el head de dos estadísticas con referencia vacía/ocupada explícita para una inferencia por sesión. No trasladar comentarios de «validado» del servidor a esta tesis. |
| `ruvsense/field_model.rs` y servidor: ocupación calibrada por subespacio/residual | Modelo estadístico calibrado con habitación vacía, covarianza/modos y ventanas de 50 frames. | Defaults: **600 s y ≥1000 frames** de calibración; 6 links, 56 tonos; caducidad 24 h. `eigenvalue` añade BLAS/ndarray-linalg; existe fallback sin ese feature, no equivalencia automática. | Bloqueado para este piloto de ventanas 30 s: falta calibración vacía larga y binding real de grid/link. No reducir gates de producción a valores de tests ni concatenar sesiones para simular 600 s continuos. |
| `adaptive_classifier.rs`: `AdaptiveModel` | Modelo supervisado: 15 rasgos, normalización y regresión logística multiclase, guardado JSON. El servidor carga `data/adaptive_model.json` si existe. | Requiere grabaciones etiquetadas y rasgos idénticos. Limita amplitudes a 56 en runtime; frecuencia temporal depende de versión. Sin clases calibradas, `classify` devuelve **`present_still`, 0.5**: fallback, no evidencia. | No hay artefacto compatible demostrado para nuestros RX/LTF/cadencia. No usar el fallback o entrenar con una sola clase quieta. |
| `ruview-unified/src/heads.rs`: `PresenceHead` | Regresión logística sobre embedding `z` de un encoder; constructor pesos/cero y bias/cero. Es un head entrenable, no un modelo de presencia ya aprendido. | `predict_prob` recién inicializado da 0.5. Requiere encoder, pesos del head, dimensiones y dataset compatibles. Los nombres ONNX de conteo/pose y un fixture de test encontrados en el árbol no acreditan esos pesos. | Bloqueado: no se comprobó existencia/carga de un bundle adecuado a nuestro contrato. |
| `wifi-densepose-calibration/src/specialist.rs`: `PresenceSpecialist` | **Modelo estadístico pequeño calibrado**, no red preentrenada: ajusta umbrales con anclas `Empty` y ocupada; `infer` lee únicamente `Features.mean` y `.variance`. | No pide frecuencia, fase, antenas sincronizadas o un embedding. Su `train` aprende parámetros de etiquetas; no equivale a heurística sin ajuste. `serde` serializa tipos; usar el crate entero arrastra core/signal, serde_json/sha2/uuid/thiserror y dependencias transitivas. | **Seleccionado como componente**. Falta adaptador auditado y calibración vacía/ocupada; no es integración lista para ejecutar. |

No se ejecutaron las CLI que abren sockets, HAP, firmware, enrolamiento interactivo o entrenamiento. Node v22.20.0 fijado ya existe para el puente; eso no sustituye el runtime/contrato Rust.

### Referencias primarias congeladas

- [PresenceSpecialist: parámetros, ajuste e inferencia](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/v2/crates/wifi-densepose-calibration/src/specialist.rs#L101).
- [Features y cálculo por serie](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/v2/crates/wifi-densepose-calibration/src/extract.rs#L103), [CLI room: scalar y defaults](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/v2/crates/wifi-densepose-cli/src/room.rs#L41).
- [Heurística signal](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/v2/crates/wifi-densepose-signal/src/motion.rs#L191), [heurística servidor](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/v2/crates/wifi-densepose-sensing-server/src/main.rs#L4193).
- [Watcher de score firmware](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/scripts/c6-presence-watcher.py#L1), [through-wall](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/scripts/through-wall-detector.js#L95).
- [FieldModel: gates de calibración](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/v2/crates/wifi-densepose-signal/src/ruvsense/field_model.rs#L30), [clasificador aprendido](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/v2/crates/wifi-densepose-sensing-server/src/adaptive_classifier.rs#L299), [head sobre embedding](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/v2/crates/ruview-unified/src/heads.rs#L20).
- [DSP de firmware](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/firmware/esp32-csi-node/main/edge_processing.c#L1068), [contrato/calibración DSP](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/firmware/esp32-csi-node/main/edge_processing.h#L65), [heurística WASM de zonas](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/v2/crates/wifi-densepose-wasm-edge/src/occupancy.rs#L44).
- [HVAC](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/v2/crates/wifi-densepose-wasm-edge/src/bld_hvac_presence.rs#L59), [consulta MCP](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/tools/ruview-mcp/src/tools/presence-now.ts#L15), [clasificador RSSI archivado](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/archive/v1/src/sensing/classifier.py#L45), [heurística MediaTek](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/v2/crates/wifi-densepose-sensing-server/src/mediatek_heuristic.rs#L209).

Los comentarios upstream sobre detección/validación no se trasladan como resultados de esta tesis; se contrastó el código efectivo. El inventario fija bytes/hash de estos archivos y de dependencias inspeccionadas.

## Por qué este componente y cómo se conectaría

Para anclas vacía E y ocupadas O, el código toma **la primera** ancla `Empty` y promedia las estadísticas de las anclas ocupadas (no promedia todas las vacías):

```text
si var_O > 1.05*var_E: umbral_var = (var_E + var_O)/2
si no: canal de varianza desactivado (+infinito)
si |media_O-media_E| > 1e-4: umbral_media = |media_O-media_E|/2
si no: canal de media desactivado
salida = (var_actual > umbral_var) OR
         (canal_media_activo y |media_actual-media_E| > umbral_media)
```

Son reglas/guardas del commit inspeccionado, **no umbrales elegidos con nuestra sesión**. La confianza es un margen normalizado/clamp, no una probabilidad de presencia calibrada. Si no hay `Empty` u ocupada, `train` retorna `None`. Si ambos canales quedan inertes, el head puede devolver `absent` con confianza cero: un adaptador debe informar falta de separabilidad, no validación de ausencia. No se ajusta ahora ningún número.

Contrato propuesto y fijado para revisar antes de implementar:

1. Fuente: canónico/CSV validados y referencias originales, exclusivamente filas plenamente incluidas en la ventana v3. **Una inferencia offline por ventana completa de 30 s**, no streaming/subventanas seleccionadas por score. Mantener resultados de adquisición y estado del detector separados.
2. Entrada primaria **RX-01 LLTF**, elegida por identidad, no por RSSI o una puntuación. RX-02 LLTF será réplica independiente, con su propia calibración; no promediar RX ni crear una antena coherente. HT-LTF permanece conservado como diagnóstico separado, sin mezclarlo con LLTF ni escoger después el bloque que mejor clasifique.
3. Por fila, `x_i = media(|CSI_i[k]|)` sobre el conjunto **fijo de 52 tonos activos LLTF** (datos+pilotos), usando índices/roles y máscara canónica. Nada de DC, guardas o pares inválidos. Si falta un tono requerido, marcar la fila/entrada no evaluable, sin cero inventado, desplazamiento o máscara variable optimizada por datos. Conservar siempre el bruto completo. El modelo LTF sigue condicionado a fuentes/metadatos, sin atestación del binario.
4. `mean` y `variance` poblacional se obtendrían de los `x_i` reales con peso igual por fila. Se preservan timestamps/duplicados y cobertura; no se interpola ni remuestrea a 15/20/100 Hz. No se usarán autocorrelación, Doppler, respiración, corazón, fase ni sus campos de relleno como mediciones. El adaptador debe definir explícitamente cómo construye el contenedor `Features` para invocar solo este head y marcar los demás campos como no utilizados, sin publicarlos como estimaciones.
5. Esto es una **adaptación del componente**, no compatibilidad directa con la CLI upstream: `frame_scalar` allí promedia todos los streams/tonos que recibe y no entiende nuestras máscaras/LTF laterales. Aunque el comentario de `extract.rs` menciona señal restada de baseline, la CLI `room.rs` realmente empuja `frame_scalar(frame)` de amplitud bruta; no se debe atribuirle una resta que no ejecuta.
6. Calibración futura propuesta: anclas `Empty` y `Sit` de sesiones de desarrollo previamente fijadas (propuesta B01-E/B01-S), mismo montaje/perfil/escala/máscara por RX. Si fallan, no seleccionar otra por mejor score; revisar el plan. No mapear caminar a `SmallMove` silenciosamente: W se conserva como estrato de evaluación de presencia/movimiento, no ancla ficticia de otro nombre. Varios `Empty` no se agregan por pasar el vector al método; cualquier política de agregación necesitaría definición propia.
7. La sesión quieta existente y los registros rechazados anteriores quedan como evidencia de transporte, no como calibración E/O ni aprobación para entrenar. La reserva por sesiones B05/B06 no participa en ajuste, normalización o elección de head. No hay un banco compatible entrenado/guardado por este trabajo.

La propuesta preserva la fórmula del head y la atribución MIT. Próxima implementación limitada posible: adaptador offline y pruebas de equivalencia con el Rust fijado. Una traducción a Python, si se decide por disponibilidad del runtime, sería un port explícito verificado, no «RuView Rust ejecutado». No se implementa aquí ninguno. El crate completo implica dependencias mayores que estas dos estadísticas; inspeccionar/aprobar su resolución antes de instalar o compilar, sin scripts remotos.

La vía completa de enrolamiento upstream añade `AnchorQualityGate` (≥60 frames) y duraciones por defecto de 20 s para E/S, además de otros especialistas y baseline/banco. El adaptador propuesto usaría las ventanas reales de 30 s y conservaría sus controles de calidad, no asumiría que llamar a `PresenceSpecialist::train` valida etiquetas, cobertura o calibración. `MixtureOfSpecialists` puede usar `unwrap_or(true)` cuando falta lectura de presencia para habilitar otros heads: ese fallback tampoco es presencia observada y no se propone usarlo.

## Compatibilidad temporal y límites con datos reales

Datos del [resumen reconstruido de originales](../results/CAPTURA_FISICA_V3.resumen.json): 150 filas incluidas por RX en 30 s; conteo/tiempo nominal = 5 filas/s. Tasas por span host: RX-01 ~4.998529 y RX-02 ~4.998609; diferencias interiores de 179.681–221.799 ms y 179.746–225.906 ms. No son una malla uniforme ni un reloj RF.

| Requisito | Compatibilidad y límite |
|---|---|
| Frecuencia | El head usa dos estadísticas de muestras y no exige `fs`; 5 filas/s no es bloqueo dimensional. La irregularidad/bursts sí puede sesgar medias por fila; se informa cobertura, sin prometer uniformidad. |
| CLI temporal | `enroll`/`room-watch` usan `fs_hz=15` por defecto; `room-watch` conserva 200 frames y comienza con ≥32, API usa ventana 256. A ~5/s, 200 implicarían ~40 s, mayor que nuestra ventana. No usar esos defaults ni rebautizar 150 filas como 200. |
| Rasgos periódicos | `Features::from_series` calcula autocorrelación con un `fs` uniforme y banda cardíaca hasta 3 Hz; no aprobar esa vía con ~5/s irregulares ni inventar frecuencia. El head elegido no los lee. |
| LTF/máscaras | 64 pares por bloque no equivalen a 128 tonos distintos ni dos antenas; seleccionar LLTF activo exige la proyección explícita anterior. No alimentar sin adaptación el frame de 128 pares concatenados a un detector que presume una sola rejilla. |
| Escala | Amplitud int8/autoescala no calibrada, merge/filtro de firmware y AGC pueden producir cambios de media que parezcan ocupación. Referencia por RX/montaje es necesaria y no garantiza separabilidad. Normalizar cada fila a media constante destruiría el canal de desplazamiento de media; no se introduce esa operación a posteriori. |
| Relojes | El head por RX no exige alinear los uint32 ni IDs entre placas. Una ventana host común no sincroniza RF. Replay rápido a un servidor que mide llegada con su reloj cambia tiempos y es otra adaptación, no reproducción fiel. |
| Datos/verdad terreno | Falta condición vacía comparable, etiquetas operativas y evaluación independiente. El global histórico sigue rechazado. No hay justificación para ajustar umbrales con la única condición quieta. |

## READY: revisión estática de aperturas sucesivas

Fuentes locales: [RX-01](../firmware/csi_recv/main/app_main.c), [RX-02](../firmware/csi_recv_02/main/app_main.c), [adaptador serial](../src/preserving_serial.py), [coordinador](../src/controlled_capture_v3.py) y [gate](../src/availability_window.py). Sus hashes se fijan en el inventario.

| Demostrado por código/archivo | Lo que no demuestra |
|---|---|
| RX-01 imprime READY una vez en `app_main`, línea 273, **antes** de `wifi_csi_init`; RX-02 una vez, línea 290, **después** de inicializar y verificar canal/ancho. | READY por sí solo no prueba CSI activo en RX-01, ni un reloj/época físicos comunes. |
| En estas fuentes no hay lector de comandos UART ni bucle que vuelva a imprimir READY ante una apertura/cierre del host. `csi_writer` continúa emitiendo CSI, no un nuevo READY periódico. | Cerrar/abrir el fd del host no implica ejecutar otra vez `app_main`. No existe aquí un handshake de solicitud READY. |
| Cada nuevo coordinador v3 arranca sin READY; exige observar uno estricto y tres filas posteriores, con D=A+10 s. | CSI válido de un receptor ya activo no autoriza fallback a «solo filas», ni reutilizar READY de otra sesión. |
| El host construye puerto cerrado, pide DTR/RTS false, abre por by-id, lee desde apertura y suprime el flush de entrada de pySerial. pySerial 3.5 POSIX actualiza DTR/RTS mediante ioctl al abrir y cierra fd al finalizar. | Pedir false no demuestra ausencia de transitorios del driver/puente/circuito de autoarranque. No se inspeccionó eléctricamente la placa ni el estado físico de líneas. No atribuirles automáticamente el arranque. |
| Los `sdkconfig.defaults` versionados fijan consola UART/115200. Los `sdkconfig` generados locales además habilitan consola secundaria USB Serial/JTAG; no se cambió ninguno. | Configuración de compilación local no atesta el binario instalado ni establece causalidad entre una señal USB y un reset. No se infiere un esquema de auto-reset desde el nombre ttyACM. |
| El intento v3 conservado contiene ROM y READY a ~0.59/~0.64 s desde A; v1/v2 tienen sus propios arranques conservados. La reconexión previa tiene hora y placas desconocidas. | Sesiones separadas con historial físico incompleto no son una prueba controlada de reapertura repetida sin reset/reconexión intermedios. No garantizan READY en 18 aperturas sucesivas. |
| El capturador conserva bytes devueltos; no envía una petición textual READY. | No garantiza que un READY anterior siga pendiente en kernel/USB ni conserva bytes que nunca devolvió una lectura. |

**Bloqueo estructural:** v3 exige un evento que el firmware solo emite al ejecutar `app_main`, sin mecanismo de solicitud/reemisión por apertura. Un RX que continúa activo puede no producirlo; el próximo intento podría terminar correctamente como timeout sin ventana. No se resuelve con un temporizador de salida del cuarto ni con el detector.

No se hacen aperturas de prueba, resets, reconexiones o cambios de firmware/protocolo aquí. Antes de una campaña repetida hay que decidir, en otra revisión autorizada, cómo acreditar disponibilidad repetible. Una sesión con conexión persistente y varias ventanas, un handshake/READY repetible o un criterio distinto serían **cambios versionados**, no propiedades actuales de v3. No se implementan ni se adoptan silenciosamente. Con v3 vigente: conservar timeout y suspender la campaña para revisión, sin reintentar hasta conseguir READY.

## Operación individual y propuesta concreta siguiente

El [piloto revisado](PLAN_CAMPAÑA_PRESENCIA_PILOTO.md) sustituye el requisito de otro operador por una única persona y el inventario actual. Ruta mínima propuesta: **laptop fuera del cuarto, RX dentro con los mismos cables si alcanzan**, inicio diferido y recibo de cierre consultable desde fuera. Para S/W, avisos de la propia laptop antes de A y después de cierre+10 s permitirían salir/volver sin introducir otra persona; su audibilidad no se supone demostrada. No se asumen teléfono, segundo PC, cámara, teclado extra ni enlace remoto.

Se preguntó si los cables actuales permiten esa colocación; no hay confirmación registrada en este cambio. Si no alcanzan o no puede confirmarse cierre sin entrar, **la operatividad exterior no está resuelta con el inventario confirmado**. No se simula su resolución con una demora fija. Los avisos/recibo y etiquetas deben probarse offline antes de una autorización física; no existe aún ese lanzador mínimo.

Orden propuesto de trabajo, sin nueva adquisición ahora:

1. Confirmar colocación exterior con los cables existentes y método visible/audible de cierre; documentar nuevo montaje fijo para las tres condiciones, sin mover RX durante un slot.
2. Revisar la disponibilidad READY repetible y escoger explícitamente una solución versionada. Mientras no se resuelva, no lanzar 18 slots v3 suponiendo que arrancarán.
3. Si se aprueba, implementar **solo** un trabajo de un slot con demora, registro de etiquetas/recibo y cero reintentos; probarlo en memoria/PTY, incluido fallo sin falso aviso de cierre. No un sistema amplio de automatización o inferencia en vivo.
4. Revisar criterios de calidad/cobertura y elegibilidad de datos; conservar rechazos previos. Obtener autorización física nueva únicamente después de cerrar esas decisiones.
5. Con nuevas sesiones E/S etiquetadas y elegibles, autorizar separadamente la calibración del head y su evaluación por sesiones. Hasta entonces, detector sin calibración válida y sin puntuaciones interpretables de presencia.

**No hay autorización física vigente, banco aprendido por este trabajo ni detector de presencia validado.** Las fuentes, brutos, informes y rechazos anteriores permanecen intactos; no se escogieron muestras o frecuencia para aparentar compatibilidad.

## Verificación realizada y reproducción de fuentes

Cambio documental y de metadatos: se contrastaron 31 fuentes upstream con Git/bytes/SHA-256, nueve fuentes locales, dos configuraciones generadas y la implementación POSIX de pySerial. Se compararon **380 archivos preservados** de fuentes, intentos, informes y visualizaciones con el inventario anterior al cambio. Se verificaron destinos de enlaces locales/permalinks y `git diff --check`. [Resultado de las comprobaciones](../results/SELECCION_DETECTOR_PRESENCIA.validacion.json). No se repitió la suite de adquisición, ni se llamó a `train`/`infer`, porque no se cambió código ejecutable. La inspección estática no es prueba sintética del detector ni validación física de presencia/READY.

Desde la raíz del repositorio, este comando contrasta el inventario contra otro checkout **local** del mismo commit, sin importar detectores o serial, instalar dependencias o abrir dispositivos:

```bash
python3 - /home/alan-monar/auditorias-externas/ruview-fefb0f918eef <<'PY'
import hashlib, json, subprocess, sys
from pathlib import Path
d = json.loads(Path('docs/DETECTOR_PRESENCIA_RUVIEW.fuentes.json').read_text())
u = Path(sys.argv[1])
def git(*args):
    return subprocess.check_output(['git', '-C', str(u), *args])
assert git('rev-parse', 'HEAD').decode().strip() == d['ruview_commit']
assert not git('status', '--porcelain')
for e in d['upstream_sources']:
    b = (u/e['path']).read_bytes()
    assert b == git('show', d['ruview_commit']+':'+e['path']), e['path']
    assert len(b) == e['bytes'], e['path']
    assert hashlib.sha256(b).hexdigest() == e['sha256'], e['path']
for e in d['local_sources']:
    b = Path(e['path']).read_bytes()
    assert len(b) == e['bytes'], e['path']
    assert hashlib.sha256(b).hexdigest() == e['sha256'], e['path']
print('31 fuentes upstream y 9 locales coinciden; no se ejecutó detector.')
PY
```

Las configuraciones generadas/venv y los originales son evidencia local, no se suben a Git. Su disponibilidad en otra máquina no se presupone; el JSON distingue sus hashes de las fuentes versionadas.
