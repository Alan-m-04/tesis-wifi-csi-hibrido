# Revisión offline de PresenceSpecialist

El port Python está atribuido al componente MIT de RuView, commit
`fefb0f918eefa7db6daef8cc83787fc7d6f74187`, conservado con licencia y procedencia en
`vendor/ruview/presence/`. Implementa la cabeza `train/infer` con redondeo binary32;
no es el crate Rust, `Features::from_series`, un modelo preentrenado ni una
probabilidad calibrada. Esta sesión inspeccionó las fuentes locales.

## Recorrido comprobado

`audit_rx02` / `audit_c03_checkpoints` → elegibilidad exploratoria original →
`describe_windows` con referencias exactas → decodificación canónica existente →
`extract_eligible_window` → `presence_offline.row_mean` → características LLTF52.

El extractor histórico `presence_offline.extract_window` admite el contrato dual
v3. No debía aceptar silenciosamente el protocolo singleton de C01/C03. El nuevo
adaptador `eligible_presence_features.py` hace explícito ese protocolo sin cambiar
el extractor histórico: exige integridad/replay, etiqueta prospectiva conforme,
ventana elegible de 30 s, referencias y recuento originales, límites temporales
conservadores y máscara completa. No relaja los criterios experimentales.

Por fila se usa la media de amplitud de los 52 tonos LLTF activos; por ventana,
la media y varianza poblacional de esas medias, bajo el contrato existente
`presence-offline-v1/LLTF52/row-mean/session-population`. Una característica
incompleta produce `no evaluable`. Se conserva el rechazo de conexión completa.
No se llamó a entrenamiento, calibración o inferencia con C01/C03; la demo usa
solo características descriptivas.

La revisión siguiente añadió `tests/test_presence_synthetic_pipeline.py`: líneas
CSV CSI inventadas en memoria → verificación de referencias/hash → validador
existente → decodificación Im/Re y máscaras → características LLTF52 → envoltorios
sintéticos → `PresenceSpecialistPort`. Se verifican amplitudes conocidas, medias,
varianzas y salidas numéricas, conservando el rechazo histórico de la conexión
de prueba. Ni guardas/DC ni HT-LTF entran en LLTF52.

Las respuestas de integridad/replay/elegibilidad se inyectan como **fixture de
decisión de auditoría**, no se simula que una captura haya superado los auditores
físicos. Las conexiones ficticias `SYNTHETIC-CAL` y `SYNTHETIC-EVAL` son distintas;
sus E/S se mantienen en el mismo grupo y las consultas no modifican el modelo
de prueba. Solo se entrenó esa cabeza sintética con I/Q inventado. Sin modelo
no hay decisión; máscaras incompletas, incertidumbre, identidad, referencias,
fronteras o barreras de auditoría inválidas impiden obtener características
completas. Esto verifica integración de software, no exactitud física.

## Qué funciona

- Auditoría, procedencia, máscaras y extracción descriptiva de las cuatro
  ventanas C01/C03, sin fusionar conexiones ni receptores.
- Fórmulas de la cabeza y barreras de ámbito/receptor/ausencia de calibración en
  pruebas sintéticas. Se corrigió el consumo doble de generadores de anclas y la
  abstención ante registros sintéticos malformados. El AST de `train/infer` y
  sus funciones aritméticas se conserva idéntico al archivado antes de la sesión.
- Pruebas sintéticas de máscaras, referencias, fronteras, elegibilidad, desajuste
  de ámbito y falta de separabilidad; no se ajustaron constantes ni umbrales.

El algoritmo original toma **la primera ancla `Empty`** y promedia las anclas
ocupadas. No agrega automáticamente todos los vacíos ni pondera por número de
filas. Esta política ya tiene prueba sintética; no se cambió la cabeza ni los
extractores durante la revisión de controles/pipeline.

## Datos de desarrollo que faltan

Faltan suficientes conexiones **independientes y completas aceptadas**, con E y S
declaradas a tiempo, cierre comprobado y geometría/entorno/operador documentados,
para estudiar estabilidad y variación entre conexiones. C01/C03 siguen siendo
exploratorias; C02 y R1–R4 conservan sus rechazos. No constituyen un conjunto de
calibración autorizado. No se preparó otra adquisición para obtenerlo.

Falta fijar prospectivamente cómo se obtendrían las anclas de varias conexiones
de desarrollo, incluida la política de `Empty` descrita arriba, su ámbito de
receptor/geometría y el tamaño del conjunto según la variación que se pretenda
medir. No se escoge una conexión o agregación por su resultado en evaluación.
Muchas filas de una misma conexión no equivalen a muchas observaciones
experimentales independientes.

## Separación futura de calibración y evaluación

La unidad de partición es la **conexión completa** (`partition_group`): sus dos
condiciones, filas y subventanas permanecen juntas. Selección de características,
normalización y ajuste de umbrales se harían únicamente con desarrollo autorizado,
con validación por grupos de conexión. Antes de evaluar se fijarían método,
criterios y versión. C04–C06 mantienen su reserva de evaluación y no se abrieron;
no se consultan para elegir métodos o escalas. No se permite repartir filas o E/S
de una conexión entre calibración y evaluación.

La separación por conexión es necesaria pero no demuestra por sí sola
independencia: se deben documentar boot, día, montaje y condiciones compartidas,
y agrupar conexiones correlacionadas cuando corresponda. Antes de consultar la
reserva deben quedar fijados las métricas (incluidas abstención y cobertura),
los criterios, el método de incertidumbre por grupos y el artefacto de calibración.
La evaluación debe informar resultados por conexiones, sin tratar filas vecinas
como réplicas independientes. No se ha ejecutado esa calibración ni evaluación.

## Qué falta para detección en vivo

Un contrato prospectivo de ventanas en flujo con identidad y relojes comprobados,
calidad/máscaras/abstención, características compatibles, una calibración física
autorizada y validada en conexiones independientes, artefacto versionado ligado a
receptor y geometría, y pruebas de latencia, pérdidas y cierre seguro. También
requiere un nuevo plan y autorización física. Nada de ello queda demostrado por
esta reproducción visual ni por las pruebas sintéticas de la cabeza.

Se ejecutaron las clases sintéticas existentes de extracción y cabeza, más las
nuevas pruebas del adaptador. No se repitió la equivalencia Rust completa ni se
afirma validación física de presencia.

En la revisión posterior pasaron 33 pruebas Python seleccionadas de pipeline,
barreras y cabeza, más dos de la demo real (35 en total). Logs en
`results/local/revision-controles-presence-r1/`. El modelo numérico y los
extractores permanecieron intactos; no se repitió la suite completa ni Rust.
