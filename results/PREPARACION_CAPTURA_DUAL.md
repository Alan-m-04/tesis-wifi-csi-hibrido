# Preparación de captura dual controlada

Cuarto hito, 25 de octubre de 2026. Rama `feat/preparacion-captura-dual` desde `56ea2702d362111faa4b470f69315547e65dd1a9`. **No se abrió UART física ni se ejecutó la captura propuesta.** El protocolo y comandos están en [PROTOCOLO_CAPTURA_DUAL.md](../docs/PROTOCOLO_CAPTURA_DUAL.md). Datos estructurados: [validación de preparación](preparacion_captura_dual.validacion.json) y [bytes del diagnóstico](diagnostico_arranque_offline.json).

## Diagnóstico demostrado sobre los originales

Se volvieron a leer los brutos del antecedente de 60 s y se conservaron sus hashes. RX-01 tiene 247862 bytes y SHA-256 `51cb3bb1cb191b5a85e09cfa8936c29f9c0e89d930e73802623defbdcae8125a`; RX-02, 250408 bytes y `5af63769f6bea835b037e3ad81e4f03ce4b5113ea266219d83fe8e4234f8d6ff`. No se modificaron ni se reconstruyeron sus matrices.

| Evidencia RX-01 | Localización exacta | Interpretación demostrable |
|---|---|---|
| Comilla + CRLF inicial | Bytes [0,3), línea 1 | Fragmento preservado; no es una muestra completa |
| CSI_DATA,3927,...ESP-ROM | Bytes [3,123), línea 2, 120 bytes con CRLF | Una sola línea física contiene prefijo CSI y ROM pegados; CSV tiene 33 campos, no 26; no hay matriz CSI recuperable completa |
| rst:0x1 (POWERON) | Línea 4, offset 142 | El log registra un arranque/reset; no demuestra su causa eléctrica |
| RX-01 READY | Línea 91, offset 4489 | Declara canal 11/HT20/UART0 y fuente esperados |
| Primera CSI completa después de arranque | Línea 94, offset 4660, id=0 | El contador local vuelve a cero; después hay 292 filas completas |

SHA-256 de la línea 2 íntegra: `60d7ec58af2e8eaab0cf4303f30153df97470627db3c1ce3c0c85a61c5305eb7`. El JSON de diagnóstico fija hex, offsets, longitudes y SHA por línea de los fragmentos iniciales. La regresión contiene exactamente esos 120 bytes y los fragmenta en varias lecturas sin repararlos. Sigue contando una línea malformada y rechazo, con bruto idéntico.

La lectura del capturador escribe cada chunk en el archivo bruto **antes** de decodificar o parsear; acumula hasta LF, sin insertar separadores ni reconstruir prefijos. Fragmentar lecturas por sí mismo no fabrica el texto CSI/ROM mezclado: al concatenar esos bytes, la línea original sigue dañada para cualquier fragmentación ensayada. El CSV solo recibe filas aceptadas y no es la fuente de ese bruto. No se conoce la segmentación exacta de reads de aquella ejecución porque faltaba el ledger; no se inventó.

RX-02 también comienza con un fragmento CSI sin prefijo, `--13`, byte no UTF-8 0xf8 y ESP-ROM pegado. Su primera línea ocupa [0,97); SHA-256 `88a09b3fff65f693b2321e925c567cc0926f6301f8da8c4c2498ba7e2dd4dedd`. El criterio histórico solo contaba CSI malformado si empezaba por CSI_DATA; por eso su flag individual seguía true. Se conserva ese resultado histórico, sin presentar el arranque como limpio. El protocolo nuevo rechaza esos residuos de encuadre reconocibles además de conservarlos.

## Hipótesis que no se convierten en conclusiones

Son compatibles con los bytes un flujo previo truncado, residuos de adaptador/kernel, reconfiguración/apertura que coincide con un reset o corrupción en el camino serie. POWERON no prueba desconexión de alimentación ni que DTR/RTS hayan causado ese reset. El código solicita ambas líneas false sin pulso deliberado, pero la documentación de pySerial reconoce glitches al abrir; no se midieron sus niveles eléctricos. Tampoco se demuestra con este registro una carrera en firmware o un problema de TX. No se cambió firmware para resolver una hipótesis.

Sí se demostraron por separado defectos del host: flush oculto en pySerial y conteo de tail, además del orden de cierre durante startup interrumpido. Esos defectos se corrigen porque son reproducibles; **no se afirma que expliquen causalmente los bytes concretos de aquella línea**. Para atribuir el reset harían falta nuevas evidencias autorizadas y, en su caso, medición eléctrica; el nuevo ledger solo mejorará la trazabilidad temporal de lo que lea el host.

## Revisión y cambios comprobables

| Aspecto | Antes / limitación | Preparación actual y regresión |
|---|---|---|
| Apertura/flush | pySerial 3.5 POSIX open llama TCIFLUSH aunque el programa no resetee buffers explícitamente | Subclase local inhibe solo ese hook al abrir y prohíbe flushes explícitos; PTY con entrada previa la conserva; la clase original sí llama tcflush |
| Exclusividad | exclusive=True equivale a flock consultivo | Se mantiene y prueba contra otro abridor cooperante; no se proclama bloqueo universal |
| DTR/RTS | False antes de abrir; posible glitch del driver | No se cambia el estado solicitado ni se garantiza ausencia de reset; no hay pulsos ni escrituras serie |
| Fragmentación | Parsing por LF, misma marca host para filas del chunk | Conservado y probado con un byte por read y fila dividida; ledger nuevo registra rangos/tiempos de reads no vacíos |
| Límites | Acumulador >65536 se libera para parsing; bruto ya guardado | Contador de cola independiente: 150000 bytes sin LF ya no se subcuentan; oversized_lines mantiene rechazo; no se limpia el dispositivo |
| Fallo de segundo RX | El flujo antiguo no recogía desde la primera apertura | Nuevo coordinador arranca el primer lector antes de abrir el segundo y preserva sus bytes ante fallo |
| Startup/cierre | Una excepción antes de abrir gate podía cerrar puertos antes de juntar lectores; join de hilo no iniciado fallaba | Gate/stop y join dentro de ExitStack, solo hilos iniciados; regresiones de interrupción y fallo de creación de hilo, además del nuevo coordinador |
| Calidad histórica | 292/291 filas, rechazo global, flag RX-02 true con residuos iniciales | Se mantienen; controles sin ledger/postflight históricos se expresan como no aplicables, no como mediciones nuevas exitosas |
| Protocolo nuevo | No existía declaración completa previa | 30 s comunes, envolvente total explícita, ledgers, identidades antes/después, ambiente obligatorio y ningún recorte aprobado |

