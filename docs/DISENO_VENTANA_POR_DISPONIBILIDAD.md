# Propuesta para revisión: conexión completa y ventana experimental por disponibilidad

**Diseño solamente.** No está implementado en el capturador, no registra un nuevo protocolo ejecutable ni modifica v1/v2. No se abre UART, flashea, entrena ni adquieren datos nuevos. Primero se subió `cb504c4` a `origin/feat/captura-dual-v2`; el intento físico v2, su visualización, brutos y rechazo se conservan intactos.

## Dos alcances con resultados simultáneos

1. **Conexión completa:** registro desde cada apertura hasta el cese de lecturas, más eventos hasta el cierre de ambos puertos. Incluye preámbulo, evidencia de disponibilidad, ventana, finalización, bytes erróneos y colas. Mantiene auditoría estricta de todo el registro: los residuos iniciales siguen causando rechazo aunque una ventana posterior cumpla sus propias reglas.
2. **Ventana experimental:** un único intervalo futuro de 30 s del reloj monotónico del host, activado por la primera satisfacción de una condición decidida antes de ejecutar. Tiene auditoría, conteos y estado propios. Una ventana aceptada no aprueba la conexión completa. La pantalla deberá mostrar siempre ambos estados junto con la procedencia y las causas, sin ocultar el rechazo general.

Se almacenaría un solo bruto íntegro por RX, sin cortar ni sustituir el original. La ventana sería una referencia verificable a offsets, líneas, lecturas y timestamps, no una copia editada que borre el arranque. La finalidad es observar el flujo durante 30 s después de constatar disponibilidad operativa; no declarar estabilidad, presencia ni sincronización RF.

«Completo» significa todos los bytes que efectivamente devolvieron las lecturas. No garantiza bytes emitidos antes de abrir, durante configuración, nunca leídos o recibidos después del cese de lectura/cierre. Esas limitaciones se mantienen explícitas, sin inventar cobertura de cable.

## Señales reales inspeccionadas

Se inspeccionaron las fuentes propias de RX-01/RX-02, el parser, los ledgers y los brutos de las dos sesiones de 30 s conservadas. [Inventario offline con referencias y hashes](../results/DISPONIBILIDAD_SENALES_OBSERVADAS.json). No se construyó una ventana nueva sobre esos datos ni se modificaron sus informes.

| Señal | Qué aporta | Límite demostrado por código/registro |
|---|---|---|
| READY de RX-01 | Texto de identificación/configuración declarada en su UART | `firmware/csi_recv/main/app_main.c` lo imprime **antes** de `wifi_csi_init()`. Sus campos se imprimen como texto fijo. Por sí solo no confirma que CSI esté habilitado ni que se reciban paquetes. |
| READY de RX-02 | Mensaje después de inicializar CSI y consultar/comprobar canal/ancho | `firmware/csi_recv_02/main/app_main.c` consulta configuración antes de imprimirlo. Tampoco demuestra recepción continua, sincronización ni estabilidad. |
| Fila CSI válida | El host recibió una línea completa, parseable y compatible con el perfil/metadatos esperado | Puede estar en buffer; su timestamp host no es tiempo de recepción RF. Una fila no acredita flujo posterior ni el hash del binario instalado. |
| Varias filas consecutivas | Progreso del writer y continuidad observable de callback/reloj local | No demuestra frecuencia uniforme ni que no existan pérdidas RF. Los relojes y callbacks siguen siendo independientes entre RX. |
| Identidad USB verificada | Asocia el flujo al RX correcto | El texto READY no sustituye by-id/udev ni hace persistente la numeración ttyACM. |

En las dos sesiones, ambos READY son líneas completas que declaran canal 11, HT20, UART0=115200 y fuente 1a:00:00:00:00:00. Los tiempos siguientes se derivan del retorno de la lectura que completó el LF; son relativos al inicio original de la **envolvente**, no una estimación de arranque eléctrico:

