# Consolidación del único intento físico controlled_dual_v3

**Se conserva el rechazo de `connection_full` y del resultado global. `experimental_window` permanece conforme según v3.** Esto no es detección de presencia, sincronización RF, aprobación para entrenar ni validación estadística. La consolidación actual es exclusivamente offline; no se abrió UART ni se adquirieron datos nuevos.

## Fuentes originales y reproducibilidad

La evidencia es el directorio local `results/local/preparacion-dual-v3-20261026T000758Z/`, su adquisición `captura-dual-v3-20261026T000758Z-intento-unico/`, control `control/ejecucion-autorizada-v3-intento01/` y análisis `analisis-v3-intento-unico/`. No se usan cifras del chat: el [reproductor](../tools/consolidar_fisica_v3.py) reconstruye desde brutos, CSV, ledgers, traza y sesión y contrasta los informes guardados.

[Resumen JSON completo y versionado](CAPTURA_FISICA_V3.resumen.json), SHA-256 `8caf7e31625218a98210bcf9b4bcf6bed2a292970bdea271f7925c684e9dd24e`. Incluye referencias/bytes/SHA-256 de fuentes y artefactos, extremos por fila, las **149 diferencias interiores por RX**, bordes, exclusiones y evidencia problemática. Los brutos y `results/local` no se distribuyen en Git; sin los originales locales la reproducción falla explícitamente, no descarga ni fabrica datos.

Código de adquisición `513be6037308015605b9a3ab41b2e70badd901ef`: los 14 hashes de procedencia coinciden tanto con sus blobs Git como con las fuentes actuales. Se comprobó pySerial 3.5 y el hash del backend POSIX. Fuente/perfil ESP32-S3 e IDF v5.4 conservados; binario instalado no atestado. RuView se limita al consumidor offline fijado a `fefb0f918eefa7db6daef8cc83787fc7d6f74187`, licencia MIT conservada, con módulo y Node v22.20.0 por hash. No se entrenó ni ejecutó inferencia de presencia.

Verificación sobre archivos disponibles:

- Los diez originales de adquisición (siete archivos de captura, dos ledgers y traza) y las 17 entradas del bundle coinciden en tamaño/hash.
- Las 18 entradas **ajenas al propio manifiesto** del control coinciden; la anomalía de autoentrada se detalla abajo, sin ocultarla.
- Trece referencias históricas del resumen local a bundle, autorización, plan, auditoría, visualización y capturas de pantalla coinciden. También coinciden las diez copias originales exportadas.
- Auditoría nueva idéntica a las cuatro guardadas: capturador, independiente original, análisis y auditoría dentro del canónico. No se buscaron intervalos alternativos.
- Plan autorizado y copias byte a byte iguales; una sola invocación física registrada y autorización `CONSUMED`. No existe autorización vigente para otra captura.

### Anomalía del manifiesto auxiliar de control

`control-manifest.json` declara «no self hash», pero incluye una entrada de sí mismo con tamaño **0** y SHA-256 de archivo vacío (`e3b0c442…b855`). El archivo real tiene **3158 bytes**, SHA-256 `48949b535dbfe52a15c7100b93ff974aeef26009d88a304e5ec159e8d8f7d0ee`. **La validación literal de ese manifiesto auxiliar no pasa.** Las otras 18 entradas sí pasan y el manifiesto se preservó intacto.

No se modifica el original para hacerlo pasar. La anomalía no es un desacuerdo entre bruto/CSV/ledgers ni invalida por sí sola su auditoría de transporte; pertenece a la capa auxiliar de archivo. Este resumen versionado fija el hash real del manifiesto. No se afirma que todos los manifiestos sean válidos ni se cambia por ello ningún estado histórico de calidad. Tampoco existen firmas/atestación que prueben por sí solas una cronología física completa.

## Ambiente declarado y momento del intento

Plan original: solo el operador en su cuarto, sentado y quieto frente a laptop, un RX a cada lado; TX-01 a algo más de 2 m con cargador USB de pared y ambos RX por USB a laptop. Es declaración humana, no medición del ambiente. Se declararon desconexiones/reconexiones previas, sin placas concretas ni hora exacta; no se infieren esas identidades ni una época de arranque/READY.

Sesión UTC `2026-10-26T00:54:53.241030+00:00` a `2026-10-26T00:55:24.550780+00:00`; America/Guayaquil: 2026-10-25T19:54:53.241030-05:00 a 2026-10-25T19:55:24.550780-05:00. Envolvente completa registrada: **31.309703431 s**. Es distinta de los 30 s experimentales.

Las identidades registradas en preflight fueron RX-01 `5C93199744` → ttyACM0 y RX-02 `5C93200689` → ttyACM1, by-id, VID/PID 1a86:55d3, UID 1000/dialout y R/W. Son snapshots del intento, no una consulta a dispositivos actuales.

## Activación única y tiempos exactos

