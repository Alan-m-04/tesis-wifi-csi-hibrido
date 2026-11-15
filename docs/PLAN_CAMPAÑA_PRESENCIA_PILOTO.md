# Propuesta para revisión: campaña piloto exploratoria de presencia

**Diseño pendiente de aprobación; no es autorización de adquisición ni de entrenamiento.** No se implementan aquí lanzador, anotador en vivo, mapas CSI, modelos ni funciones avanzadas. Presencia sigue siendo el primer hito del sistema; este piloto no sustituye el alcance del anteproyecto.

Revisión desde `f6829e18a1bccab46a7eca7361849e9d9c89bf2c`: **una sola persona**, sin otro operador ni equipo adicional supuesto. La [selección de componente RuView y revisión estática de READY](DETECTOR_PRESENCIA_RUVIEW.md) condicionan este plan. Antes de adquirir hay dos bloqueos operativos: confirmar control/cierre desde fuera con el inventario actual y resolver disponibilidad repetible sin suponer que reabrir produce READY.

## Pregunta, evidencia actual y unidad experimental

Explorar si el registro dual y las etiquetas pueden obtenerse de forma reproducible en una habitación bajo ausencia, presencia quieta y presencia en movimiento. Sentado/caminando son estratos de presencia, no clases de un modelo de actividades. No se calculará precisión ni se declarará presencia a partir de una ventana conforme.

El [único intento físico v3 consolidado](../results/CAPTURA_FISICA_V3.md) tiene una ventana conforme y conexión/global rechazados. Una sesión quieta no caracteriza variabilidad entre sesiones, personas o días, ni fundamenta suficiencia estadística. v1/v2/v3 existentes permanecen fuera de los conjuntos piloto propuestos; no se concatenan ni reetiquetan retrospectivamente.

Unidad: **una sesión dual independiente con una única ventana prospectiva de 30 s** y ambos RX. Los dos receptores, sus LTF y las filas de esa sesión pertenecen siempre al mismo grupo de partición. Se conserva la conexión íntegra desde apertura, incluso si falla disponibilidad, etiqueta o cobertura.

## Tres condiciones y montaje que debe fijarse antes

| Código | Condición dentro de la habitación | Procedimiento propuesto |
|---|---|---|
| E | Habitación vacía: cero personas | La única persona queda fuera, en un punto marcado junto a la laptop exterior; nadie entra hasta cierre confirmado. Mantener puerta en la posición fijada. Registrar también animales, ventilación u otros movimientos; «vacía» se refiere a esta habitación, no a toda la escena RF. |
| S | Una persona sentada y quieta | Silla marcada dentro, pies/apoyo y orientación documentados; sin hablar ni gestos voluntarios durante el intervalo. La laptop permanece fuera también en S/W. Respiración/micromovimientos naturales no se llaman ausencia de movimiento físico. |
| W | Una persona caminando | Recorrido de ida y vuelta P1–P2, propuesto de **2.0 m** entre marcas; comenzar en P1, avanzar a P2, girar y volver, continuamente. Objetivo de ejecución inicial: unos 4 s por tramo más giro, practicado antes, sin metrónomo/avisos dentro de la ventana. Es una instrucción operativa, no velocidad medida o validada. |

La posición concreta de P1/P2 respecto de TX/RX debe medirse y aprobarse en el croquis de montaje. Si el cuarto no admite 2 m libres de cables/equipos, revisar esa longitud **antes de adquirir**, sin improvisarla después de ver CSI. P1/P2 se mantendrán idénticos en todas las repeticiones W. En S se usa la misma silla marcada, sin desplazar laptop, RX o TX para facilitar el recorrido.

Antes del primer intento se requiere un manifiesto de montaje versionado y fijado por hash:

