# Inventario de la base verificable

Fecha: 24 de octubre de 2026. Inicio: rama main limpia en `72ccb0abc29912b05716d2f52710fd9d270a901b`, origin correcto y autenticación disponible. Trabajo en `feat/base-propia-verificable`; se conservan los archivos iniciales. No se altera la restauración.

## Selección y trazabilidad

Se inspeccionaron el árbol restaurado `/home/alan-monar/tesis-restaurada-20261024T043056Z/tesis-wifi-csi-mesh/` y la consolidación anterior. Se importan **17 copias verificadas**: 14 archivos firmware y 3 archivos Python (dos herramientas y sus 18 tests). Cada SHA-256 se volvió a comparar con la fuente seleccionada antes de registrar el hito. [PROCEDENCIA_BASE.json](PROCEDENCIA_BASE.json) contiene origen absoluto, fecha de modificación, hash y comparación con la primera restauración por archivo.

Se prefieren las variantes firmware de `consolidacion-tecnica-20261024/trabajo/tesis-wifi-csi-mesh/`: incluyen el CMake de componente TX reconstruido anteriormente y la retirada previa de inicialización de clave de ejemplo no utilizada. El parser, capturador dual y tests se copiaron literalmente del primer árbol restaurado. La retirada no se vuelve a aplicar ni se publica el valor anterior. Las fuentes adaptan ejemplos Espressif ESP-CSI, revisión histórica `8633d67152db2808f141cc1595970aa9cf406045`; se preservan SPDX y atribuciones Apache-2.0. No se reasigna licencia global al proyecto.

| Copia incorporada | SHA-256 | Selección |
|---|---|---|
| `firmware/csi_send/CMakeLists.txt` | `30f04f0d09072d609a05da6e2fac38a41960108dfcc0475a5734d980e4ae6a6a` | copia literal verificada |
| `firmware/csi_send/sdkconfig.defaults` | `0308464cb583c0d7ead14fd672653951d11986aa394ca4adad2374d8aeee9b11` | copia literal verificada |
| `firmware/csi_send/main/app_main.c` | `8e9d1a0cfd2996f0b6b3420f495fe2270e7f7ad0ca7487c3b876b6878c5c8eba` | variante consolidada compilada; retirada previa de inicialización de clave del ejemplo en difusión sin cifrar; original intacto |
| `firmware/csi_send/main/CMakeLists.txt` | `677ada172a1826884b5145497f5f2fba7972e6e8e9f19c91287f46c5b988cb7a` | CMake TX reconstruido previamente en consolidación; compilación previa salida 0; no se etiqueta original perdido |
| `firmware/csi_recv/CMakeLists.txt` | `f0ea95f6160e3d84eda8d4442050bb06fd96ecc1619ab81cd0327578450fb5f2` | copia literal verificada |
| `firmware/csi_recv/sdkconfig.defaults` | `0308464cb583c0d7ead14fd672653951d11986aa394ca4adad2374d8aeee9b11` | copia literal verificada |
| `firmware/csi_recv/main/app_main.c` | `c940779452aedad8862dd6eb7a24d51786c662d3acbb9369b1a86bff54a1ccc6` | variante consolidada compilada; retirada previa de inicialización de clave del ejemplo en difusión sin cifrar; original intacto |
| `firmware/csi_recv/main/CMakeLists.txt` | `47114157940dc826fa2b7f81beeb00d95b0249d410ea516565916871a4247846` | copia literal verificada |
| `firmware/csi_recv/main/idf_component.yml` | `4a1f01c43b2ebab54ee95377ca12412eb14993428f3587227c7c5862d11cf11b` | copia literal verificada |
| `firmware/csi_recv_02/CMakeLists.txt` | `3a9acc5679e8b82cc39516193278a4495d0d28ebf1c51c0d70e07991e3036d31` | copia literal verificada |
| `firmware/csi_recv_02/sdkconfig.defaults` | `3dfc815b2c3f2abfc9dbada469d5a546477a751a3c7bf7251e566ff421ec5897` | copia literal verificada |
| `firmware/csi_recv_02/main/app_main.c` | `1fb53776e1e5776194749041d1252c3f8ee11f69f30fb982a42c7577319e00d5` | variante consolidada compilada; retirada previa de inicialización de clave del ejemplo en difusión sin cifrar; original intacto |
| `firmware/csi_recv_02/main/CMakeLists.txt` | `47114157940dc826fa2b7f81beeb00d95b0249d410ea516565916871a4247846` | copia literal verificada |
| `firmware/csi_recv_02/main/idf_component.yml` | `4a1f01c43b2ebab54ee95377ca12412eb14993428f3587227c7c5862d11cf11b` | copia literal verificada |
| `src/capture_csi.py` | `f2e285971f9c6dd4802e7ed38b72dc44cb70a9ac061c5b68c7bb70b97c4287e8` | copia literal verificada |
| `src/capture_csi_multi.py` | `7a58b62258a8057fc8c7652ccad36b6f0c22895319c2f52d2d44a331ad4e6908` | copia literal verificada |
| `tests/test_capture_csi_multi.py` | `339ba29ca1dbdce8dec869872eaa9c3da87e9f120f7dbc2d7e7140960b4d433e` | copia literal verificada |

