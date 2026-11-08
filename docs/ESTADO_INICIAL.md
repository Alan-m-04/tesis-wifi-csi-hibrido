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

## controlled_dual_v3 implementado y ensayado offline

Rama `feat/ventana-disponibilidad` basada exactamente en `a3f10ea2bed354cebd1b3354f1fb30a69a646a2e`, con autorización de implementación y pruebas offline. Se precisó antes de implementar que caída de flujo significa fin prematuro/fallo de lector antes de T1; los huecos de cobertura no tienen umbral máximo de silencio. READY/tres filas/frescura 1 s/espera 10 s/ventana 30 s son parámetros operativos, no estabilidad ni aptitud para modelos.

v3 conserva registro completo, evento de decisión atómico, auditoría de lotes/tiempos/procesamiento tardío, índices de inclusión y finalización acotada v2. Cada estado aparece en la interfaz; un resultado conforme no aprueba el otro. Se prueban memoria/PTY, errores/reset en el mismo chunk, concurrencia, eventos tardíos, timeout, fronteras, aborto y cierre. Evidencia y resultados reales en [informe v3](../results/VENTANA_DISPONIBILIDAD_V3.md) y [protocolo/comando preparado](PROTOCOLO_VENTANA_DISPONIBILIDAD_V3.md). No se abrió UART físico, adquirieron mediciones, flasheó, cambió firmware ni entrenó. No se creó ni consumió autorización física; v1/v2 y sus rechazos permanecen intactos.

## Consolidación offline del único intento físico v3 existente

La adquisición posterior autorizada desde `513be60` queda documentada en [CAPTURA_FISICA_V3](../results/CAPTURA_FISICA_V3.md) y su [resumen reproducible](../results/CAPTURA_FISICA_V3.resumen.json), calculados de los originales. Se mantienen 154/153 filas completas y 150/150 incluidas: integridad registrada, filas y parada conformes, ventana conforme, conexión y global rechazados. La auditoría nueva coincide con las cuatro copias guardadas. La autoentrada de tamaño cero del manifiesto auxiliar de control se expone como inconsistencia de archivo, sin corregirla ni confundirla con los 17 archivos de adquisición verificados.

Se añade un consolidador exclusivamente offline y cuatro verificaciones de reproducción/alteraciones en memoria/preservación, con red y dispositivos físicos aislados. No se repite la suite de adquisición ni se ejecuta otra captura. El [plan piloto de presencia](PLAN_CAMPAÑA_PRESENCIA_PILOTO.md) deja pendientes revisión de montaje/recorrido, etiquetado exterior, 18 slots y particiones completas, cobertura prospectiva y nueva autorización. No se aplican esos candidatos a v3 ni a v1/v2. Sin cambios de firmware, modelos, captura en vivo o mapas CSI; ninguna autorización física vigente.

## Selección estática de presencia y operación individual — desde f6829e1

Se inspeccionaron 31 archivos del checkout limpio de RuView `fefb0f918eefa7db6daef8cc83787fc7d6f74187`, contrastados con sus blobs Git y sin cambiar dependencia/licencia raíz MIT. La [decisión y comparación de requisitos](DETECTOR_PRESENCIA_RUVIEW.md) distingue parsers de scores de firmware, heurísticas, modelos calibrados y heads sin pesos compatibles acreditados. Se selecciona `PresenceSpecialist` como componente para un futuro adaptador offline: media/varianza de amplitud LLTF en RX-01, RX-02 independiente, sin fase/sincronización o frecuencia inventada. No se compiló/ejecutó detector, ajustaron umbrales, entrenó ni generó puntuaciones sobre la sesión quieta. Faltan adaptador/runtime, anclas vacía/ocupada elegibles y evaluación.

El [piloto](PLAN_CAMPAÑA_PRESENCIA_PILOTO.md) ya no presupone otro operador/equipo. Propone laptop exterior con cables actuales si alcanzan, demora de un slot, aviso C0 antes de abrir y recibo de ambos cierres+10 s para C1; las etiquetas son declaraciones humanas, no observación instrumental de transiciones. Geometría exterior y avisos sin confirmar. READY se imprime una vez en `app_main`; no hay solicitud/reemisión por apertura en estas fuentes. Los arranques históricos no demuestran repetibilidad sin eventos físicos intermedios. Esta limitación bloquea asumir 18 aperturas operativas: mantener timeout y suspender si falta, sin resets/reconexiones o cambios de criterio.