| Evento host | Nanosegundos monotónicos |
|---|---:|
| A, antes de la primera apertura | 21060399243703 |
| D, límite de disponibilidad | 21070399243703 |
| T0, decisión real única | 21061663479670 |
| T1, deadline experimental | 21091663479670 |

D−A = 10 s; T1−T0 = **30 s exactos**. Tiempo hasta disponibilidad/disparo común: **1.264235967 s**. Se verificó un único evento `armed`, sin timeout, fatal o conflicto de activación. T0 no se retrocedió a una fila.

| Evidencia de disponibilidad | RX-01 | RX-02 |
|---|---:|---:|
| READY después de A (s) | 0.590254230 | 0.638800619 |
| Callbacks citados para el disparo | 1,2,3 | 0,1,2 |
| Edad de última fila al decidir (ms) | 7.984848 | 2.056444 |

READY estricto, tres filas consecutivas por RX y frescura ≤1 s son parámetros operativos. No atestan sincronización RF, firmware instalado o estabilidad.

## Filas completas, inclusiones y exclusiones

| Métrica / estado | RX-01 | RX-02 |
|---|---:|---:|
| Filas completas CSI | 154 | 153 |
| Filas incluidas | 150 | 150 |
| Filas excluidas | 4 | 3 |
| Motivo de exclusión | preámbulo antes de T0 | preámbulo antes de T0 |
| Callbacks completos | 0..153 | 0..152 |
| Bytes brutos | 137718 | 135560 |
| Lecturas no vacías | 2251 | 2229 |
| Cola final | 0 bytes | 0 bytes |
| Calidad de filas completas | Conforme | Conforme |
| connection_full | Rechazada | Rechazada |
| experimental_window | Conforme | Conforme |

La regla conservadora de inclusión sigue siendo `inicio_primera_lectura >= T0` y `retorno_LF < T1`. RX-01 excluye callbacks 0..3 (CSV líneas 2..5; bruto líneas 93..96); RX-02 excluye 0..2 (CSV líneas 2..4; bruto 94..96). Los siete son `preamble`, completados antes de T0. Cruces de inicio, cruces de ambas fronteras, filas en/después de T1 y fragmentos finales: cero. No se borró ninguna fila excluida.

### Primera y última fila incluida

Líneas CSV/bruto son 1-based; offsets y límites de byte están en el JSON junto a sus hashes. Los tiempos son observaciones de lectura host y pueden ser compartidos por varias filas de un chunk, no recepción RF.

| RX / extremo | Callback | Línea CSV / bruto | Inicio primera lectura ns | Retorno LF ns | UTC original LF |
|---|---:|---:|---:|---:|---|
| RX-01 primera | 4 | 6 / 97 | 21061757354333 | 21061854311933 | 2026-10-26T00:54:54.698061+00:00 |
| RX-01 última | 153 | 155 / 246 | 21091549358678 | 21091663082596 | 2026-10-26T00:55:24.506833+00:00 |
| RX-02 primera | 3 | 5 / 97 | 21061762795378 | 21061849858429 | 2026-10-26T00:54:54.693609+00:00 |
| RX-02 última | 152 | 154 / 246 | 21091544970122 | 21091658151448 | 2026-10-26T00:55:24.501902+00:00 |

## Cobertura real observada

Huecos calculados con retornos LF host de las filas incluidas: borde inicial `primera−T0`, 149 diferencias consecutivas y borde final `T1−última`. La suma de interiores y ambos bordes es 30 000 000 000 ns en cada RX. El JSON conserva **todas** las diferencias, no solo el máximo.

| Métrica (ms salvo conteo) | RX-01 | RX-02 |
|---|---:|---:|
| Borde inicial | 190.832263 | 186.378759 |
| Borde final | 0.397074 | 5.328222 |
| Huecos interiores, número | 149 | 149 |
| Interior mínimo | 179.680743 | 179.746091 |
| Interior máximo | 221.798754 | 225.906040 |
| Máximo observado, incluidos bordes | 221.798754 | 225.906040 |

`max_gap_ns=null` se conserva: v3 no fija un umbral máximo de silencio host. Su mínimo de una fila incluida por RX y esta cobertura registrada no equivalen a observación continua de RF, tasa RF uniforme, presencia inferida ni suficiencia para un modelo. La regla heredada de reloj local (delta uint32 1..10 000 000 µs), callbacks y descartes sigue separada; no se relajó. Ningún criterio futuro del plan piloto se aplica para reaprobar esta sesión.

## Continuidad, descartes, errores, parada y cierre

En ambos RX: cero filas CSI malformadas, fuente/metadatos inesperados, huecos o reinicios de callback, discontinuidades de reloj, incrementos de descartes y disminuciones del contador. `queue_drops` inicial/final = 0/0 en cada uno; `capture_error=null`. Esto no mide pérdidas de paquetes RF ni latencia de ida.