- Origen de referencia físico y posiciones/alturas/orientaciones medidas de TX-01, RX-01, RX-02, laptop, silla, P1/P2 y puerta. Registrar incertidumbre de las medidas y un croquis/foto de equipos sin inferir un mapa espacial CSI. La descripción actual «TX algo más de 2 m, un RX a cada lado» es aproximada y no completa este manifiesto.
- Marca y geometría del punto exterior de la única persona en E, junto a la laptop. En S/W esa persona está dentro y no queda otro operador fuera. Este cambio de posición exterior/interior es parte del contraste y un posible factor RF: no se supone que la pared elimine la influencia exterior ni se promete una escena exterior idéntica.
- Confirmar si los cables USB existentes permiten laptop fuera y ambos RX dentro, con puerta en un ángulo fijo y sin tensión. Se consultó, pero no hay respuesta registrada en esta revisión. No se suponen extensiones, segundo teclado/pantalla, teléfono, cámara ni otro PC. Si no es viable, la operación exterior está bloqueada con el inventario confirmado; no mover RX entre condiciones para compensarlo.
- Cables y puertos USB, fijación de RX, posición de antenas, alimentación de TX por el mismo cargador de pared y RX por USB a laptop; configuración de energía de laptop y programas en ejecución. No desconectar placas entre condiciones para conseguir READY.
- Identidades USB y MAC originales, canal 11/HT20, UART 115200, ESP-IDF v5.4, perfil CSI y fuentes/commit. Registrar que el binario instalado no está atestado mientras no exista evidencia independiente. Sin flashear ni modificar firmware para este plan.
- Puerta, ventanas, luces, ventilador/HVAC, objetos móviles y personas exteriores; registrar desviaciones. No cambiar hardware, geometría o configuración a mitad de campaña: cerrar ese bloque, conservar datos y revisar una nueva revisión de montaje antes de continuar.

## Duración, repeticiones y orden fijados prospectivamente

Se proponen **18 slots de intento: seis por condición**, organizados en seis bloques de tres condiciones. Cada slot conserva v3: espera de disponibilidad máxima 10 s desde A; una ventana de 30 s; finalización hasta LF de línea pendiente con máximo 250 ms/65536 bytes por RX. El presupuesto de lectura ordinario puede llegar aproximadamente a 40.25 s por intento más configuración/cierre reales; no es garantía de tiempo real duro.

Se propone un trabajo de **un solo slot**, iniciado desde fuera: demora de **60 s antes de A**, con aviso de inicio de etiqueta a los **30 s**. Para S/W, la persona entra sola y establece la condición antes de ese aviso; en E permanece fuera. No es warmup calibrado ni prueba de estabilidad RF; durante la demora no se abre UART ni se promete registrar bytes anteriores a la apertura. Son 30 s planificados entre aviso y apertura, con tiempos reales registrados. La condición se mantiene hasta el aviso posterior al cierre comprobado de ambos puertos más 10 s. Este trabajo mínimo todavía no existe ni se implementa en este cambio.

| Bloque | Visita propuesta | Orden de slots | Destino de sesiones completas |
|---|---|---|---|
| B01 | 1 | E → S → W | Desarrollo exploratorio |
| B02 | 1 | S → W → E | Desarrollo exploratorio |
| B03 | 1 | W → E → S | Desarrollo exploratorio |
| B04 | 2 | E → W → S | Desarrollo exploratorio |
| B05 | 2 | W → S → E | Reserva de evaluación futura |
| B06 | 2 | S → E → W | Reserva de evaluación futura |

Son las seis permutaciones: en el conjunto planeado cada condición aparece dos veces en cada posición. No equivale a independencia estadística ni balance perfecto de las particiones por separado. Dos visitas aportan una primera comprobación de deriva entre montajes/tiempos; registrar fecha, hora y cualquier cambio. Propuesta: misma persona en ambas visitas y pausas de unos cinco minutos entre bloques; generalización entre personas o a otras habitaciones queda pendiente.