Código nuevo distinguido de lo recuperado: `src/validate_capture.py`, sus 20 pruebas sintéticas, las dos regresiones físicas offline, los procedimientos `tools/`, el perfil y la documentación. No se reconstruye lógica RF ni un adaptador RuView.

## Contrato CSI_DATA inspeccionado

Cada muestra tiene 26 campos originales, con `data` como lista JSON entrecomillada en CSV:

```
type,id,mac,rssi,rate,sig_mode,mcs,bandwidth,smoothing,not_sounding,aggregation,stbc,fec_coding,sgi,noise_floor,ampdu_cnt,channel,secondary_channel,local_timestamp,ant,sig_len,rx_state,len,first_word_invalid,queue_drops,data
```

El CSV añade delante `session_id,receiver_id,usb_serial,host_timestamp_utc,host_monotonic_ns`: 31 columnas. Se conservan representaciones originales. Perfil real: canal 11, HT20 (`bandwidth=0`), MAC TX `1a:00:00:00:00:00`, 256 escalares int8, `sig_mode=1`, `mcs=0`, `stbc=0`, `first_word_invalid=0` y `rx_state=0`. RX-01 USB `5C93199744`; RX-02 `5C93200689`; UART0 a 115200. El capturador descubre identidades serie; no se confía en la numeración ttyACM.

`len` son bytes de escalares, no número de subportadoras. `id` es contador local del callback receptor, no secuencia transmitida. `local_timestamp` es microsegundos uint32 con posible wrap y relojes independientes por RX; los relojes host marcan lectura serie y no llegada RF ni latencia de enlace. El firmware habilita LLTF/HTLTF/STBC-HTLTF2, merge y filtro de canal; aún falta verificar el empaquetado real por LTF, orden I/Q y subportadoras antes de convertir para RuView. No se ha aplicado conversión compleja.

## Referencia física y límites

Se inspeccionó `consolidacion-tecnica-20261024/pruebas_fisicas/dual-60s-20261024T205854Z/`, su informe, sesión, logs y CSV. Siete copias byte a byte se conservan localmente en `data/raw/dual-60s-20261024T205854Z/captura/`, ignoradas por Git. El manifiesto versionado fija tamaños y SHA-256; también se verificó el hash del informe original. No se publican capturas completas ni se ejecuta una sesión física nueva.

| Evidencia histórica | RX-01 | RX-02 |
|---|---|---|
| Filas válidas en 60 s | 292 | 291 |
| Tasa media por ventana solicitada | 4,867 Hz | 4,850 Hz |
| Líneas CSI malformadas | 1 inicial | 0 |
| Calidad estricta registrada | Rechazada | Aceptada |

La sesión terminó pero el capturador retornó 1. Los arranques y residuos permanecen en bruto. El validador separa integridad, resultado original y controles adicionales; no oculta reinicios ni colas sin terminar. No hay sincronización RF, etiquetas de presencia ni campaña completa demostradas. Los fixtures sintéticos usan puertos de memoria o PTY privados y nunca cuentan como evidencia experimental. Los saltos callback no permiten medir pérdida de paquetes TX por sí solos.

## Reproducción y exclusiones

[Resultados reales](../results/BASE_VERIFICADA.md): tres builds nuevos exitosos con ESP-IDF v5.4 y 40 pruebas aprobadas, sin omisiones. Las dos regresiones sobre datos físicos solo verifican offline la referencia y su rechazo esperado. No se asumen aprobadas las 304 pruebas históricas. `tools/test_base.sh` exige aislamiento Bubblewrap; si falta la copia de datos omite explícitamente dos regresiones. No abre UART física.

Se excluyen builds, entornos, sdkconfig generado, binarios, credenciales, scripts históricos de flasheo con rutas obsoletas, registros ajenos, adaptadores experimentales no aprobados y modelos sin pesos verificados. Las resoluciones generadas de componentes solo IDF quedan locales; los manifiestos fuente se versionan.

## Pendientes del sistema híbrido

1. Aprobar correspondencia compleja, LTF, geometría, subportadoras y relojes; diseñar el contrato del adaptador con las pérdidas de representación explícitas.
2. Revisar y fijar componentes y licencias de RuView; la revisión candidata documentada no se ha instalado.
3. Con autorización nueva, comprobar por USB el firmware realmente instalado y realizar captura física controlada, conservando arranques y todos los errores sin relajar calidad.
4. Definir campañas con etiquetas de ocupación/presencia, condiciones y partición por sesión; mantener los demás objetivos del anteproyecto para las etapas siguientes.
5. Seleccionar modelos solo tras comprobar pesos, dependencias, frecuencia y geometría. No hay modelo Edge AI validado en esta base.
