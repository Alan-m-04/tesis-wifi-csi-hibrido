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
