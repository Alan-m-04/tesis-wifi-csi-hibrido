# Propuesta para revisión: campaña piloto exploratoria de presencia

**Diseño pendiente de aprobación; no es autorización de adquisición ni de entrenamiento.** No se implementan aquí lanzador, anotador en vivo, mapas CSI, modelos ni funciones avanzadas. Presencia sigue siendo el primer hito del sistema; este piloto no sustituye el alcance del anteproyecto.

## Pregunta, evidencia actual y unidad experimental

Explorar si el registro dual y las etiquetas pueden obtenerse de forma reproducible en una habitación bajo ausencia, presencia quieta y presencia en movimiento. Sentado/caminando son estratos de presencia, no clases de un modelo de actividades. No se calculará precisión ni se declarará presencia a partir de una ventana conforme.

El [único intento físico v3 consolidado](../results/CAPTURA_FISICA_V3.md) tiene una ventana conforme y conexión/global rechazados. Una sesión quieta no caracteriza variabilidad entre sesiones, personas o días, ni fundamenta suficiencia estadística. v1/v2/v3 existentes permanecen fuera de los conjuntos piloto propuestos; no se concatenan ni reetiquetan retrospectivamente.

Unidad: **una sesión dual independiente con una única ventana prospectiva de 30 s** y ambos RX. Los dos receptores, sus LTF y las filas de esa sesión pertenecen siempre al mismo grupo de partición. Se conserva la conexión íntegra desde apertura, incluso si falla disponibilidad, etiqueta o cobertura.

## Tres condiciones y montaje que debe fijarse antes

| Código | Condición dentro de la habitación | Procedimiento propuesto |
|---|---|---|
| E | Habitación vacía: cero personas | Participante y operador fuera; puerta cerrada y nadie entra hasta cierre confirmado. Registrar también animales, ventilación u otros movimientos; «vacía» se refiere a esta habitación, no a toda la escena RF. |
| S | Una persona sentada y quieta | Silla marcada, frente a laptop, pies/apoyo y orientación documentados; sin hablar ni gestos voluntarios durante el intervalo. Respiración/micromovimientos naturales no se llaman ausencia de movimiento físico. |
| W | Una persona caminando | Recorrido de ida y vuelta P1–P2, propuesto de **2.0 m** entre marcas; comenzar en P1, avanzar a P2, girar y volver, continuamente. Objetivo de ejecución inicial: unos 4 s por tramo más giro, practicado antes, sin metrónomo/avisos dentro de la ventana. Es una instrucción operativa, no velocidad medida o validada. |

La posición concreta de P1/P2 respecto de TX/RX debe medirse y aprobarse en el croquis de montaje. Si el cuarto no admite 2 m libres de cables/equipos, revisar esa longitud **antes de adquirir**, sin improvisarla después de ver CSI. P1/P2 se mantendrán idénticos en todas las repeticiones W. En S se usa la misma silla marcada, sin desplazar laptop, RX o TX para facilitar el recorrido.

Antes del primer intento se requiere un manifiesto de montaje versionado y fijado por hash:

- Origen de referencia físico y posiciones/alturas/orientaciones medidas de TX-01, RX-01, RX-02, laptop, silla, P1/P2 y puerta. Registrar incertidumbre de las medidas y un croquis/foto de equipos sin inferir un mapa espacial CSI. La descripción actual «TX algo más de 2 m, un RX a cada lado» es aproximada y no completa este manifiesto.
- Marca y geometría de los puntos exteriores donde esperan operador y participante en E. El operador queda en el mismo punto exterior en las tres condiciones. Las personas fuera pueden afectar RF: documentarlo, no suponer que la pared las elimina del enlace.
- Cables y puertos USB, fijación de RX, posición de antenas, alimentación de TX por el mismo cargador de pared y RX por USB a laptop; configuración de energía de laptop y programas en ejecución. No desconectar placas entre condiciones para conseguir READY.
- Identidades USB y MAC originales, canal 11/HT20, UART 115200, ESP-IDF v5.4, perfil CSI y fuentes/commit. Registrar que el binario instalado no está atestado mientras no exista evidencia independiente. Sin flashear ni modificar firmware para este plan.
- Puerta, ventanas, luces, ventilador/HVAC, objetos móviles y personas exteriores; registrar desviaciones. No cambiar hardware, geometría o configuración a mitad de campaña: cerrar ese bloque, conservar datos y revisar una nueva revisión de montaje antes de continuar.

## Duración, repeticiones y orden fijados prospectivamente

Se proponen **18 slots de intento: seis por condición**, organizados en seis bloques de tres condiciones. Cada slot conserva v3: espera de disponibilidad máxima 10 s desde A; una ventana de 30 s; finalización hasta LF de línea pendiente con máximo 250 ms/65536 bytes por RX. El presupuesto de lectura ordinario puede llegar aproximadamente a 40.25 s por intento más configuración/cierre reales; no es garantía de tiempo real duro.

Se propone una demora exterior de **60 s antes de A**, contada desde la confirmación de condición, para salir, cerrar puerta y establecer la etiqueta sin introducir al operador en E. No es warmup calibrado ni prueba de estabilidad RF; en esta demora no se abre UART y no se promete registrar bytes anteriores a la apertura. La condición se mantiene desde su confirmación hasta el cierre comprobado de ambos puertos, también durante disponibilidad y finalización.

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