| Sesión / RX | READY observado | Primera fila válida | Tercera fila válida |
|---|---:|---:|---:|
| v1 / RX-01 | 0.559741 s | 0.671865 s | 1.070175 s |
| v1 / RX-02 | 0.572117 s | 0.664364 s | 1.061805 s |
| v2 / RX-01 | 0.557295 s | 0.775818 s | 1.164365 s |
| v2 / RX-02 | 0.582477 s | 0.776644 s | 1.170400 s |

Los callbacks iniciales son 0,1,2 en los cuatro casos; no se impondrá comenzar en cero en otra conexión. Estas cuatro observaciones respaldan que las señales existen y son separables. No validan universalmente ningún tiempo máximo ni garantizan que READY se emita al abrir: un receptor ya funcionando puede no repetirlo. `ready_seen` actual es solo un booleano basado en una subcadena; **no basta para implementar este diseño**.

## Condición propuesta, fijada antes de ejecutar

Parámetros recomendados para revisión: **READY obligatorio en cada RX, tres filas válidas consecutivas posteriores por RX, frescura host máxima de 1 s y espera máxima de 10 s**. No habría fallback automático a «solo filas» si faltara READY.

Por cada receptor se exigiría, conjuntamente:

- Identidad USB prevista confirmada, lector activo y almacenamiento/ledger sin error.
- Un READY completo terminado en LF, con UTF-8 válido y gramática del mensaje inspeccionado: etiqueta del RX y tag correctos, canal 11, HT20, UART0=115200 y MAC fuente prevista. Solo se eliminan secuencias ANSI reconocidas para interpretar; los bytes se guardan intactos. No se acepta una mera subcadena pegada a basura, un mensaje de otro RX o de otra configuración.
- Después de ese READY, tres filas consecutivas del mismo flujo con LF completo y todos los requisitos de formato/perfil de v2: identidad, fuente, canal/ancho/estado, dimensiones, escalares int8 e indicadores de invalidez. Se conserva el modelo LTF documentado y condicionado; no se presume el binario instalado.
- Entre esas filas: callback local aumenta exactamente en uno, timestamp local progresa según la regla uint32 ya auditada (incluido wrap legítimo), sin incrementos/decrementos de descartes, sin línea CSI inválida, residuo, error de arranque o reset intermedio. No se compara el reloj local de un RX con el del otro.
- En el instante real de evaluación, la última fila válida de **cada** RX tiene retorno host no más antiguo de 1 s. Además de esos timestamps se guarda cuándo fue validada/procesada; no se interpreta frescura de lectura como frescura RF.

Tres filas proporcionan dos transiciones comprobables de contador/reloj y evidencian progreso, frente a una línea aislada que podría estar pendiente en buffer. Es un requisito operativo pequeño, no un tamaño estadístico ni una prueba de estabilidad. La frescura de 1 s evita activar la ventana con un RX que produjo datos y luego dejó de actualizarse mientras se esperaba al otro. Se propone por presupuesto de disponibilidad y margen sobre los intervalos observados, no como ley del enlace ni tasa mínima RF validada.

Una fila malformada/residuo antes de activar la ventana se conserva, afecta la calidad completa y reinicia a cero la racha de ese RX; no desaparece del resultado. Una expiración de frescura también reinicia su racha, sin desplazar el deadline de espera. Mensajes informativos íntegros y reconocidos no son muestras y no cuentan para la racha; bytes/líneas desconocidos la interrumpen. Puede cumplirse después la misma condición dentro del plazo fijo: es una regla prospectiva de la conexión actual, no otra captura ni una búsqueda posterior del intervalo más favorable.

Para evitar una lista abierta de excepciones, la propuesta inicial solo trataría como neutros la cabecera CSV exacta del perfil y líneas vacías íntegras; READY se procesa por su propia regla. Cualquier otro texto entre filas interrumpe la racha. Una futura ampliación de esa lista requeriría quedar fijada en la revisión, no decidirse después de ver la captura.

