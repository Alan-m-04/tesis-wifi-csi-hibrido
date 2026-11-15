# Evaluación Edge AI por sesiones completas — preparación offline

El comando `tools/evaluar_edge_ai.py` lee sesiones etiquetadas, extrae LLTF52
y evalúa una cabeza estadística para **vacío / ocupado sentado**. Esta entrega
solo ejecutó datos sintéticos. No se entrenó, calibró ni infirió con registros
físicos, ni se conectaron ESP o abrieron UART. No hay detector en vivo o modelo
desplegado en una ESP. El procesamiento permanece en PC local.

## Reproducir el ensayo sintético

Desde la raíz del repositorio, con las ESP desconectadas y sin instalar nada:

```bash
.venv/bin/python -B tools/evaluar_edge_ai.py synthetic \
  --output-new results/local/edge-ai-synthetic-NUEVA
```

La carpeta debe ser nueva. Se conservan CSV CSI inventados, referencias de bytes,
hashes, etiquetas, fixtures explícitos de decisiones de auditoría, manifiesto
de sesiones y reportes `report.json` / `report.md`. **No son capturas físicas**.
El generador no abre PTY, UART ni sockets y no descubre otros bundles.

Para repetir únicamente lectura, extracción y evaluación del dataset ya guardado:

```bash
.venv/bin/python -B tools/evaluar_edge_ai.py evaluate \
  --manifest results/local/edge-ai-synthetic-20261114-r1/dataset-synthetic/sessions.json \
  --output-new results/local/edge-ai-reevaluacion-NUEVA
```

La ejecución final conservada está en `results/local/edge-ai-synthetic-20261114-r3/`.
Su [JSON agregado versionado](../results/EDGE_AI_SINTETICO_20261114.json) guarda
características, particiones, parámetros, predicciones por ventana, métricas por
sesión, SHA-256 de entradas e implementación y atribución RuView. El
[reporte legible](../results/EDGE_AI_SINTETICO_20261114.md) conserva la matriz.

## Componentes y unidad de evaluación

Se reutilizan `frame_from_reference`, `validate_sample`, el decodificador canónico,
`extract_eligible_window`, `presence_offline.row_mean` y `PresenceSpecialistPort`.
El port corresponde a RuView `fefb0f918eefa7db6daef8cc83787fc7d6f74187`, MIT;
fuentes, hashes y licencia permanecen en `vendor/ruview/presence/`. No se cambiaron
el port, el extractor o el capturador. No se repitió la equivalencia Rust completa.

Cada fila aporta la media de amplitud de los 52 tonos LLTF activos. Cada ventana
original de 30 s aporta media y varianza poblacional de esas medias. No se
incluyen DC, guardas o HT-LTF ni se interpolan, rellenan o remuestrean filas.
Una máscara requerida incompleta invalida la característica de la ventana entera.
El rechazo de conexión se conserva como dato; los rechazos sintéticos nunca
se presentan como aceptación de una adquisición nativa.

La partición se declara por **conexión completa / `partition_group`**. E y S
de cada conexión permanecen juntas. Hay al menos dos grupos de entrenamiento
y dos de evaluación, con ambas clases por conexión. Es un mínimo del contrato
de software, no una justificación del tamaño muestral de una campaña real.
Se rechazan IDs/bundles duplicados, alias de ruta y grupos cruzados. Las
referencias originales no pueden repetirse o compartirse entre E y S.

El modelo usa únicamente características de entrenamiento. Se mantiene la
política original: primera ancla `Empty` en orden lexicográfico de sesión y
promedio sin ponderación de todas las anclas `Sit`. Las demás anclas vacías
no ajustan la cabeza. No hay selección de características, normalización,
búsqueda de umbrales o ajuste con evaluación. Si el entrenamiento está
incompleto se detiene; si no hay separabilidad el modelo se abstiene. Un
modelo sintético no se carga ni transfiere para clasificar datos físicos.

Hay una decisión por ventana E/S, no una decisión por fila ni por persona.
La matriz tiene filas de verdad y columnas vacío, ocupado y abstención.
Se informan FP, FN, cobertura, abstenciones, exactitud sobre decisiones y
aciertos sobre todas las ventanas. La tasa de falsas alarmas se da con dos
denominadores: `FP/(FP+TN)` y `FP/todas_las_ventanas_vacías`. Los cocientes
sin denominador son `null`; el margen del port no es una probabilidad.

El fixture contiene dos conexiones de entrenamiento (cuatro ventanas) y tres
de evaluación (seis ventanas), de 150 filas inventadas por ventana. Incluye
deliberadamente un falso positivo, un falso negativo y dos ventanas con máscara
inválida. La matriz resultante tiene **1 en cada celda**, dos abstenciones y
cobertura 4/6. Son casos construidos para comprobar contadores y barreras;
no estiman sensibilidad, precisión física, generalización o utilidad comercial.

