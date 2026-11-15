# Validación de interpretación y visualización offline

Tercer hito, 24 de octubre de 2026. Base exacta `73099b3347ff5403ca789c7c87d398ec7928b09b`, rama `feat/visualizacion-csi-offline`. La especificación completa está en [CONTRATO_CONSUMIDOR_RUVIEW.md](../docs/CONTRATO_CONSUMIDOR_RUVIEW.md); resumen estructurado y hashes en [visualizacion_offline.validacion.json](visualizacion_offline.validacion.json).

## Resultado

Se ejecutaron las funciones oficiales `parsePacket`, constructor/`add`/`result` de `SpectrumCollector` y transitivamente `iq8`/`binAmplitudes` del módulo `harness/ruview/src/devices/esp32.js`, RuView `fefb0f918eefa7db6daef8cc83787fc7d6f74187`. Se usaron exclusivamente buffers en memoria. No se ejecutó captureEsp32, kernel, detector de presencia ni funciones de entrenamiento.

Este módulo **sí interpreta ESP32 como Im/Re con signo y fase atan2(Im,Re)**. Se verificó por ejecución, no por analogía con los scripts JS anteriores. La lectura completa de 128 pares HT20 también es aceptada: dividir en vistas LTF es una decisión para conservar su significado e historiales, no una limitación de tamaño del parser. Las discrepancias de otros consumidores del segundo hito siguen documentadas.

## Datos reales analizados y visualizados

Única sesión de la visualización: `dual-60s-20261024T205854Z`. Se verificaron nuevamente los siete hashes del manifiesto y las correspondencias de cada fila con su bruto. Se copiaron completos e intactos al artefacto nuevo, incluidos arranques y la línea CSI malformada inicial de RX-01. Las referencias CSV/serial y SHA por línea permiten regresar desde cada vista al original.

| Vista | USB | Filas originales | Posiciones por vista | Amplitudes cotejadas | Fases no desconocidas cotejadas |
|---|---|---:|---:|---:|---:|
| RX-01 / LLTF | 5C93199744 | 292 | 64 | 18.688 | 15.172 |
| RX-01 / HT-LTF | 5C93199744 | 292 | 64 | 18.688 | 16.348 |
| RX-02 / LLTF | 5C93200689 | 291 | 64 | 18.624 | 15.132 |
| RX-02 / HT-LTF | 5C93200689 | 291 | 64 | 18.624 | 16.296 |

Total: **583 filas independientes del CSV**, 74.624 posiciones complejas cotejadas entre canónico y parsePacket y 62.948 fases no desconocidas, tolerancia absoluta 1e-10. Las dos LTF no duplican mediciones independientes, receptores ni antenas. Los 11.676 pares cero conservan fase desconocida en el canónico; upstream devuelve 0 numérico y no se usa ese valor como fase medida. No hubo first_word_invalid=1 en estas filas; su tratamiento se ejercitó con fixtures sintéticos separados.

El modelo documentado exige HT, 20 MHz, sin secundario ni STBC, LLTF/HT-LTF habilitados; no se deduce por longitud. Se conservan 64 posiciones por bloque, índice, DC/guardas/pilotos, configuración de merge/filtro y sus límites de evidencia. No se deshace el filtro, no se calibra AGC, no se eligen artificialmente 56 tonos ni se fija geometría de un modelo.

Los archivos de 15 s y las 596 filas incompletas del segundo hito **no se concatenaron ni se incluyen en esta visualización**. Tampoco se visualizaron las 296 filas de replay como evidencia física ni los fragmentos sin procedencia como campañas adicionales.

## Calidad y tiempo preservados

La interfaz y los JSON mantienen literalmente **“captura histórica con validación estricta rechazada”**, `strict_quality_ok=false` y el error original de RX-01. Las regresiones aprobadas comprueban ese rechazo esperado: no aprueban la campaña. No se elimina ni maquilla el arranque. RX-02 conserva su aceptación individual del capturador; no cambia el rechazo global.

Los gráficos usan tiempos host registrados y muestran UTC/monotónico/local RX originales por fila. No hay remuestreo, interpolación, ticks animados ni sincronización RF inventada. Los enteros ns se conservan como strings; para el colector oficial se resta BigInt antes de convertir un delta pequeño a ms. La tasa oficial por span host es 4,93 Hz para RX-01 y 4,90 Hz para RX-02, diferente de la media por ventana solicitada 4,867/4,850 Hz. Ninguna mide por sí sola tasa RF, pérdidas TX o latencia.

Cada RX/LTF tiene un SpectrumCollector separado, bins=64 y capacidad igual al número original de filas. Se conservaron todas sus filas. Sus redondeos a 0,1, ausencia de tiempos por fila, máscaras y fase en el resultado se explican en el contrato. El canónico conserva las amplitudes exactas, fase, máscaras, procedencia y metadatos, y es la fuente de los gráficos con validez; el espectro no enmascarado upstream no queda habilitado para inferencia.

## Pruebas ejecutadas

Comando: `./tools/test_offline.sh results/local/visualizacion-csi-entrega/canonical.json`.