Las 18 ventanas planeadas suman **9 min nominales de observación**, no 9 min garantizados de datos válidos. Se eligieron 30 s para conservar el protocolo revisado y seis repeticiones para recorrer órdenes y observar variación entre sesiones con un presupuesto acotado. No se afirma potencia o suficiencia para entrenar/evaluar un modelo.

Un slot es un intento, **no una obligación de obtener seis sesiones aceptadas por clase**. Timeout o rechazo conserva su ID y lugar en la tabla; no se sustituye, extiende, fragmenta ni repite automáticamente. Si faltan READY/disponibilidad, no resetear, reconectar, reabrir o cambiar el criterio: suspender los slots restantes para revisar el bloqueo de READY. Cualquier reemplazo exigiría un nuevo slot documentado y autorización nueva. Un fallo de identidad, almacenamiento/trazabilidad o cierre también suspende los slots restantes. **Los 18 slots son un diseño, no una secuencia ejecutable con disponibilidad repetida demostrada en v3.**

## Etiquetas y transiciones sin contaminar E

**Ruta mínima condicionada:** laptop fuera y ambos RX dentro con los cables existentes; mismo montaje en E/S/W y un registro de eventos del reloj monotónico del host. El inicio y el recibo se consultan en esa misma laptop desde fuera. Para S/W hacen falta avisos distinguibles de la propia laptop que se oigan desde la silla y el recorrido; su capacidad/audibilidad debe comprobarse sin UART antes de aprobar este método. No se supone que exista ese aviso ni se incorpora control inalámbrico. Si la laptop debe quedarse dentro, una demora permite salir pero **no resuelve comprobar cierre desde fuera** con los recursos confirmados; queda pendiente otra solución revisada, sin dar por disponible más equipo.

1. Fijar el ID, condición, bloque, partición, montaje/hash y orden del slot en `campaign-plan.json`. Desde fuera, registrar su intención, verificar preflight sin UART y lanzar solo ese trabajo autorizado; ninguna cadena de 18 capturas o reintentos. No cambiar firmware ni buffers.
2. En E, la persona comprueba que no queda nadie y se mantiene en el punto exterior. En S/W, entra y se sienta/inicia el recorrido antes del aviso a los 30 s. Mantener puerta en la misma posición prefijada. No entrar después a manejar la laptop durante E.
3. Registrar **C0 como tiempo real de emisión del aviso**, no como instante observado de postura/entrada. A se solicita a los 60 s y no antes de C0+30 s; si hay retraso del aviso, diferir A para respetar ese margen, sin abrir anticipadamente. A/T0/T1 son los tiempos efectivos del capturador, jamás retrocedidos. En S/W se requiere después una declaración explícita de que el estado ya estaba establecido al oír el aviso y se sostuvo; en E, declaración de permanencia fuera. El aviso programado **no confirma por sí mismo la etiqueta física**. Si se perdió, se llegó tarde o hay duda, etiqueta incierta del slot entero, sin mover C0 buscando CSI favorable.
4. El futuro trabajo espera la salida del proceso, verifica en sus registros **ambos eventos reales de cierre** y crea un recibo persistente referenciado/hash. Solo después de ese recibo y otros **10 s** emite el aviso de fin C1. Un cronómetro o solo el fin del proceso no confirman cierre. En E se comprueba recibo en pantalla sin entrar; en S/W se mantiene condición hasta ese aviso y después se sale para comprobarlo en la laptop. Ante timeout de disponibilidad puede haber cierre y recibo, pero no T0 ni ventana inventados.
5. Si faltan cierres, hay fallo del trabajo o no se oye el aviso final, no declarar cierre por haber transcurrido el tiempo nominal: registrar fallo/indeterminación y detener el piloto. Si la persona abandona la condición para comprobarlo, registrar esa desviación y etiqueta incierta; no emitir éxito falso ni relanzar automáticamente. El aviso de fallo debe distinguirse del recibo de cierre conforme.
6. Registrar declaración posterior, interrupciones, entradas, conversación, cambios de equipos y si la condición se mantuvo entre ambos avisos. [C0,C1) es un **intervalo planificado corroborado por declaración**, con incertidumbre humana no acotada instrumentalmente, no ground truth observada por otro operador. Exigir [T0,T1) dentro de ese intervalo con márgenes propuestos de 10 s; si hay ambigüedad que pueda intersectar la ventana, conservarla con etiqueta inválida/incierta, sin sustituir intervalo. No atribuir a esos márgenes estabilidad RF.