Un slot es un intento, **no una obligación de obtener seis sesiones aceptadas por clase**. Timeout o rechazo conserva su ID y lugar en la tabla; no se sustituye, extiende, fragmenta ni repite automáticamente. Si faltan READY/disponibilidad, no resetear, reconectar, reabrir o cambiar el criterio. Cualquier reemplazo exigiría un nuevo slot documentado y autorización nueva. Un fallo de identidad, almacenamiento/trazabilidad o cierre suspende los slots restantes para revisión.

## Etiquetas y transiciones sin contaminar E

**Método preferido para aprobar antes del piloto:** un operador fuera y un participante, control local cableado desde fuera (teclado y pantalla/indicador exterior conectados al mismo host) y un registro de eventos del reloj monotónico del capturador. No usar control inalámbrico como condición añadida variable. Su disponibilidad, paso de cables y prueba offline del anotador/lanzador son pendientes; este cambio no los implementa ni asume que ya existen.

1. Fijar antes de cada slot su ID, condición, bloque, partición, montaje/hash y orden en `campaign-plan.json`. Preparar equipos sin cambiar firmware o buffers.
2. Establecer E/S/W. Para E, el operador verifica salida del participante y cierre de puerta desde fuera y solo entonces pulsa **confirmar vacío**. Para S/W, el participante establece el estado, lo confirma antes del registro y lo mantiene; el operador exterior registra **confirmar condición**. La ocupación de puerta puede observarse; postura/caminar siguen siendo declaraciones humanas si no se instrumentan, y así se etiquetan.
3. Esa confirmación define el **inicio conservador de etiqueta** C0 en el host; el estado ya debe estar establecido. Programar A no antes de C0+60 s. Registrar A/T0/T1 efectivos cuando existan, sin usar la hora programada para retrocederlos. El operador no entra ni manipula la laptop para iniciar E.
4. Mantener el estado hasta observar desde fuera el recibo de salida del capturador y los dos eventos `closed`, y **otros 10 s después de ese recibo** antes de C1. Así se conserva el margen posterior para una ventana completa. Si el host/driver se demora, no entrar por haber transcurrido solo un cronómetro. El indicador exterior solo confirma metadatos de cierre, sin necesitar una visualización CSI en vivo; ante timeout sin T0 se registra etiqueta pero no se fabrica ventana.
5. Registrar **fin de condición/solicitud de entrada** C1 antes de abrir puerta o permitir cambiar postura/recorrido. La etiqueta conservadora es [C0,C1); no requiere inventar el instante exacto del cruce de puerta, porque sus confirmaciones se ordenan físicamente después del inicio y antes del fin. Exigir [T0,T1) dentro de ese intervalo con margen propuesto de 10 s a cada borde; no afirmar que ese margen valida estabilidad RF.
6. Registrar toda entrada, conversación, interrupción de caminata, movimiento de equipos o desviación. Si pudo intersectar la ventana y no se puede acotar fuera, la etiqueta homogénea queda inválida/incierta. Conservar CSI y transición con sus tiempos; no buscar después otro tramo que salve el slot.

Propuesta de `labels.events.jsonl` append-only: `campaign_id`, `session_id`, `block_id`, `planned_condition`, `event`, `host_monotonic_ns` como entero decimal en texto, `utc`, `actor_pseudonym`, `observation_method`, `timing_uncertainty` (desconocida si no hay cota), `notes`. Eventos mínimos: transición solicitada, salida/entrada observada, puerta cerrada, confirmación C0, A, disparo o timeout, T1, paradas/cierres, C1 y desviaciones. Señales de confirmación y movimiento de preparación ocurren antes del margen, nunca se añaden muestras para rellenarlo.

Un manifiesto de campaña separado fijaría hashes del plan, etiquetas, montaje y bundle de cada captura. No editar los brutos ni el CSV original para insertar etiquetas; la asociación usa referencias y tiempos. Si no hay control y evidencia exterior suficientes, **no improvisar E entrando a comprobar la pantalla**: aplazar el piloto y revisar el método. No se declara «vacío observado» a partir de la propia señal CSI.

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

No se entrena ahora, no se garantiza que 12/6 sesiones sean suficientes y no se propone un porcentaje de exactitud esperado. No se afirma validación entre personas/días/negocios a partir de este piloto.

## Decisiones que bloquean una nueva adquisición

1. Aprobar propósito exploratorio, 18 slots/orden, dos visitas, pausas y partición completa; asignar IDs antes del primer intento.
2. Completar medidas/croquis y verificar recorrido de 2 m; confirmar participante y posiciones exteriores.
3. Disponer, revisar y probar offline control/anotación exterior, demora de 60 s, evidencia de C0/C1 y recibo de cierre, sin modificar todavía este capturador. Resolver etiquetas inciertas sin inventar precisión temporal.
4. Aprobar o cambiar ahora los candidatos 120 filas, 15/bin, 500 ms y márgenes de etiqueta; versionarlos separadamente del contrato v3.
5. Revisar offline la procedencia de prefijos y el catálogo de mensajes de arranque. Acordar si la campaña será solo diagnóstico mientras la conexión siga rechazada; cualquier nueva política necesitará versión y pruebas propias, sin reaprobar v1/v2/v3 históricos.
6. Resolver cómo se observará READY en aperturas futuras sin prometer que un receptor ya activo lo repita y sin resets/reconexiones para conseguirlo. Con v3 actual, si falta, aceptar timeout.
7. Obtener nueva autorización explícita para los slots físicos que se acuerden. No hay autorización vigente. Este plan no programa, abre ni consume ningún intento.