| Conjunto | Ejecutadas | Fallos/errores | Omitidas | Tipo de evidencia |
|---|---:|---:|---:|---|
| Python unittest | 72 | 0 | 0 | 69 sintéticas, 3 regresiones físicas offline heredadas |
| Node test nativo | 31 | 0 | 0 | 26 sintéticas, 5 regresiones físicas offline nuevas |
| Total | **103** | **0** | **0** | 95 sintéticas y 8 regresiones históricas, ninguna adquisición nueva |

Python incluye las 60 del hito anterior y 12 nuevas para conservar 31 campos, bytes/offsets/base64/SHA, bloques y máscaras, ceros, nanosegundos anidados, timestamps compartidos, integridad y rechazo de perfil inconsistente. Node ejecuta el módulo oficial con pruebas de fase, signo, cabecera, byteOffset, dimensiones, arrays opcionales/múltiples, flags, truncamiento, redondeo/binning/ring buffer, relojes irregulares, separación LTF y wrapper. Las cinco regresiones físicas ejercitan las cuatro vistas y la preservación del rechazo/arranque. Las pruebas sintéticas no cuentan como mediciones CSI experimentales.

Los runtimes corrieron con red separada, fuentes de solo lectura y /dev privado. El módulo no crea sockets en este flujo; cualquier intento dgram.createSocket en las CLI/pruebas propias falla. No se enviaron paquetes CSI por UDP ni se abrió UART. No se ejecutaron las 304 pruebas históricas ni el conjunto completo de RuView.

## Validación visual real

La página HTML local se verificó en Firefox headless **154.0**, ya disponible; no se instaló un navegador. Se probaron las cuatro combinaciones RX/LTF y el slider contra la fila CSV 2, con estado `rendered=true`, identidad correcta, límites 291/290, cuatro gráficos no vacíos y etiqueta de rechazo visible. La σ tiene 52/56 puntos utilizables por LLTF/HT-LTF; guardas/DC excluidas no aparecen como ceros de variabilidad inventados. Se inspeccionaron screenshots de RX-01/LLTF y RX-02/HT-LTF.

La invocación simple de --screenshot se bloqueó en el entorno gráfico aislado. Se resolvió usando Marionette dentro del mismo aislamiento externo, control TCP solo en **127.0.0.1**, sin servidor HTTP ni envío CSI/UDP. Para esa instancia efímera se deshabilitó el sandbox interno de contenido/GPU mediante su perfil propio; Bubblewrap mantuvo red aislada, fuentes de solo lectura y /dev privado. No se cambió el perfil del navegador del usuario. Los mensajes de servicios Firefox sin red y de cierre no invalidaron las aserciones DOM/screenshots, que completaron con código 0.

El control de navegador no usa un reloj de pantalla como datos: navega, inspecciona DOM y selecciona una fila existente. Los PNG y el informe de cuatro vistas están bajo `results/local/visualizacion-csi-entrega/browser-qa/`; se fijan hashes en el resumen versionado. No se añaden a Git capturas completas, perfiles ni screenshots.

## Artefacto y reproducción

Página lista para abrir localmente:

`results/local/visualizacion-csi-entrega/index.html`

Incluye RSSI, amplitud por fila, σ temporal descriptiva e historial por RX/LTF; máscaras, DC/guardas y relojes se conservan. `canonical.json`, `ruview-consumer.json`, `validation.json` y `originals/` están junto a la página. No se inicia un servidor; no hay peticiones externas y CSP prohíbe conexiones.

Para repetir sin sobrescribir: preparar el runtime fijado si falta, ejecutar `.venv/bin/python -B tools/build_offline_bundle.py --output results/local/OTRO-NOMBRE`, probar con `tools/test_offline.sh` y abrir ese index.html. El constructor comprueba hashes del runtime/módulo antes de su ejecución y rechaza directorios existentes. Sin la evidencia local las regresiones se omiten explícitamente o el exportador falla; no se inventan ni descargan capturas.

Para repetir la comprobación de navegador, con un artefacto nuevo y Firefox ya instalado, usar `tools/check_offline_browser.py` dentro de `bwrap --unshare-all --die-with-parent --ro-bind / / --dev /dev --tmpfs /dev/shm --proc /proc --tmpfs /tmp`, añadir `--bind RUTA_BUNDLE RUTA_BUNDLE --setenv HOME /tmp` y ejecutar `.venv/bin/python -B tools/check_offline_browser.py RUTA_BUNDLE`. La salida browser-qa debe ser nueva. El servidor de control efímero solo escucha localhost dentro de esa red privada; nunca se usa --remote-allow-hosts ni bind público.

## Estado real y siguientes límites

Funciona la cadena diagnóstica **original verificado → canónico reversible y enmascarado → parsePacket oficial en memoria → cuatro SpectrumCollector independientes → visualización local comprobada**. Las muestras preservan su trazabilidad y el consumidor concreto ya tiene un contrato Im/Re demostrado.

Continúan bloqueados la aprobación experimental de esta sesión, el streaming integrado/UDP, la calibración y fase RF estable, sincronización entre placas, atestación del binario histórico, comparación con otras configuraciones y cualquier presencia/Edge AI. Falta una campaña autorizada y estrictamente válida, con etiquetas y condiciones verificables antes de evaluar precisión o modelos. No se modificó ESP-IDF, firmware, placas, originales ni el alcance del anteproyecto.