Los mensajes ROM/rst anteriores al primer READY se conservan como arranque observado; no se asigna causa eléctrica. Un nuevo reset, error de arranque reconocido, READY duplicado/conflictivo o reinicio de contador **después** de haber aceptado READY invalida la disponibilidad y aborta ese intento, sin rearmarla. No se espera otro arranque «más limpio». Una excepción UART, cambio de identidad, error de almacenamiento o pérdida de trazabilidad es fatal en cualquier fase.

READY podría faltar, quedar fragmentado o pertenecer a bytes previamente pendientes. La regla no demuestra una época de arranque atestada: solo coherencia del flujo observado, sin reset posterior detectado y con datos posteriores. Si faltan señales, no se pulsa reset ni se reabre para obtenerlas. Otro criterio requeriría revisión previa de un diseño distinto.

## Máximo de espera y activación única

Sea **A** el timestamp monotónico del evento inmediatamente anterior a la primera llamada de apertura. El deadline de disponibilidad se fija una sola vez en **D = A + 10 000 000 000 ns**. Incluye apertura/configuración, preparación de lectores y espera de ambos RX; abrir el segundo no reinicia el plazo. El primero se lee inmediatamente después de abrir, igual que en v2.

Los 10 s son un límite de operación propuesto, amplio frente a las señales observadas hacia 1.2 s y suficientemente finito para no esperar indefinidamente un RX/TX ausente. No son una duración de warmup calibrada ni un máximo físico demostrado. El controlador debe comprobar el plazo durante startup/lectura y al recuperar control de una llamada; un bloqueo de driver/planificación puede retrasar la limpieza real. Se registrarían los excesos y no se prometería tiempo real duro.

En la **primera evaluación** del coordinador en que ambos estados cumplen la condición, sin errores pendientes y antes de D, se guardaría atómicamente:

```text
T0 = monotonic_ns() en el acto de armar la ventana
T1 = T0 + 30 000 000 000 ns
```

T0 es el instante real de decisión, posterior a validar las señales. No se usa `max(timestamp de las terceras filas)` para retroceder el inicio. Una activación exactamente en D o después es timeout. Si los estados caducan antes de la decisión, no se arma con una foto antigua. READY o las filas que activaron la condición no se incluyen automáticamente: normalmente son preámbulo.

El coordinador debe procesar los eventos por orden de bytes de cada RX y consumir todos los ya devueltos en el chunk que aporta la señal antes de evaluarla; no debe armar por una tercera fila dejando sin revisar un reset/error ya presente en el mismo chunk. Debe resolver las colas pendientes de ambos lectores antes de la decisión y registrar la evidencia observada; una señal/error nuevo mientras se arma se procesa con su tiempo real, sin editar T0. La auditoría debe detectar conflictos que afecten la frontera. No hay orden RF implícito entre RX.

Haría falta una política de publicación por lotes y decisión coordinada, probada frente a concurrencia; el código actual no la proporciona. Si después se descubre un evento con retorno anterior a T0 que invalida la disponibilidad usada para disparar, se rechaza la ventana por evidencia de activación inconsistente. No se corrige T0 hacia otro instante ni se reemplaza el intervalo.

Si vence D sin disponibilidad, se declara **ventana no iniciada/no evaluable**, con causa por RX; no se fabrican 30 s vacíos. No se selecciona después otra región. Para una salida ordinaria por timeout se propone la misma finalización acotada de v2, referida a D (250 ms/65536 bytes por RX si queda línea pendiente); un error fatal o aborto elude esa espera. La conexión fallida y todos sus fragmentos se conservan.

Una vez fijados T0/T1 no cambian. Error, caída de flujo o reset dentro de la ventana causa el rechazo correspondiente; no se pausa el reloj, reinicia la ventana, busca un segundo comienzo ni extiende para acumular filas «buenas». La condición de disponibilidad no se vuelve a evaluar para desplazar el intervalo.

## Reglas de timestamps e inclusión

El intervalo experimental es **[T0,T1)** del reloj host. UTC se registra como referencia humana; no gobierna el disparo. Los timestamps locales uint32, RSSI, secuencias y metadatos originales no se alteran ni se usan para inventar una alineación RF.

Para cada línea/muestra se conservarían offsets y referencias a la primera y última lectura que la contienen:

- **s**: inicio monotónico de la primera lectura que aportó un byte de esa línea.
- **e**: retorno monotónico de la lectura que completó su LF; es el timestamp host original de la fila.
- Tiempo de validación/procesamiento y referencia a la decisión del coordinador, sin reemplazar s/e.

La propuesta conservadora incluye una fila experimental solo si es completa/válida y **s ≥ T0 y e < T1**. Por tanto, no basta que su LF llegue dentro de la ventana si su prefijo procede de una lectura anterior al inicio. Esta regla añade trazabilidad de primera lectura respecto de los conteos de v2, que usan el retorno final. No se cambiarán retroactivamente sus reglas o resultados.

| Caso | Inclusión propuesta |
|---|---|
| Primera lectura empieza en T0 y LF retorna antes de T1 | Incluida, si pasa todos los requisitos |
| LF retorna antes de T0 | Preámbulo; no incluida |
| Prefijo leído antes de T0, LF después | Cruza inicio: conservada como contexto, excluida del conteo experimental |
| Petición empieza antes de T0 y retorna después, incluso con varias filas | Se excluyen esas filas de la ventana por frontera ambigua; no se inventan tiempos individuales |
| LF retorna exactamente en T1 o después | Posterior/al límite: excluida, aunque la petición empezara antes |
| Varias filas terminan en un mismo chunk iniciado dentro | Comparten el retorno real y pueden incluirse; sin interpolación ni multiplicar frecuencia |
| Cola sin LF | Nunca se convierte en muestra; se conserva y clasifica por sus referencias de lectura |

Estas son ventanas de **observación por lecturas host**: un byte podía estar pendiente en el kernel/USB antes de la llamada. Ni s ni e es tiempo de llegada RF. La regla conservadora puede excluir filas físicamente recibidas durante la ventana; no reclama lo contrario ni las rellena.

La auditoría de errores abarca el flujo del intervalo, no solo las filas que aprobaron parsing. Para un error/residuo se usaría su intervalo de evidencia [s,e]; si intersecta [T0,T1), o no puede demostrarse que queda fuera, se rechaza la ventana. Una línea malformada no se oculta simplemente porque no entró al CSV. Una línea válida que cruza una frontera se conserva y excluye como contexto; no es por sí misma corrupción.

## Posteriores, cierre y reglas de rechazo

Al llegar a T1 se conserva la finalización de v2: si hay línea pendiente, llegar a LF con máximo hasta T1 + 250 ms y 65536 bytes adicionales por RX; si no la hay, terminar sin iniciar otra. Se guarda íntegro todo chunk en vuelo y toda lectura adicional. Las filas tardías quedan en el registro completo/contexto, con sus tiempos reales, sin aumentar los 30 s ni el conteo experimental. No se drena hasta silencio ni se promete conservar lo que nunca fue leído. Se juntan lectores antes de cerrar, con eventos por RX y postflight.

| Suceso | Conexión completa | Ventana experimental |
|---|---|---|
| Residuo inicial inequívocamente anterior a T0 | Conserva rechazo estricto correspondiente | No la rechaza por sí solo; muestra siempre el rechazo completo y el residuo excluido |
| Error/residuo dentro o ambiguamente sobre una frontera | Rechazo | Rechazo, aunque las filas completas sean válidas |
| Timeout de disponibilidad, READY ausente o incompatibilidad | Fallo de disponibilidad, registrado | No iniciada/no evaluable |
| Reset/READY duplicado después de aceptar READY, antes de T0 | Rechazo; sin rearmar | No iniciada/no evaluable |
| Reset, callback no monótono/hueco, descarte o perfil inválido dentro | Rechazo estricto | Rechazo según las mismas reglas, sin reinicio del intervalo |
| Fila íntegra completada después de T1 | Conservada con tiempo real, sin rechazo solo por ser tardía | Excluida, con causa visible |
| Texto erróneo demostrado enteramente después de T1 | Rechazo correspondiente | Sus bytes no contaminan retrospectivamente los datos de ventana; se mantiene el requisito de parada/identidad/trazabilidad conforme |
| UART/almacenamiento/ledger/identidad/cierre fallidos, en cualquier fase | Error/rechazo | No aprobable: la fiabilidad y cierre del intento son requisitos compartidos |
| Finalización agota límite, excede presupuesto o deja cola | Rechazo y fragmento preservado | No aprobable por parada no conforme; nunca completar artificialmente la cola |
| Ventana termina antes de T1 por aborto/fallo | Error/rechazo | Rechazo/incompleta; no se llama una ventana completa de 30 s |

