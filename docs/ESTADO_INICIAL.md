# Estado del repositorio — primer hito verificable

Actualizado el 24 de octubre de 2026. Esta actualización sustituye el estado inicial que describía únicamente carpetas; se conserva su historia en Git.

## Comprobado en esta base

Se incorporaron 17 copias con procedencia y SHA-256: firmware TX-01/RX-01/RX-02, parser CSI, capturador dual y pruebas recuperadas. Se añadieron un validador offline, perfil, manifiesto físico, pruebas y procedimientos reproducibles. Ver [INVENTARIO_BASE.md](INVENTARIO_BASE.md) y [PROCEDENCIA_BASE.json](PROCEDENCIA_BASE.json).

Los tres firmware compilan para ESP32-S3 con ESP-IDF v5.4, commit `67c1de1eebe095d554d281952fde63c16ee2dca0`. Se ejecutaron **40 pruebas, sin fallos, errores ni omisiones** (18 recuperadas, 20 nuevas sintéticas, 2 regresiones offline físicas). Las 304 históricas no se ejecutaron en esta base. Los resultados y límites están en [BASE_VERIFICADA.md](../results/BASE_VERIFICADA.md).

## Evidencia física histórica revisada

La captura dual de 60 s tiene 292/291 filas válidas, identidades USB históricas, MAC TX y canal 11 consistentes; sus siete archivos coinciden por SHA-256 con los originales. RX-01 conserva una línea inicial malformada; el resultado estricto global sigue rechazado y la CLI offline retorna 1. Las pruebas comprueban ese rechazo esperado. Las copias brutas quedan locales e ignoradas; se versiona el manifiesto.

No se realizó ninguna adquisición física, flasheo ni modificación de placas en este hito. Compilar no verifica el binario instalado. No se modificaron fuentes ni capturas originales y no se instalaron herramientas globales.

## Integración y pendientes

Se conserva el alcance del anteproyecto para MIPYMES de Riobamba y procesamiento local en PC; presencia es el primer hito, no el alcance total. No hay adaptador RuView aprobado ni modelo Edge AI con pesos verificados en esta base.

RuView fue inspeccionado anteriormente en `fefb0f918eefa7db6daef8cc83787fc7d6f74187`; sigue siendo revisión candidata, no dependencia instalada. Falta validar I/Q, empaquetado LTF, subportadoras, relojes y compatibilidad de modelos antes de transformar CSI. Después se requieren campañas físicas autorizadas, etiquetadas y con control de calidad, y evaluación separada por sesión.

El repositorio privado origin sigue siendo https://github.com/Alan-m-04/tesis-wifi-csi-hibrido . El hito se prepara en rama `feat/base-propia-verificable`; se conservan los objetivos y el flujo Git existentes.

## Segundo hito: auditoría CSI/RuView

Desde la base 74d612a se auditó RuView fijado a fefb0f918eefa7db6daef8cc83787fc7d6f74187 en checkout separado y ESP-IDF v5.4 instalado. Se demuestra Im/Re en fuentes propias y se documentan discrepancias de fase, banda, índices y parsers que bloquean ADR-018 directo. No se modificó firmware ni el capturador.

Ahora hay 60 pruebas aprobadas (57 sintéticas, 3 regresiones offline físicas), sin omisiones; los 40 resultados anteriores quedan como snapshot del primer hito. Se mantienen 292/291 filas y rechazo estricto global. Node/Rust no se ejecutaron, y no se instalaron dependencias RuView. Ver [COMPATIBILIDAD_CSI_RUVIEW.md](COMPATIBILIDAD_CSI_RUVIEW.md) y [AUDITORIA_CSI_RUVIEW.md](../results/AUDITORIA_CSI_RUVIEW.md).

## Tercer hito: canónico y visualización offline

Desde 73099b3 se ejecutó el consumidor oficial específico `harness/ruview/src/devices/esp32.js` (RuView fefb0f9), con Node v22.20.0 aislado y fijado por SHA. Su parsePacket Im/Re conserva la fase; SpectrumCollector se usa por separado para cada RX/LTF. No se instalaron npm ni dependencias RuView, y ESP-IDF sigue intacto.

Se generó una página local con 292/291 filas reales y sus dos LTF, procedencia reversible, máscaras y relojes originales. Se conserva el rechazo estricto histórico. Pasaron 103 pruebas (72 Python, 31 Node), cero omisiones, y las cuatro vistas/slider se verificaron en Firefox headless. Solo el control efímero del navegador escuchó TCP 127.0.0.1 en una red privada; ningún servidor HTTP, UART ni UDP CSI.

Ver [CONTRATO_CONSUMIDOR_RUVIEW.md](CONTRATO_CONSUMIDOR_RUVIEW.md) y [VALIDACION_VISUALIZACION_OFFLINE.md](../results/VALIDACION_VISUALIZACION_OFFLINE.md). Siguen pendientes streaming físico, campaña estrictamente aceptada, calibración, sincronización y modelos. El alcance del anteproyecto se mantiene.

## Cuarto hito: captura preparada, no ejecutada

Base 56ea270, rama feat/preparacion-captura-dual. Se diagnosticaron offline bytes CSI/ROM pegados en RX-01 y residuos de RX-02; reset observado no equivale a causa eléctrica demostrada. Se corrigieron defectos comprobables de host: flush implícito pySerial 3.5, conteo de tail excesivo y join/cierre durante startup. No se modificaron firmware ni originales.

Se prepararon coordinador de 30 s comunes con preámbulo conservado, ledgers, manifests, condición ambiental obligatoria y análisis/visualización posteriores en carpeta nueva. No se aprueba ventana estable separada. Pasaron 124 pruebas sin omisiones (93 Python y 31 Node); solo PTY/memoria y archivos históricos, ningún UART físico ni preflight udev real.

La captura permanece pendiente de condición ambiental e instrucción explícita para abrir RX-01 y RX-02. Ver [PROTOCOLO_CAPTURA_DUAL.md](PROTOCOLO_CAPTURA_DUAL.md) y [PREPARACION_CAPTURA_DUAL.md](../results/PREPARACION_CAPTURA_DUAL.md). No se flasheó ni se entrenó.

## Actualización física posterior al reinicio — 25 de octubre de 2026

La preparación anterior se conserva como estado histórico. Tras una autorización nueva y confirmación ambiental explícita, se ejecutó un único intento dual de 30 s comunes con identidades USB verificadas antes de abrir. RX-01 (5C93199744) correspondía a ttyACM1 y RX-02 (5C93200689) a ttyACM0. Ambos puertos se cerraron; no hubo reintentos ni cambios de firmware.

Se obtuvieron 145/146 filas completas. La integridad bruto/CSV/ledgers pasó, pero la sesión completa fue **rechazada**: ambos brutos conservan texto ROM pegado a residuos iniciales y una cola incompleta de 129 bytes. No se recortó ni reparó. La visualización offline nueva conserva ese rechazo y pasó las cuatro vistas en Firefox. Se verificaron 15 archivos del bundle y 40 archivos previos/fuentes sin cambios. No se repitieron las 124 pruebas de preparación; no se entrenó ni validó presencia.

Ver [resultado físico, límites y rutas locales](../results/CAPTURA_DUAL_POST_REINICIO.md) y [evidencia resumida con hashes](../results/captura_dual_post_reinicio.validacion.json). El intento anterior fallido por permisos y los originales permanecen intactos. Otro intento físico requiere nueva autorización.
