# Contrato del consumidor RuView y representación canónica offline

Tercer hito, 24 de octubre de 2026. Rama `feat/visualizacion-csi-offline` basada exactamente en `73099b3347ff5403ca789c7c87d398ec7928b09b`. Se conservan ESP-IDF v5.4, firmware propio y objetivos del anteproyecto. Esta entrega es diagnóstica offline: no habilita presencia, entrenamiento ni conclusiones de precisión.

## Consumidor concreto y dependencias

Se ejecuta [harness/ruview/src/devices/esp32.js](https://github.com/ruvnet/RuView/blob/fefb0f918eefa7db6daef8cc83787fc7d6f74187/harness/ruview/src/devices/esp32.js) del commit `fefb0f918eefa7db6daef8cc83787fc7d6f74187`, **distinto de los scripts JavaScript del segundo hito**. Copia byte a byte en `vendor/ruview/esp32.js`; SHA-256 `21b8c74d9b0a47f52538b5d902faa32ac6f4c58dab94d6612d7fbc89237d8f80`. Licencia MIT y atribución conservadas. `vendor/ruview/PROVENANCE.json` fija fuente, commit, hash, requisito Node y runtime. El `package.json` mínimo local solo declara ESM/privado; no ejecuta los scripts ni instala el paquete upstream.

El único import del módulo es `node:dgram`, incorporado en Node. En la importación se inicializa una tabla CRC; no se abre socket. Se invocan `parsePacket`, constructor/`add`/`result` de `SpectrumCollector`, y transitivamente `iq8`/`binAmplitudes`. No se invocan `captureEsp32`, `FrameCollector`, `runAnalysis`, kernel ni funciones de presencia. En las CLI/pruebas propias `dgram.createSocket` está reemplazado por una función que falla si se intenta usar; además se aísla la red y /dev mediante Bubblewrap.

El paquete oficial declara Node >=20. Se preparó **Node v22.20.0 Linux x64** únicamente en `.tools/node-v22.20.0/bin/node`, fuera del SDK/Python ESP-IDF. Se descargó el archivo oficial [node-v22.20.0-linux-x64.tar.xz](https://nodejs.org/dist/v22.20.0/node-v22.20.0-linux-x64.tar.xz) y se comparó su SHA-256 fijado `00bbd05e306ea68b6e13e17360d0e2f680b493ef95f2fea1c4296ff7437530bc` con [SHASUMS256.txt oficial](https://nodejs.org/dist/v22.20.0/SHASUMS256.txt) servido por HTTPS y con los bytes descargados. No se afirma verificación GPG. El script local revisable `tools/prepare_node.py` lee solo dos entradas regulares permitidas del TAR: binario y LICENSE, sin extraer rutas arbitrarias, enlaces, npm ni instaladores. No se instala todo RuView ni dependencias npm; no se modifica PATH global ni ESP-IDF. El constructor de artefactos comprueba hash del binario y del módulo antes de ejecutarlos.

## Contrato ejecutado de parsePacket

Entrada: `Buffer` con cabecera ADR-018 efectiva de 20 bytes y payload int8. `{iq:true}` solicita amplitudes/fases; sin esa opción no hay arrays. **En este módulo el orden ESP32 es Im/Re y la fase es correcta**, a diferencia de los parsers R3/R4/R5 del informe anterior. `iq8(...,true,...)` lee Im primero, Re después; calcula `sqrt(Re²+Im²)` y `atan2(Im,Re)`. Se ejecutaron cuatro cuadrantes, extremos -128/127, buffers con byteOffset no cero, dimensiones vacías/múltiples, truncamiento y error de magic. El vector sintético [-4,3] da 5 y -0,927295218 rad; la permuta con amplitud idéntica se detecta por fase.

| Cabecera | Contrato efectivo ejecutado | Vista propia y límite |
|---|---|---|
| @0 u32 LE | magic 0xC5110001 | Solo buffers en memoria; ningún datagrama |
| @4 u8 | nodeId | RX-01→1 y RX-02→2, tabla explícita local, no identidad USB implícita |
| @5 u8 | Cantidad de antenas | 1 por vista de un RX; ant original=0 sigue siendo índice en el envoltorio |
| @6 u16 LE | Cantidad de pares por antena | 64 por LTF documentado; el parser también acepta 128 pares completos y no exige dividirlos |
| @8 u32 LE | Frecuencia MHz | Canal primario 11→2462 MHz, conservando canal original aparte |
| @12 u32 LE | Secuencia | Copia del callback local RX, declarada como tal; nunca secuencia TX ni pérdida RF |
| @16/@17 int8 | RSSI/noiseFloor con signo | Metadatos del paquete originales, sin normalización ni SNR calibrado |
| @18 u8 | PPDU | 0 categoría HT/legacy; sig_mode=1 completo permanece aparte |
| @19 flags | bw40 bit0, firstWordZeroed bit5 | HT20 bit0=0. Bit5 no significa máscara: el parser no invalida pares por él. No se afirma haber zeroed ni sincronizado datos |
| @20 int8[] | Im/Re | Copia literal del segmento LTF, sin permutar, escalar, rellenar ni eliminar guardas/DC |

En una antena el parser devuelve arrays completos; con múltiples antenas no devuelve arrays de fase/amplitud completos y `firstChain` es una ruta separada de amplitud. No se usa esa ruta. Rechaza dimensiones cero y truncamiento, pero acepta bytes sobrantes y no valida el perfil PHY completo, máscaras ni procedencia: esas garantías provienen del validador propio. Para el par cero upstream devuelve fase numérica 0; el envoltorio conserva fase desconocida `null`/`phase_known=false`. Un flag firstWordZeroed por sí solo tampoco evita que upstream calcule amplitud sobre bytes inválidos: probado con un buffer sintético.

## Vistas LTF: elección semántica, no geometría forzada

Se conserva el modelo condicionado del [segundo hito](COMPATIBILIDAD_CSI_RUVIEW.md): ESP32-S3, HT20, sin secundario, sin STBC y LLTF+HT-LTF habilitados; 256 bytes por fila y dos bloques de 128 bytes. No se deducen bloques solo por longitud. Orden por bloque `0..31,-32..-1`, según documentación ESP-IDF v5.4. Fuentes verificadas usan merge/filtro activos y autoescala; el binario histórico no está atestado por hash ni se revierten mezcla/filtrado/AGC.

Se eligen dos vistas **del mismo registro original**: LLTF [0,128) y HT-LTF [128,256). Cada una contiene 64 posiciones nominales, incluidas DC/guardas, sin seleccionar artificialmente 56 tonos ni representar bloques como antenas. Los cuatro historiales se denominan RX-01/LLTF, RX-01/HT-LTF, RX-02/LLTF y RX-02/HT-LTF. Son dos receptores y 583 filas originales, no cuatro receptores ni 1.166 mediciones independientes.

Cada historial tiene su propia instancia `SpectrumCollector`; las dos LTF de un RX mantienen **el mismo nodeId**, con el contexto LTF fuera del colector. Su clave interna solo incluye fuente/node/shape y no distingue LTF: usar una sola instancia mezclaría historiales 1x64. La prueba sintética con LLTF de amplitud 5 y HT-LTF de amplitud 13 verifica que no se mezclan.

`SpectrumCollector` agrupa por posiciones adyacentes y redondea amplitudes a 0,1; no conoce índices físicos. Aquí se configura bins=64 para 64 posiciones y capacidad igual a las 292/291 filas, conservando todas las filas. Su constructor directo permite esa capacidad; no se ejecuta la CLI captureEsp32 ni su límite de captura. Se probaron también pérdida por binning, ring buffer, separación de historiales y timestamps repetidos/irregulares. Solo se valida lo ejercitado: no se transforma su resultado en evidencia de presencia.

## Representación canónica y pérdidas del consumidor

`src/canonical_csi.py` genera `tesis-canonical-csi-v1`. Antes de interpretar exige integridad del manifiesto y coincidencia CSV/bruto; permite diagnóstico de calidad rechazada **sin cambiar el resultado de calidad**. `canonical.json`, `ruview-consumer.json`, los siete originales copiados y la página se guardan exclusivamente en un directorio local nuevo.

| Elemento | Preservado en el envoltorio propio | Límite del consumidor oficial |
|---|---|---|
| Bruto | Copias exactas de los siete archivos, tamaños/SHA-256; cada muestra apunta a línea/offset/longitud y SHA de línea con bytes completos en base64 | El Buffer LTF solo contiene muestras aceptadas, no mensajes de arranque ni línea malformada |
| Fila CSV | Los 31 campos originales como texto, número de línea y registro, hash del CSV | No retiene la fila original ni todos sus campos |
| Identidad/sesión | RX, USB, run global, session_id original y tabla nodeId | nodeId numérico no basta para identidad física o sesión |
| Relojes | UTC original, host_monotonic_ns y local_timestamp uint32; nanosegundos como strings decimales también en el JSON de sesión anidado | No hay timestamps de adquisición en ADR-018; SpectrumCollector no devuelve tiempos por fila |
| Complejos | Re+jIm, arrays real/imag, amplitud sin redondeo y fase en radianes | parsePacket conserva fase en su resultado; SpectrumCollector conserva solo amplitud redondeada |
| Invalidez | hardware_valid, cfr_usable, phase_known, fase/amplitud null donde corresponda; primeros 4 bytes inválidos→2 pares globales sin desplazar índices | No hay máscara por par; no se interpreta flag bit5 como una máscara automática |
| Ceros | Amplitud cero válida cuando procede, fase desconocida null | atan2(0,0)=0 numérico no es fase medida |
| LTF/roles | Nombre, rango byte, índice nominal y roles data/pilot/DC/guard por bloque | Solo conoce cuenta de pares; no fronteras ni etiquetas LTF |
| Configuración/evidencia | Perfil original, hash de perfil serializado con claves ordenadas, SHA de fuentes firmware, IDF y límite de asociación histórica | No conserva merge/filtro/autoescala ni prueba el firmware instalado |
| Calidad | Resultado estricto original, auditoría completa y etiqueta visible | Parsear bytes o reunir espectros no aprueba una campaña |

Las máscaras tienen significados diferentes: una guarda/DC puede ser hardware_valid=true, pero cfr_usable=false. La fase matemática de un par no cero no certifica fase RF calibrada. La representación conserva todo el original y nunca convierte inválidos en cero. El buffer al consumidor conserva bytes incluso para la prueba sintética de invalidez; la UI usa máscaras propias para no presentar esos valores como mediciones utilizables. Los resultados no enmascarados de upstream no quedan habilitados para análisis físico o entrenamiento.

## Tiempo, visualización y variabilidad

`SpectrumCollector.add(pkt,t)` recibe milisegundos relativos derivados del reloj host **registrado**: primero se resta con BigInt y después se convierte la diferencia a número. Los ns originales permanecen como strings; no se usan Date.now, performance.now ni ticks de pantalla como muestras. `rateHz` usa el span observado (N-1)/Δt y es diagnóstico de lecturas host; no es tasa RF ni la media de la ventana solicitada. Timestamps compartidos se conservan como tales. No se sincronizan los relojes independientes de RX ni se emparejan paquetes por callback igual.

`src/offline_view.mjs` dibuja RSSI, espectro de la fila elegida, σ poblacional de amplitud por posición y un historial por RX/LTF. RSSI/historial colocan un punto/marca por fila en su tiempo host registrado. No hay interpolación, resampling, reproducción con reloj de pantalla ni animación. El slider elige un índice de **fila real** y mantiene estado por vista; sus eventos no crean datos. El historial usa una marca de tamaño fijo por muestra, no un intervalo temporal rellenado. Dos puntos con el mismo tiempo pueden superponerse; siguen siendo dos filas en el envoltorio.

La σ se calcula sobre valores utilizables observados con peso igual por fila, sin suponer muestreo uniforme, rellenar faltantes ni atribuir significado causal a movimientos. DC y guardas quedan sombreadas, inválidos señalados y valores desconocidos sin punto numérico inventado. El orden de bytes se conserva en el envoltorio; el gráfico coloca puntos por índice nominal para mostrar -32..31, sin alterar arrays fuente. La interfaz muestra permanentemente **“captura histórica con validación estricta rechazada”** y explica que no hay presencia, entrenamiento ni precisión demostrados.

## Procedimiento reproducible

1. Con `.venv` del primer hito y `requirements-dev.txt` preparados, ejecutar `python3 tools/prepare_node.py` **solo si falta el runtime**. Si existe, el script lo preserva y sale sin sobrescribir. El build verifica después su hash. No activar ni modificar ESP-IDF para este flujo.
2. Crear un artefacto nuevo: `.venv/bin/python -B tools/build_offline_bundle.py --output results/local/diagnostico-NUEVO`. Requiere las siete copias locales fijadas por el manifiesto; nunca las descarga ni fabrica. Rechaza destinos existentes y todo destino fuera de results/local. Ejecuta Python y Node con fuentes de solo lectura, salida nueva escribible, red aislada y /dev privado.
3. Ejecutar `./tools/test_offline.sh results/local/diagnostico-NUEVO/canonical.json`. Incluye pruebas Python y JavaScript. Sin brutos locales se omiten las tres regresiones Python; sin CSI_CANONICAL_PATH se omiten cinco JS. Revisar siempre los recuentos, no asumir aprobación.
4. Abrir `results/local/diagnostico-NUEVO/index.html` como archivo local en el navegador. No hace peticiones externas ni necesita servidor; CSP prohíbe conexiones. Opciones iniciales: `?rx=RX-02&ltf=HT-LTF`. No se inicia un servidor de visualización.
5. Opcional: `tools/check_offline_browser.py BUNDLE` usa un Firefox ya disponible y Marionette **solo TCP 127.0.0.1** para comprobar las cuatro vistas/slider y producir screenshots. Debe ejecutarse en la red privada descrita en el informe; no instala Firefox ni usa un servidor HTTP/UDP. Crea browser-qa nuevo y preserva salidas anteriores.

Los artefactos con capturas completas, perfiles del navegador y screenshots quedan ignorados en results/local; Git contiene código, licencias, hashes y resultados resumidos, no el conjunto físico completo. Para compartir el conjunto íntegro sigue haciendo falta una decisión específica.

## Qué queda respaldado y qué sigue bloqueado

Respaldado por ejecución: **datos propios íntegros → representación canónica con máscaras/procedencia → vistas LTF documentadas → parsePacket Im/Re y SpectrumCollector independientes → visualización diagnóstica local**. El consumidor concreto resuelve el bloqueo de fase de esta ruta offline; no corrige ni valida automáticamente los otros parsers del segundo hito.

Siguen bloqueados: adquisición integrada en vivo/UDP, campaña estrictamente aceptada, atestación del binario histórico, calibración/escala y fase RF estable, sincronización entre RX, comparabilidad con configuraciones sin filtro y cualquier modelo de presencia/Edge AI. No se han abierto UART, flasheado placas, modificado firmware/originales ni entrenado modelos.