La ventana exigiría además, como mínimo, una fila plenamente incluida por RX, controles de integridad de sus referencias, formato/perfil, continuidad de las secuencias locales, parada acotada conforme y postflight válido. Se reportarán número de filas, primera/última y mayores huecos, incluidos los bordes. Ese mínimo de cobertura mantiene la base de v2: **no certifica una señal medida continuamente durante 30 s**. No se exigirá exactamente 150 filas o 5 Hz ni se supondrán mediciones en tiempos sin muestras. Cualquier umbral adicional para una campaña/modelo debe fijarse antes en otra revisión, no después de ver resultados.

Dos resultados quedarían visibles permanentemente: `connection_full` y `experimental_window`, cada uno con integridad registrada, calidad de filas completas, cobertura, calidad de parada y causas de rechazo. El estado conjunto de la adquisición no se convertirá en «aceptado» si `connection_full` está rechazado. Se permitiría el texto explícito «ventana conforme; conexión completa rechazada», con el vínculo al bruto y las exclusiones. Si la integridad no permite evaluar, no se mostrará aprobación de ventana. No se modificarán las páginas v1/v2 existentes para aplicar esta propuesta.

## Evidencia que necesitaría una futura implementación

Antes de cualquier ejecución se fijarían un identificador/versionado de diseño aprobado, hashes de código/perfil/plan, parámetros de disponibilidad, máximo de espera y reglas de frontera. No se ha creado ese plan ejecutable ni una autorización.

Además de los archivos completos de v2, harían falta:

- Eventos de disponibilidad trazables a bytes: READY estricto, fila válida/inválida, racha, caducidad, reset/error, primera/última lectura, validación y decisión. El booleano actual no permite auditar todo esto.
- Un registro inmutable de A, D, T0, T1, evidencia de ambos RX y motivo de disparo o timeout. Los nanosegundos se conservan exactamente, sin redondeo.
- Un índice de inclusión/exclusión por fila/fragmento, con razones y hashes. No una búsqueda de subintervalos ni un CSV que esconda lo rechazado.
- Auditorías completas y de ventana separadas, más una visualización nueva que muestre ambos estados, disponibilidades y fronteras sobre el mismo registro.

Casos de revisión/pruebas todavía pendientes, **no ejecutados como protocolo nuevo**: READY ausente/fragmentado/falso, filas previas a READY, RX asimétricos o sin actualización, racha interrumpida, caducidad, timeout exacto de 10 s, error en el mismo chunk que la tercera fila, coordinación concurrente de ambas señales, fronteras T0/T1, lectura con varias filas, reset antes/después de disparo, agotamiento de cierre, aborto, fallo de un RX y cierre de ambos. Se probarían en memoria/PTY antes de considerar hardware.

No se modificó código ni se invocó un nuevo capturador. Las 155 pruebas anteriores no prueban esta propuesta y no se volvieron a ejecutar para un cambio documental. La comprobación actual es inspección offline de fuentes/señales, auditorías v1/v2 idénticas y hashes de preservación, incluida la visualización existente. Los registros v1/v2 no contienen los eventos de validación/decisión propuestos ni los 30 s completos posteriores a esa hipotética disponibilidad: **no pueden presentarse como validación física de una ventana nueva**.

**Recomendación para revisión:** aprobar o ajustar este criterio y sus límites antes de implementar un protocolo distinto. Hasta entonces, v1/v2 y su rechazo no cambian; no hay autorización para otro intento, ni flasheo, entrenamiento o inferencia de presencia habilitados.