## Entrada futura con capturas válidas: comando y bloqueo vigente

El manifiesto usa `schema=tesis-edge-labeled-sessions-1`, `receiver=RX-02`,
`scope` fijo de receptor/geometría y una lista `sessions` con `id`,
`partition_group`, `split` (`train`/`evaluation`) y ruta `bundle`, relativa al
manifiesto. Las fuentes permanecen dentro de esa carpeta, separadas de la
salida. No se acepta SQL, búsqueda de sesiones o descubrimiento de puertos.

Con un manifiesto revisado y capturas válidas, el punto de entrada previsto es:

```bash
.venv/bin/python -B tools/evaluar_edge_ai.py evaluate \
  --manifest results/local/edge-ai-desarrollo-valido/sessions.json \
  --output-new results/local/edge-ai-desarrollo-evaluacion-r1
```

**Este comando todavía no está habilitado para entrenar con la campaña actual.**
La ruta física exige permisos prospectivos en el plan original (`training` o
`evaluation` según partición, además de `calibration` al entrenar),
`edge_scope` coincidente, datos de desarrollo, auditoría nativa de
integridad/replay, calidad estricta aceptada, cierre
confirmado, E/S declaradas y características completas. No basta con cambiar
`evidence_type` en un manifiesto o con una ventana exploratoria elegible.

Los contratos nativos actuales exigen `permitted_uses.training=false` y no
habilitan `evaluation`; no existe hoy un conjunto real admisible por esta ruta.
Antes de usarla se debe revisar el **contrato prospectivo y su adaptador/auditor**
para capturas nuevas autorizadas, probar el recorrido real aceptado y fijar
grupos, ámbito, método y criterios. La ruta de rechazo sí está probada; la ruta
real aceptada sigue pendiente. No se deben editar planes históricos para
satisfacer esos campos ni relajar sus auditores. Esto deja el punto de entrada
y las barreras preparados, no una validación real completa.

El piloto SQLite es `diagnostic_only`, sin etiquetas; C01/C03 son exploratorias,
C02 conserva su rechazo y R5-N01 no tiene ensayo humano completado. Ninguno
se promueve a entrenamiento. **C04–C06 están bloqueadas incluso como rutas o IDs**:
la evaluación aquí preparada es sobre desarrollo independiente, no sobre esa
reserva final. Revisar boot, día y montaje compartidos antes de fijar grupos
físicos correlacionados; separar conexiones por sí solo no prueba independencia.

## Pruebas

```bash
PYTHONPATH=src:tools:tests .venv/bin/python -B -m unittest \
  test_edge_presence_evaluation test_presence_synthetic_pipeline \
  test_presence_adapter_review test_presence_offline -v
```

42 pruebas aprobadas sin omisiones. Incluyen recorrido de I/Q con valores
conocidos, matriz con errores y abstenciones, denominadores, ausencia de
separabilidad, grupos cruzados, fuentes alteradas, conservación de entradas,
ausencia de ajuste con evaluación y rechazo de planes sin permiso de uso.
La prueba física histórica del extractor es solo descriptiva y de lectura;
no entrena ni infiere. La nueva evaluación solo se comprobó con I/Q inventado.

Bubblewrap no pudo crear namespaces; las pruebas se ejecutaron directamente
bajo la restricción del entorno y una barrera de auditoría Python de archivos
UART/reserva. No se atribuye aislamiento Bubblewrap. Ver
[checklist técnico](CHECKLIST_TECNICO.md) para evidencia y pendientes.

## Prevalidar la primera sesión sin entrenar

El punto de entrada `tools/prevalidar_captura_offline.py` no exige permiso de
entrenamiento: comprueba una conexión completa mediante su auditor nativo,
etiquetas E/S, elegibilidad estricta y exploratoria, cierre y LLTF52. Una sola
sesión puede verificar ese recorrido; nunca se usa para afirmar exactitud o
evaluar el modelo. Los motivos originales de rechazo permanecen en el JSON.

```bash
.venv/bin/python -B tools/prevalidar_captura_offline.py \
  --bundle results/local/devrep-rx02-r5-N01 \
  --output-new results/local/prevalidacion-r5-N01-r1
```

La salida debe ser nueva y estar separada del original. Código de salida 0
indica sesión apta para comprobar procesamiento; 2 indica rechazo y su motivo
exacto. No se cambian permisos, planes, etiquetas, umbrales o hashes originales.
La ruta real aceptada queda pendiente hasta disponer de esa captura; el
recorrido nativo aceptado/rechazado se ensayó con I/Q y relojes sintéticos.

Ver [contrato, dependencias y límites](PREVALIDACION_CAPTURA_REAL_OFFLINE.md).