Propuesta de `labels.events.jsonl` append-only: `campaign_id`, `session_id`, `block_id`, `planned_condition`, `event`, `host_monotonic_ns` como entero decimal en texto, `utc`, `actor_pseudonym`, `observation_method`, `timing_uncertainty` (desconocida si no hay cota), `notes`. Distinguir eventos del host (solicitud, avisos C0/C1, A, disparo/timeout, T1, paradas/cierres, recibo) de declaraciones humanas posteriores (estado antes del aviso, continuidad, puerta, desviaciones). La hora de escribir la declaración no es la hora de la transición; no inventar un timestamp exacto de cruce/ocupación ni añadir muestras para rellenar márgenes.

Un manifiesto separado fijaría hashes del plan, etiquetas, montaje y bundle. No editar brutos/CSV para insertar etiquetas. Antes de implementar este trabajo mínimo: probar en memoria/PTY demora, avisos, timeout, error/aborto, dos cierres y ausencia de falso éxito si faltan recibos; después comprobar sin UART audibilidad y acceso exterior. No se implementa aquí automatización. Sin evidencia exterior suficiente, **aplazar el piloto**; no declarar vacío desde CSI ni entrar a comprobar la pantalla durante E.

## Cobertura prospectiva propuesta, aún sin aplicar

Estos son candidatos de ingeniería para **revisión y fijación antes de datos nuevos**. Se registrarían como un indicador adicional `pilot_coverage`, nunca como cambio de v3 ni de los rechazos históricos. No se calcula aquí si el registro existente los aprobaría.

| Candidato por RX | Propuesta para cada ventana futura de 30 s | Justificación y límite |
|---|---|---|
| Cantidad total | ≥120 filas válidas plenamente incluidas | Presupuesto operativo de 4 filas/s host en promedio, con margen respecto del objetivo aproximado de 5; no tasa RF garantizada ni muestra estadística suficiente. |
| Distribución | Seis bins fijos de 5 s desde T0; ≥15 filas incluidas en cada bin | Evitar aprobar solo una concentración al principio; bins definidos antes, sin mover fronteras para mejorar. |
| Huecos interiores | Máximo entre retornos LF consecutivos ≤500 ms | Límite operacional de falta de observación host, no diagnóstico de desconexión ni pérdida RF. |
| Bordes | Primera LF−T0 ≤500 ms y T1−última LF ≤500 ms | Hacer explícita cobertura del inicio y fin; no fabricar medidas entre muestras. |
| Integridad/continuidad/parada | Mantener todos los controles v3 y sus presupuestos | Sin tolerancia nueva de corrupción, callback, descartes, reloj local, colas o identidad. |
| Etiqueta | [T0,T1) dentro de [C0,C1), márgenes ≥10 s y sin transición ambigua | Validar el estado declarado durante toda la ventana; no autoetiquetar desde CSI. |

Aplicar cantidad, bins y huecos **en ambos RX por separado**, con la inclusión v3 `primera_lectura>=T0` y `retorno_LF<T1`. Reportar también timestamps repetidos/chunks compartidos y todos los huecos, sin interpolación. No exige exactamente 150 filas, RSSI constante o amplitud de baja varianza; no define estabilidad RF. Los candidatos se rechazan/revisan ahora si no son apropiados; nunca se ajustan tras ver nuevas capturas para aprobarlas. Una revisión posterior inicia otro contrato/lote, conservando los fallos del anterior.

