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

## Diagnóstico offline posterior — sin otra captura

Se subió `cf36c30` a la misma rama. El ledger demuestra prefijos de 3/2 bytes en la primera lectura y colas de 129 bytes leídas como 1+127+1; la última lectura cruza el deadline y el host deja de leer con una línea pendiente antes de cerrar. No se observó su resto en el dispositivo físico ni se determinó el origen de los residuos iniciales. No se demuestra corrupción de las filas completas ni causalidad WiFi/firmware.

Se reprodujo la parada a mitad de línea en memoria/PTY y se ensayó un prototipo de finalización hasta LF acotada por tiempo y bytes, sin integrarlo ni cambiar el protocolo v1. Pasaron 142 pruebas (111 Python y 31 Node), sin omisiones. Se mantienen separados integridad del transporte registrado, calidad de filas completas y rechazo global. Los originales y firmware siguen intactos; no se abrió UART físico. Ver [evidencia, pruebas y recomendación antes de repetir](DIAGNOSTICO_LIMITES_CAPTURA.md). No repetir todavía v1: primero integrar/revisar una política versionada con auditoría de los tiempos reales y obtener autorización nueva.

## controlled_dual_v2 integrado — únicamente validación offline/PTY

Rama `feat/captura-dual-v2` desde `39c5cc3413ca5250320a5218f14dca2723bbb612`. v2 reutiliza el lector acotado con 250 ms y 65536 bytes adicionales, mantiene los 30 s comunes y guarda parada por RX y conteos separados de filas anteriores/dentro/posteriores. El coordinador junta lectores antes de cerrar, también ante aborto o error. Auditoría, canónico y visualización verifican la política sin limpiar fragmentos ni aprobar el arranque residual. v1, sus planes y resultados conservan su significado; el intento físico sigue rechazado.

Pasaron 155 pruebas (124 Python y 31 Node), cero omisiones; dos ensayos PTY persistidos (uno de 30 s nominales y otro sintético abreviado con residuos) y ocho vistas Firefox. Se verificaron 51 archivos previos intactos. No se abrió UART físico, flasheó, cambió firmware ni creó/consumió autorización nueva. El origen del arranque sigue indeterminado. Ver [protocolo y comando para revisión](PROTOCOLO_CAPTURA_DUAL_V2.md) y [evidencia real de las pruebas](../results/CONTROLLED_DUAL_V2.validacion.json).

## Único intento físico v2 autorizado — 25 de octubre de 2026

Con una autorización y declaración ambiental nuevas se ejecutó v2 una sola vez en un directorio nuevo, tras verificar ambas identidades USB. Se conservaron 147/147 filas, todas dentro de los 30 s nominales. Integridad registrada, calidad de filas completas y calidad de parada pasan; la sesión global sigue **rechazada** por residuos iniciales (RX-01: ROM pegada a 0x00; RX-02: dos fragmentos huérfanos). Ambas paradas fueron LF, con cero cola, cero filas tardías y cero bytes de finalización adicional. No se ejercitó la extensión de una línea pendiente en este hardware.

Ambos puertos quedaron cerrados. Auditoría independiente y cuatro vistas de visualización pasaron manteniendo el rechazo visible. Se verificaron 86 archivos anteriores/fuentes intactos y el resultado v1 idéntico; no se concatenaron sesiones ni se cambió su rechazo. Sin reintentos, recortes, flasheo ni cambios de firmware; autorización nueva consumida. Ver [resultado y comparación separados](../results/CAPTURA_FISICA_V2_20261025.md) y [evidencia resumida](../results/CAPTURA_FISICA_V2_20261025.validacion.json).

## Propuesta de ventana por disponibilidad — solo diseño para revisión

Se subió `cb504c4` y se inspeccionaron offline READY/filas/ledgers. RX-01 imprime READY antes de habilitar CSI; RX-02 después de inicializar y consultar configuración. Se propone exigir READY más tres filas válidas consecutivas por RX, frescura host de 1 s y máximo de espera de 10 s desde antes de la primera apertura. La ventana futura de 30 s se activaría una sola vez en el instante real de decisión, con reglas conservadoras de inclusión por primera/última lectura y resultados visibles separados de conexión completa y ventana. Esto no acredita sincronización RF ni estabilidad.

Ver [diseño y límites pendientes de revisión](DISENO_VENTANA_POR_DISPONIBILIDAD.md) e [inventario de señales existentes](../results/DISPONIBILIDAD_SENALES_OBSERVADAS.json). Sin implementación, nuevo plan/autorización, UART, adquisición, flasheo o entrenamiento. Los intentos, visualización y rechazos v1/v2 permanecen intactos; no se creó una ventana retrospectiva.