La verificación de este cambio es de hashes, blobs, enlaces y preservación, documentada en la selección; no se repiten pruebas de adquisición sin cambios de código. Fuentes, capturas, visualizaciones y rechazos v1/v2/v3 siguen intactos, con brutos y `results/local` fuera de Git. Sin UART, capturas, firmware o entrenamiento nuevos; ninguna autorización física vigente.

## Movimiento libre físico existente y comparación descriptiva offline

Se consolida el [intento exploratorio de movimiento libre](../results/CAPTURA_MOVIMIENTO_LIBRE_V3.md), adquirido posteriormente desde `cef86ef`: 152 completas/149 incluidas por RX, ambos puertos cerrados, integridad/filas/parada conformes, ventana conforme y conexión/global rechazados por arranque conservado. La autorización se consumió una vez, sin reintentos. El usuario declaró iniciar actividades después de enviarla; no se conoce la transición física exacta ni se asume movimiento continuo. La sesión queda fuera del piloto, calibración y entrenamiento.

La [comparación sentada/libre](../results/COMPARACION_FISICA_V3.md) reconstruye los canónicos/auditorías desde originales verificados y conserva ambos T0/T1 y rechazos. Las 14 fuentes/perfil de adquisición y runtime serial son iguales, con commits generales distintos; montaje fijo solo declarado, binarios instalados no atestados, entorno intermedio sin control y cambio de `noise_floor` observado en RX-02. Se describen RSSI, amplitud y σ temporal con 52/56 tonos activos, máscaras y cobertura por sesión/RX/LTF, sin normalizar ganancias ni rellenar intervalos. Cinco figuras SVG/PNG usan escalas comunes. No se atribuyen diferencias al movimiento o se calcula precisión.

Diez pruebas específicas aprobadas, sin omisiones, más reproducción y preservación de 507 archivos anteriores. Código exclusivamente offline con Bubblewrap y runtime de gráficos aislado/fijado; no se modifican capturador, firmware, criterios o resultados históricos. Brutos/canónicos y `results/local` continúan fuera de Git. No se abre UART, adquieren datos o entrenan modelos durante esta consolidación/comparación. Ninguna autorización física vigente.

## Adaptador de presencia offline — desde 796d534

Rama `feat/adaptador-presencia-offline` creada exactamente desde `796d534a9d04bb040f9868f77030980529ec02e7`. [Implementación/pruebas y límites](../results/VALIDACION_ADAPTADOR_PRESENCIA.md): port Python explícito del head `PresenceSpecialist` del RuView fijado, extracción de media LLTF52 por fila y media/varianza poblacional por RX/sesión. Se mantienen estados de adquisición y cobertura separados; datos requeridos incompletos dejan toda la entrada de ese RX no evaluable, sin rellenar o seleccionar otro intervalo.

22 pruebas aprobadas sin omisiones, más 2022/2022 vectores sintéticos idénticos bit a bit frente a los cuerpos Rust originales compilados/ejecutados con scaffolding mínimo; no el workspace Cargo ni `Features::from_series`. Rust 1.85.1 y std musl se prepararon como binarios oficiales fijados en `.tools`, sin instalación global, scripts remotos o cambios de IDF/RuView. Las envolturas sintéticas se abstienen sin anclas/separabilidad y no permiten trasladar sus modelos a datos físicos.

En las dos sesiones físicas solo se extrajeron 598 medias por fila, con trazabilidad y cuatro pares de media/varianza; estado **sin calibración**, decisión/confianza nulas. No se ajustaron umbrales/anclas ni se clasificó presencia con ellas. Conexión/global rechazados y ventanas conformes conservados; inicio físico del movimiento libre desconocido. Se verifican 598 archivos anteriores intactos, con brutos y artefactos locales fuera de Git. Sin UART, nueva captura, reset, firmware o protocolo modificado. No hay calibración física válida, detector real validado ni autorización de captura vigente.