El módulo serial instalado no se modificó, ni los originales del árbol restaurado. El capturador activo ahora es una derivación documentada de la copia verificada. Los hashes antes/después de cuatro archivos derivados están en el resumen; las fuentes de firmware permanecen idénticas. provenance.json futuro registrará hashes actuales de código/configuración/commit y firmware instalado desconocido, no el hash de un .bin supuesto.

## Arranque y validación acordados antes de ejecutar

No se limpian buffers ni se descarta un warmup silencioso. Se conserva el preámbulo desde cada apertura completada y todas las lecturas hasta el cierre previsto, incluidas las que retornen después del límite común. No se promete lo que no leyó el host ni se drena indefinidamente un flujo que continúa emitiendo.

La ventana común de 30 s arranca cuando ambos lectores están listos. La envolvente total comienza antes de abrir y termina después de cerrar, de modo que puede durar más de 30 s. Se registran ambos límites y las marcas de ciclo de vida; no se alteran timestamps para ajustarlos a 30 s. Los clocks RX siguen independientes y los callbacks no son secuencias TX.

stable_window=null: **no se genera ni se aprueba una ventana estable derivada**. Los errores de arranque quedan en el resultado completo; los conteos de la ventana común no lo sustituyen. Un eventual protocolo futuro con recorte deberá preservar explícitamente ambos resultados y la procedencia, y requerirá otra decisión.

El auditor conserva sus criterios anteriores y agrega para controlled_dual_v1 la integridad de ledgers, cobertura exacta de bytes, asociación de cada fila al read que completó su último byte, identidades postflight y ausencia de cola incompleta/residuos de encuadre identificables. No se considera aprobado por tener exactamente 150 filas o por terminar sin excepción; tampoco la aprobación de formato demostraría precisión experimental.

## Pruebas reales de software ejecutadas

`./tools/test_offline.sh results/local/visualizacion-csi-entrega/canonical.json`:

| Conjunto | Casos | Fallos/errores | Omitidos |
|---|---:|---:|---:|
| Python unittest | 93 | 0 | 0 |
| Node nativo, consumidor RuView del tercer hito | 31 | 0 | 0 |
| Total | **124** | **0** | **0** |

Se ejecutaron las 103 del hito anterior y 21 casos nuevos de preparación. Desglose por evidencia: 115 casos sintéticos/PTY privados, uno que reproduce en memoria el fragmento histórico exacto y ocho regresiones sobre archivos históricos completos. Ninguno es una adquisición física nueva ni añade filas a campañas experimentales. Los subtests/fragmentaciones no se cuentan como casos adicionales.

Las pruebas corren con red aislada y /dev privado. Incluyen apertura POSIX únicamente sobre PTY generados en ese sandbox, no los receptores. Se probaron modo predeterminado sin UART, ambiente pendiente, duración/vistas no autorizadas, exclusividad consultiva, entrada previa preservada, colas excesivas, fragmentación, ledger alterado incluso con hash recalculado, fallo/interrupción de segunda apertura, hilo que no llega a arrancar, orden de cierre y etiquetas sintéticas/controladas. Los brutos históricos siguen idénticos y su rechazo estricto se conserva.

Además se comprobó el analizador/exportador de punta a punta con **puertos en memoria**: `results/local/ensayo-memoria-controlado-20261025/`, evidencia synthetic_fixture, y `results/local/ensayo-memoria-analisis-20261025/visualization/index.html`. Produjo cuatro vistas marcadas «prueba sintética controlada con validación estricta rechazada», nunca captura física. El retorno 1 era esperado por el error inyectado, no un fallo de la prueba de software. Los tests unitarios y este ensayo están separados de los datos de RX-01/RX-02 reales.

No se abrieron los UART reales ni se ejecutó su preflight udev durante esta preparación; las identidades de la tabla del protocolo son las históricas esperadas, y se verificarán obligatoriamente antes de abrir después de autorizar. No se instaló software, no se modificó ESP-IDF, no se flasheó ni se entrenaron modelos.

## Estado de preparación y siguiente decisión

Quedan listos el plan/plantilla, el modo de preflight, el capturador corregido, el coordinador de 30 s, manifests/procedencia, validación y análisis/visualización posterior en otro directorio. El directorio propuesto `results/local/captura-dual-30s-20261025-plan01` **no se ha creado como captura física**. Los archivos previstos y el comando exacto están en el protocolo.

Pendientes antes de ejecutarlo: declaración ambiental real del operador, confirmación de presencia/identidad USB mediante preflight y **autorización explícita para abrir RX-01 y RX-02**. El comando falla antes de abrir mientras el plan local contenga campos ambientales null. Esta entrega no solicita permiso para flashear, cambiar firmware, instalar RuView, abrir TX-01 ni entrenar.