La calidad de etiquetas, cobertura propuesta, disponibilidad, transporte/formato, parada y resultados `connection_full`/`experimental_window` deben quedar separados. Una ventana con etiqueta/cobertura conformes no borra rechazo de conexión/global. El catálogo de arranque y los prefijos actuales requieren revisión offline; no se autoriza entrenar con esas ventanas por este documento.

## Sesiones reservadas y prevención de fuga

B01–B04: hasta 12 sesiones para diagnóstico/desarrollo exploratorio, cuatro slots por condición. B05–B06: seis sesiones reservadas completas, dos slots por condición. La reserva se fija en el plan antes de adquirir; si un slot reservado falla no se reemplaza con uno de desarrollo por conveniencia.

No dividir aleatoriamente filas vecinas, LTF, receptores ni subventanas de una misma sesión entre entrenamiento y prueba. Cualquier futura normalización, selección de rasgos o umbral se ajustaría solo en desarrollo, con autorización y evidencia suficientes; evaluación se abriría una vez fijado el método. La comprobación de integridad/calidad puede ver los metadatos de todas las sesiones, sin seleccionar ejemplos por su rendimiento. Si se usa la reserva para elegir el modelo, deja de ser evaluación independiente y se necesitará otra reserva nueva.

La ruta seleccionada de [PresenceSpecialist](DETECTOR_PRESENCIA_RUVIEW.md) propone fijar **B01-E y B01-S** como anclas futuras de calibración por RX, sin ejecutar ajuste ahora ni sustituirlas por otras de mejor puntuación si fallan. W se conserva como estrato de evaluación de presencia, no se renombra como ancla `SmallMove`. Esta propuesta y la elegibilidad de sesiones deben revisarse antes de adquirir/calibrar; una ventana conforme no revoca el rechazo de conexión ni habilita por sí sola entrenamiento.

No se entrena ahora, no se garantiza que 12/6 sesiones sean suficientes y no se propone un porcentaje de exactitud esperado. No se afirma validación entre personas/días/negocios a partir de este piloto.

## Decisiones que bloquean una nueva adquisición

1. Aprobar propósito exploratorio, 18 slots/orden, dos visitas, pausas y partición completa; asignar IDs antes del primer intento.
2. Confirmar alcance de cables para laptop fuera/RX dentro, avisos de la propia laptop y posición de puerta fija. Completar medidas/croquis y recorrido de 2 m con una única persona. Si no es viable, el requisito exterior sigue bloqueado; no se presupone otro operador/equipo.
3. Revisar y probar offline un trabajo de un slot, demora de 60 s, aviso C0 a los 30 s, declaración posterior e incertidumbre, recibo de ambos cierres y aviso C1 diez segundos después. No modificar todavía el capturador ni afirmar que un temporizador observa la etiqueta.
4. Aprobar o cambiar ahora los candidatos 120 filas, 15/bin, 500 ms y márgenes de etiqueta; versionarlos separadamente del contrato v3.
5. Revisar offline la procedencia de prefijos y el catálogo de mensajes de arranque. Acordar si la campaña será solo diagnóstico mientras la conexión siga rechazada; cualquier nueva política necesitará versión y pruebas propias, sin reaprobar v1/v2/v3 históricos.
6. Resolver READY antes de lanzar la campaña: las fuentes actuales solo lo imprimen una vez en `app_main`, el host no lo solicita y v3 exige uno nuevo observado. No hay prueba controlada de repetición al reabrir. Una solución persistente/handshake/otro criterio requeriría revisión y versión separadas; no se adopta aquí. Con v3 actual, conservar timeout y suspender, sin resets/reconexiones para conseguir READY.
7. Obtener nueva autorización explícita para los slots físicos que se acuerden. No hay autorización vigente. Este plan no programa, abre ni consume ningún intento.