Los problemas de formato de la conexión son distintos de la calidad de filas completas: **21 líneas por RX**, todas con evidencia anterior a T0. Una línea inicial no UTF-8 contiene 95/92 bytes antes de `ESP-ROM:` (línea completa de 121/118 bytes), de origen físico indeterminado. Las otras 20 son mensajes legibles `boot.esp32s3`/`wifi:` no reconocidos por la gramática fijada (tag con punto o sin espacio tras `:`). No se consideran prueba de corrupción WiFi/firmware ni se amplía retrospectivamente esa gramática. Los brutos, offsets, tiempos y hashes de esas líneas se conservan.

| Parada/cierre | RX-01 | RX-02 |
|---|---:|---:|
| Motivo | lf_boundary | lf_boundary |
| Calidad de parada | Conforme | Conforme |
| Bytes adicionales / cola | 0 / 0 | 0 / 0 |
| Parada después de T1 (ms) | 0.696039 | 0.547640 |
| Último retorno LF ns | 21091663082596 | 21091658151448 |
| Puerto cerrado ns | 21091706760444 | 21091669233085 |

La finalización máxima 250 ms/65536 bytes por RX se mantuvo; no había línea pendiente, por lo que **la rama de lectura adicional no fue ejercitada físicamente**. No se le atribuye una mejora que no intervino. Lectores reunidos antes de ambos cierres; postflight de identidad correcto. Se conserva fuser posterior rc 1 y salidas vacías como metadato de usuarios visibles, sin garantía global de exclusividad.

## Resultados preservados y límites

Integridad registrada, calidad de filas completas, disponibilidad, cobertura mínima y parada pasan la auditoría v3. La conexión y el global siguen rechazados por la evidencia de arranque; la ventana conforme no borra ese rechazo. Capturador retornó 1 por calidad global, sin fallo UART/proceso. El manifiesto auxiliar tiene además la anomalía de archivo ya expuesta; no se confunde su literalidad con integridad de bruto/CSV/ledger.

La visualización original conserva los dos estados y tiene cuatro vistas Firefox guardadas/verificadas. Se comprobaron sus hashes y resultados; no se regeneró ni se volvió a ejecutar el navegador por un cambio documental. [Visualización local](local/preparacion-dual-v3-20261026T000758Z/analisis-v3-intento-unico/visualization/index.html).

Es una sola sesión con condición quieta declarada, distancia aproximada y binario no atestado. No hay condición vacía/caminando comparativa, sincronización RF ni evaluación de presencia. No se entrena, clasifica actividad, genera mapa espacial o implementa procesamiento en tiempo real. v1/v2 y sus rechazos permanecen intactos, sin ventanas v3 retrospectivas.

## Reproducir y verificar offline

Requisitos: originales locales en sus rutas, historia Git con el commit de adquisición, `.venv` con pySerial 3.5 y runtime oficial fijado ya disponible. No se descargan archivos.

```sh
./tools/offline_sandbox.sh .venv/bin/python -B tools/consolidar_fisica_v3.py \
  --check results/CAPTURA_FISICA_V3.resumen.json
./tools/offline_sandbox.sh .venv/bin/python -B -m unittest discover \
  -s tests -p 'test_consolidar_fisica_v3.py' -v
```

El sandbox deja originales de solo lectura, red aislada y `/dev` privado. Para reconstruir un archivo nuevo en el workspace autorizado: `.venv/bin/python -B tools/consolidar_fisica_v3.py --output-new RUTA_NUEVA.json`; se rehúsa sobrescribir. El código de salida 0 del consolidador significa **reproducción consistente y anomalía expuesta**, no aprobación del intento global rechazado.

Se aprobaron cuatro verificaciones específicas: reconstrucción y ausencia de UART/modificación de inputs; rechazo de otro hash auxiliar alterado (la excepción propia no lo oculta); rechazo de tamaño de bundle alterado; y rechazo de resumen publicado con T0 modificado. No se repite la suite completa de adquisición ni se adquiere otro registro. Los logs de comprobación y la comparación de preservación quedan en `results/local/consolidacion-fisica-v3-20261026/`.

La comparación final conserva **375 archivos originales/de código fijados sin cambios**, y verifica enlaces del informe, extremos y suma de huecos, las seis permutaciones del piloto y sus seis slots reservados. Verificaciones específicas: 4 aprobadas, 0 fallos y 0 omisiones. Hashes de evidencia local:

- `comprobacion-resumen-final.log`: `14a529bc675d0b083c9549631fa22804e4a0e8310cffd0a73242ccc9e959dba5`.
- `verificaciones-consolidacion-final.log`: `8b06ecd1e98ae67c138f8622f59cf45a1e673341c81c8fb1489da781cbdfc4e9`.
- `preservacion-antes.json`: `80000924fc5c04a78addc24ce576cdeca492bf861f9716e71d6c067cee17a262`.

Continuación propuesta: revisar [plan piloto y decisiones pendientes](../docs/PLAN_CAMPAÑA_PRESENCIA_PILOTO.md). **No hay autorización vigente para capturar, ni adquisición programada por este informe.**