Reanudación del 27 de octubre: se conserva el código guardado y se cierran documentación y verificación previa a publicar la rama. Pasaron otra vez 22 pruebas, se reprodujo exactamente el informe de rasgos bajo bloqueos de UART/calibración/inferencia y se confirmaron 2022 salidas sintéticas ejecutando el binario Rust existente. Bubblewrap no puede crear namespaces en el entorno actual: unittest se ejecutó directamente en el entorno restringido, sin atribuirle ese aislamiento. [Cierre y pendientes](../results/VALIDACION_ADAPTADOR_PRESENCIA.md#reanudación-y-cierre-documental--27-de-octubre-de-2026): faltan anclas físicas elegibles, banco por RX y evaluación independiente; el piloto conserva sus bloqueos. No se abrió UART ni se cambió firmware.

## Adquisición persistente v4 preparada offline — desde 51246df

Se define antes del código el [contrato v4](PROTOCOLO_PRESENCIA_PERSISTENTE_V4.md), sin cambiar v1/v2/v3: una conexión por RX, READY inicial, vigilancia continua de disponibilidad y ventanas independientes de 30 s con gate nuevo por slot. Memoria y PTY propios verifican bytes íntegros, fronteras, continuidad/reset/silencio, interrupción, etiquetas inciertas y cierre real de recursos. El [plan nuevo](PLAN_REVISION_CAMPAÑA_PERSISTENTE_V4.md) mantiene laptop y RX dentro, demora de salida, avisos distintos y particiones por conexión completa; sustituye solo la propuesta futura de operación, no evidencia histórica.

El transporte físico sigue deshabilitado. READY inicial, montaje, reproducción/audibilidad real y promoción a UART sin flush requieren revisión/comprobación posterior y autorización nueva. Se conservan las calidades de conexión, ventana, cobertura y etiqueta separadas; ni estas pruebas ni el detector offline calibran o validan presencia física. Ver [resultados reales, preservación y límite de Bubblewrap](../results/PRESENCIA_PERSISTENTE_V4.md). No hubo UART, adquisición física, cambios de firmware, calibración o entrenamiento.

## Backend UART v4 — desde 414b461, sin ejecución física

Se implementa en rama nueva el [transporte UART explícito](BACKEND_UART_PRESENCIA_V4.md): verificadores by-id/udev/permisos, pySerial fijado por hash, preservación de entrada, lector durante segunda apertura, journal/auditor y límites de almacenamiento/cierre. La apertura física necesita otro plan completo, referencia de autorización nueva y opción explícita; preparación/preflight no abren. READY y sus 10 s siguen obligatorios, una apertura por RX y sin reintentos automáticos. Protocolos históricos y firmware intactos.

Se inspeccionaron DTR/RTS/HUPCL efectivos de pySerial 3.5 y se ensayaron en PTY/dobles; solicitudes/getters no garantizan niveles eléctricos ni ausencia de transitorios/resets. [163 pruebas y bundles sintéticos auditados](../results/BACKEND_UART_V4.md), sin UART o campaña real ni calibración. [Práctica de sonidos sin ESP](PRACTICA_SONIDOS_V4.md) preparada; reproducción/audibilidad humana pendientes. Bubblewrap sigue fallando explícitamente sin namespaces y no se atribuye aislamiento a los tests directos.

## Diagnóstico offline del primer intento v4 — 28 de octubre de 2026 UTC

El usuario ejecutó posteriormente un único intento autorizado desde su terminal. Se conserva `post_ready_info:RX-02`, cero slots, cero filas CSI y recibo de ambos puertos cerrados. [Diagnóstico, bytes/tiempos y propuesta sin activar](../results/DIAGNOSTICO_V4_POST_READY.md): la línea inmediatamente posterior a READY es `I (545) main_task: Returned from app_main()`, compatible con el retorno normal de inicialización en ESP-IDF v5.4. Los marcadores de arranque anteriores no permiten atribuir causa eléctrica. Los residuos iniciales y la cola de RX-01 siguen rechazados.

Auditoría original reproducida; 176 pruebas offline aprobadas, incluidas 13 sobre una excepción estrecha aplicada solo a una copia temporal. Backend/auditor, firmware y protocolos históricos intactos. Se preservan 48 archivos originales, ambas prácticas y el intento consumido. PRUEBA02 es declaración humana de cuatro patrones distinguibles; PRUEBA01 permanece incierta, sin verificación automática. Bubblewrap falla explícitamente; los tests directos no acreditan su aislamiento. No se abrió UART en este diagnóstico. Otra adquisición requiere revisión y autorización nueva; no hay slots físicos v4 ni calibración válidos.

## Corrección versionada del retorno de app_main — 1 de noviembre de 2026

Al retomar se encontró el diagnóstico completo y un parche probado solo en copia,
todavía sin commit. Se registró ese trabajo y se integró una
[política optativa](POLITICA_LINEAS_V4_APP_MAIN_RETURN_V1.md), sin cambiar las
plantillas ni los protocolos históricos. La revisión `v4-app-main-return-1`
admite exclusivamente el retorno exacto inmediato al primer READY, antes de CSI
y de disponibilidad, dentro del plazo inicial y sin suspensión/cierre previos.
Plan, procedencia y auditor concuerdan; ausencia de revisión conserva la regla
histórica. Los bundles originales siguen reproduciendo sus eventos y rechazo.

[Verificación y límites](../results/CORRECCION_V4_POST_READY.md): 188 pruebas
offline aprobadas, cero omisiones, con 25 de política/replay y un adaptador
serial sobre PTY propios. Se verifican 2335 archivos previos intactos, incluidos
datos, firmware, protocolos y autorización consumida. Bubblewrap continúa sin
poder crear namespaces; no se atribuye su aislamiento a las pruebas directas.
No hubo UART, captura, reset, reconexión, cambio de firmware o calibración.
Antes de otro plan físico deben revisarse los motivos iniciales de formato y
los límites distintos de RX-01/RX-02; faltan READY/flujo de ambos, ventanas
físicas elegibles y autorización nueva. No se preparó otro intento.

## Revisión offline de formatos y orden de arranque — desde 6af037b

La [revisión de doce brutos y fuentes ESP-IDF v5.4](../results/REVISION_ARRANQUE_V4.md)
confirma cinco arranques completos de RX-01 con READY → `ic_enable_sniffer` →
retorno, a diferencia de RX-02. El v4 no contiene READY completo de RX-01.
Las tareas independientes permiten cabecera/CSI antes del retorno; se ensaya
esa posibilidad como reconstrucción sintética, sin atribuirla a otra captura.

La [revisión optativa `v4-startup-sequence-1`](POLITICA_LINEAS_V4_STARTUP_SEQUENCE_V1.md)
reconoce solo sniffer/retorno exactos, una vez y con orden por RX, dentro del
plazo original. Añade ambos retornos al gate inicial y mantiene tres filas
frescas, perfil y continuidad estrictos. No cambia las políticas históricas
ni plantillas; los bundles anteriores conservan su selección y replay.

210 pruebas aprobadas, incluidas 22 nuevas y dos ventanas completas sobre PTY,
sin omisiones; 2355 archivos anteriores intactos. El fallo de Bubblewrap sigue
explícito. **Bloqueo específico antes de preparar un nuevo plan E/S:** faltan
un tratamiento verificable del preámbulo completo y su contrato de elegibilidad.
Los prefijos no UTF-8 pegados a ROM y otros formatos iniciales registrados
mantienen el rechazo de conexión; no se aceptan o recortan para aprobar.
No se preparó otro intento ni hubo UART, resets, reconexiones, firmware o
calibración; los datos, rechazos y autorizaciones anteriores siguen intactos.

## Elegibilidad exploratoria v4 — desde 1f974b0

El [contrato nuevo, definido antes del código](ELEGIBILIDAD_EXPLORATORIA_V4_R1.md),
selecciona explícitamente `v4-exploratory-1` junto al arranque revisado. Mantiene
rechazada la conexión con preámbulo anómalo/no interpretado y conserva bytes,
hashes, offsets y tiempos. La elegibilidad exploratoria es un resultado separado
del auditor; las candidatas del reductor no son aprobación. No autoriza calibrar,
entrenar o usar en producción ni cambia el perfil CSI o las políticas anteriores.

La disponibilidad exige ambos retornos y tres filas frescas por RX de lecturas
nuevas fuera de los chunks de arranque. T0 sella fronteras de bytes/lecturas;
la cobertura exploratoria usa solo evidencia posterior y los mínimos anteriores.
Anomalías que alcancen una ventana o no puedan excluirse la impiden. Cualquier
suspensión posterior revoca candidatas sin rearmado. Identidad, almacenamiento,
integridad/replay, cobertura, etiqueta y ambos cierres se verifican antes de certificar.

[Resultados y límites](../results/ELEGIBILIDAD_EXPLORATORIA_V4.md): 234 pruebas
offline aprobadas, cero omisiones, dos ventanas sintéticas exploratorias elegibles
con conexión rechazada y 2370 archivos anteriores intactos. El v4 original conserva
su rechazo bajo su propia política. Bubblewrap sigue fallando explícitamente.
Se preparó un [plan nuevo vacío/sentado para revisión](PLAN_PILOTO_EXPLORATORIO_V4_ES_R1.md),
con ambas revisiones explícitas y declaraciones ambientales pendientes; ejecución
física requiere autorización nueva. No hubo UART, captura física, firmware,
calibración o entrenamiento.

## Diagnóstico offline del intento EXP02 consumido — 3 de noviembre de 2026

El usuario ejecutó un único intento autorizado desde su terminal normal con la
base `4f12233`. Alcanzó disponibilidad inicial pero no solicitó slots. Se conserva
la suspensión `availability_lost:RX-01`: última fila válida con edad 1006,375455 ms,
cola de 768 bytes sin LF y RX-02 con edad 5,673129 ms. Hubo 107 ticks y lecturas
continuas en el intervalo causal; no se demuestra una pausa global del host o
un bloqueo interactivo de un segundo. La causa física del hueco sigue indeterminada.

[Clocks, persistencia, límites y corrección del informe](../results/DIAGNOSTICO_EXP02_AVAILABILITY.md):
el nuevo esquema separa apertura física durante adquisición de ausencia de apertura
por el auditor offline. Los originales se conservan con enmienda nueva; rechazo,
datos, ambos cierres confirmados y autorización consumida permanecen intactos.
246 pruebas aprobadas, cero omisiones, 2459 archivos previos preservados. No cambian
capturador, umbral, políticas, firmware o detector. Sin UART, captura nueva, resets
o reconexiones durante este diagnóstico; no hay reintento autorizado.

## Diagnóstico de continuidad dual separado — preparación del 3 de noviembre

Desde `6450919`, [continuity-dual-1](CONTRATO_CONTINUIDAD_DUAL_1.md) y su
[plan de 60 s para revisión](PLAN_CONTINUIDAD_DUAL_60S_R1.md) reutilizan identidad,
apertura preservando entrada, almacenamiento y cierre. Cada RX tiene lector
independiente sin stdin. Silencio >1 s produce incidencia y permite observar
recuperación; transporte/almacenamiento fallidos detienen ambos. No hay ventanas
elegibles, etiquetas ni aprobación de calidad, calibración o entrenamiento.

[Validación offline](../results/CONTINUIDAD_DUAL_1.md): 262 pruebas aprobadas,
cero omisiones, y ensayos PTY de 60 s reales. Se conservan brutos, fragmentos,
referencias por fila, relojes y diferencias de callbacks/descartes sin inferir
pérdida RF. v4, su watchdog y todos los intentos/rechazos/autorizaciones anteriores
permanecen intactos. No se abrió UART físico ni se ejecutó preflight sobre las
ESP. La copia local nueva conserva declaraciones pendientes; antes de ejecutar
se requieren su confirmación y autorización explícita para un único intento.

## CONT-DUAL-01 físico consolidado offline — 3 de noviembre

El operador ejecutó el único diagnóstico autorizado desde `c243406`. El
[informe r1](../results/DIAGNOSTICO_CONTINUIDAD_DUAL_01_R1.md) verifica 60 s,
integridad/replay correctos, ambos cierres y autorización consumida. Conserva
171/296 filas válidas y dos colas de 640 bytes. RX-01 tiene tres incidencias
host recuperadas con id consecutivo y queue_drops=0; intervalos locales de
400–800 ms también aparecen fuera de ellas. RX-02 conserva cadencia próxima
a 200 ms. Servicio continuo de ambos lectores, sin pausa global de escala 1 s
en los relojes registrados; causa RF/firmware/transporte no localizada.

269 pruebas offline aprobadas, cero omisiones, incluidas siete nuevas del
analizador reproducible y preservación del bundle. El experimento mínimo
propuesto añade observación pasiva independiente de UART para separar emisión
de entrega USB/host; no resolvería por sí solo RF frente a filtro/driver.
Ninguna nueva captura, apertura UART, reset, reconexión, firmware, calibración
o cambio del watchdog v4 durante el análisis. No hay reintento autorizado.

## Viabilidad del intercambio pendiente — declaración posterior del operador

Alan declara cables de aproximadamente 20 cm y RX a ambos lados de la laptop;
no puede confirmar alcance conservando cable y puerto. Se registra viabilidad
**dudosa** y no se prepara ejecución A–B–A. La [alternativa para revisión](VIABILIDAD_MONTAJE_CONTINUIDAD_R1.md)
propone estudiar orientación local solo si hay holgura, con menor alcance causal,
y explica los efectos de desconectar/cambiar puerto (alimentación, arranque y
camino USB). No se movieron equipos, abrieron UART, ejecutaron capturas ni
cambiaron firmware, umbrales, resultados o autorizaciones. Sin compra propuesta.

## Orientación RX-01: plan A–B–A presentado para revisión

El operador confirma que RX-01 puede girar sin tensión. El [plan r1](PLAN_ORIENTACION_ABA_CONTINUIDAD_R1.md)
define A1 actual, B propuesto +90° horario y A2 de regreso; tres intentos separados
de 60 s con continuity-dual-1 intacto. Ambos UART deben estar cerrados y su cierre
comprobado antes de los cambios físicos. RX-02/TX/laptop y cable/puerto de cada
RX se mantienen; registrar geometría y curva local del cable RX-01.

Tres JSON nuevos solo para revisión, sin referencias de autorización y con
declaraciones pendientes que bloquean ejecución. Falta confirmar plano/ángulo B,
marcas y contexto actual antes de solicitar autorización nueva. No se abrieron
UART, hicieron movimientos o capturas, cambiaron fuentes/políticas/firmware,
calibraron detectores ni alteraron datos o autorizaciones consumidas. El estudio
de orientación no equivale al intercambio de posiciones que sigue sin confirmar.

## Revisión del montaje con antenas externas — r2 pendiente

Se localizaron y abrieron los dos JPG `ChatGPT Image Nov 3, 2026, 02_23_17 PM`
y `02_23_29 PM` de Downloads. El operador declara que ambos RX usan antenas
externas por coaxial fino y no ha movido nada. El [plan r2](PLAN_ORIENTACION_ABA_CONTINUIDAD_R2.md)
distingue placa, antena/base, coaxial y USB. El giro de placa +90° de r1 no define
un giro de antena externa; su holgura no confirma la del coaxial.

Pendientes: asociar fotos a identidades, confirmar articulación/holgura y fijar
qué componente, eje y ángulo cambiarían en B. R1 y sus JSON se conservan bloqueados;
no se preparan ejecución o autorización r2 hasta cerrar la geometría. Sin apertura
UART, movimiento, desconexión, captura, firmware, calibración o cambio de política.

## Identificación física pendiente con rutas USB consultadas

Se consultaron solo sysfs y udev por ruta, sin abrir UART: RX-01 serie `5C93199744`
está en `3-7.1`, detrás de un hub GenesysLogic `05e3:0610`; RX-02 `5C93200689`
en `3-4`, sin ese hub intermedio. Ambos pertenecen al mismo controlador xHCI.
Las etiquetas físicas del sistema no distinguen los conectores externos; falta
confirmar visualmente qué cable llega al hub y cuál directamente a la laptop
antes de asignar las fotos. Ver [registro y observación necesaria](IDENTIFICACION_RX_USB_MONTAJE_R1.md).
Sin movimientos, desconexiones o capturas; originales y autorización consumida
verificados intactos. La articulación de antena se revisará después de identificar RX-01.

## Asociación fotográfica confirmada antes de revisar la antena

Alan confirma visualmente los extremos USB, sin mover o desconectar: foto
`02_23_17 PM` al hub marrón = RX-01, serie `5C93199744`; foto `02_23_29 PM`
directamente a laptop = RX-02, serie `5C93200689`. Se [registra la asociación](ASOCIACION_RX_FOTOS_CONFIRMADA_R1.md)
en un artefacto nuevo, conservando los metadatos y fotos originales. El punto
de identidad del plan r2 queda resuelto; articulación/holgura del coaxial y
definición de B siguen pendientes. Sin UART, movimientos, capturas o autorización nueva.

## Antena externa RX-01: intervención r3 presentada para autorización

Alan confirma articulación e inclinación de 90° sin desenroscar. El [plan r3](PLAN_ANTENA_ABA_CONTINUIDAD_R3.md)
selecciona solo el cuerpo móvil: A1 actual documentada, B a 90° en el plano de
la bisagra hacia arriba, A2 de regreso. Placa, base/conector, coaxial, USB y
conjunto RX-02/TX/laptop/hub fijos. Si ese sentido/plano no es posible sin tensión
o desplazamiento, se detiene la preparación antes de adquirir A1.

Tres intentos independientes propuestos de 60 s, cierre comprobado de ambos
UART antes de cada movimiento y cero reintentos. Tres JSON r3 y registro de
montaje nuevos solo para revisión; R1/R2, sus configuraciones, imágenes y datos
se conservan. Faltan registro A1/B, confirmación de partes fijas sin tensión,
declaraciones actuales y autorización explícita. No se abrió UART, hizo preflight
físico, movió antena/placa, desconectó equipo o capturó durante la actualización.

## Autorización r3 recibida; documentación previa a A1 pendiente

Alan confirma giro de 90° hacia arriba del cuerpo móvil, sin tensión o movimiento
de partes fijas, y autoriza tres únicos intentos A1/B/A2 y dos movimientos de
articulación entre ellos conforme a r3. La autorización queda registrada en
`results/local/preparacion-antena-aba-r3/autorizacion-serie.json`; es condicional a
documentar A1/B y completar declaraciones actuales antes de adquirir. No se pide
de nuevo esa autorización para el alcance ya concedido.

Copias locales nuevas del registro y tres planes preparadas; ejecución aún
bloqueada por documentación/declaraciones pendientes. Ningún intento iniciado o
consumido en la serie, salidas físicas inexistentes. Solo se guiará A1 tras esos
prerrequisitos; B depende de verificar integridad/replay y cierre de ambos UART
de A1, y A2 de los de B. Ante fallo detener la serie, sin reintentos, resets,
reconexiones, firmware, calibración o entrenamiento. Sin apertura UART, preflight
físico, movimiento o captura durante este registro de autorización.

## A1: referencia fotográfica vigente, croquis todavía pendiente

Alan declara que el montaje sigue como en las fotos, sin movimientos; está solo,
sentado frente a laptop enchufada y abierta, con puerta/ventanas cerradas y sin
ventilador. Se registra la foto RX-01 `02_23_17 PM` con hash como referencia visual
vigente y se describe la dirección de antena en el plano de la imagen; no se
infiere su inclinación 3D. El croquis no está hecho y no se marca como completo.

Siguiente observación única: si el cuerpo móvil negro está apoyado en la mesa o
levantado/inclinado, sin tocarlo. Suspensión automática, otros lectores/capturas,
alimentación TX y preflight actuales siguen pendientes; no se dieron por
verificados. Registro local `results/local/preparacion-antena-aba-r3/estado-previo-A1-01.json`.
Ejecución bloqueada; ningún UART abierto, movimiento o intento iniciado.

## Serie antena r3: A1 adquirido por el operador y verificado offline

El operador ejecutó solo `CONT-ANT-ABA-R3-A1`: 60,006937558 s comunes,
integridad/replay correctos y cierre confirmado de ambos UART, con una apertura
y un cierre por RX. Se verifican 294/296 filas, sin incidencias ni colas; ids
consecutivos, queue_drops=0 y ninguna anomalía posterior a la primera fila CSI.
El mensaje exacto de sniffer en arranque RX-01 conserva su clasificación original
y no se acepta como CSI ni se convierte el resultado en aprobación de calidad.

Bundle A1 y autorización consumida intactos. Verificación independiente guardada
en `results/local/preparacion-antena-aba-r3/A1-paso-a-B-verificado-r1.json`.
El siguiente paso autorizado es solo inclinar el cuerpo móvil de la antena RX-01
a B, tras estos cierres; el movimiento aún no se ha reportado y B/A2 no se han
iniciado. Esta revisión no abrió UART ni repitió capturas o cambió firmware.

## Serie antena r3: B verificado, regreso a A1 autorizado pendiente

El operador ejecutó B con antena RX-01 a 90° y partes fijas declaradas intactas.
Auditoría offline: integridad/replay correctos, 60,012542376 s comunes y ambos
cierres confirmados, una apertura/cierre por RX. RX-01 conserva 213 filas y dos
incidencias de silencio recuperadas; RX-02, 291 filas y ninguna incidencia.
Sin colas, saltos de id, cambios de queue_drops o anomalías posteriores al primer
CSI. Las incidencias siguen siendo observacionales, sin aprobación de calidad.

Se preservan B y su autorización consumida. Verificación en
`results/local/preparacion-antena-aba-r3/B-paso-a-A2-verificado-r1.json`.
El siguiente paso es solo el regreso ya autorizado de la articulación a la
postura A1 apoyada, con base/coaxial/placa y resto del montaje fijos. Ese retorno
no se ha reportado; A2 no se ha iniciado. Sin UART o nueva captura por el auditor.

## Serie antena r3 cerrada: A2 no reprodujo A1

El operador completó A2 y solicitó consolidar los tres bundles existentes. El
[informe con gráficos y hashes](../results/COMPARACION_ANTENA_ABA_R3.md) verifica
integridad/replay, duración común de 60 s, una apertura/cierre por RX y ambos
cierres en A1/B/A2. Las tres autorizaciones están consumidas, sin permiso restante.

RX-01: 294/213/201 filas, cero/dos/dos incidencias recuperadas. RX-02:
296/291/291, sin incidencias de 1 s. Todos los ids completos son consecutivos,
queue_drops=0, perfil constante y colas finales de cero bytes. Medianas RSSI
RX-01 −58/−54/−51 dBm; RX-02 −50/−49/−47. A2 no recupera A1, pese al retorno
mecánico declarado; el control cambia también su RSSI y las sesiones están
separadas por intervalos de minutos. No se establece causalidad por orientación.

Cinco gráficos comparables con runtime local fijado, sin instalar dependencias;
279 pruebas aprobadas, cero omisiones. Originales, fotos, planes y autorizaciones
consumidas conservados. Siguiente experimento mínimo propuesto: dos sesiones
A–A estáticas con intervalo fijado, sin ejecutarlas ni crear autorización nueva.
Sin UART, captura nueva, movimientos, firmware, cambios de watchdog o calibración
por esta auditoría. Los borradores previos se conservan como historia de preparación.

## Checkpoints RX-02: un diagnóstico físico sostenido consolidado offline

[RX02-DIAG-CP-R1](../results/RX02_DIAG_CP_R1.md) alcanza 240,007883569 s hasta
inicio de cierre; 1190 filas, ids consecutivos, queue_drops=0, cero huecos host
>500 ms, cola cero y cierre confirmado. Integridad/replay, identidad/espacio y
76 checkpoints verificados, pendiente final cero. La conexión sigue rechazada
por preámbulo. CPU 13,364 s y ru_maxrss 26596 KiB hasta fin de servicio; sin
muestreo físico periódico de fds/hilos ni equivalentes C02. Comparación con C02
conserva su rechazo y explica duración, control y condiciones sin causalidad.
Autorización diagnóstica consumida; C01/C02 y fuentes históricas intactos.
[Revisión C03](REVISION_C03_CHECKPOINTS_RX02.md) nueva solo offline, persistencia
explícita y permisos false, sin captura, calibración o entrenamiento.

## C03: integración optativa preparada sin UART

La [entrada C03](INTEGRACION_C03_CHECKPOINTS_RX02.md) selecciona explícitamente
checkpoints en plan, procedencia y auditoría. Sin campo de persistencia delega
al comportamiento histórico. Conserva E→S, partición y criterios; admite
RX-01 declarada desconectada solo en esta revisión. Plan local nuevo y salida
exclusiva reservada, sin adquisición. Condiciones actuales pendientes de una
consulta agrupada antes de preflight por metadatos y permiso nuevo. C02 y el
diagnóstico físico quedan intactos; sin calibración/entrenamiento.

## C03 consolidada offline: E/S y comparación con C01

[Informe y figuras](../results/RX02_C03_C01.md): C03 contiene 7414 filas, con
143/146 en E/S, bins/cobertura conforme, etiquetas humanas y ambas ventanas
exploratorias elegibles. Conexión estricta conserva rechazo por preámbulo.
495 checkpoints, pendiente final cero, cola cero y cierre RX-02 confirmado;
autorización consumida. C01/C03 se comparan por condición usando definiciones
existentes de RSSI/LLTF52/variabilidad, sin ajustes ni causalidad de presencia.
Diferencias de persistencia, montaje declarado y RX-01 alimentada/desconectada
documentadas. C02 y particiones intactas; 102 archivos originales preservados.
473 pruebas aisladas aprobadas; reserva C04–C06 sin acceder y cero intentos de
lectura registrados. Sin UART nuevo, captura adicional, calibración o entrenamiento.
