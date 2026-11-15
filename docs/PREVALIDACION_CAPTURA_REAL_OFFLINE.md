# Prevalidación offline de una sesión real, antes de evaluar un modelo

El comando comprueba **una conexión completa ya registrada**: integridad del
bundle, replay nativo, etiquetas E/S, elegibilidad, cierre confirmado, referencias
originales, cobertura y extracción LLTF52. No abre UART, consulta USB, adquiere,
repara, reetiqueta, calibra, entrena o infiere. No modifica fuentes o planes.

## Comando para continuar

Desde la misma copia del proyecto y versión de fuentes que generaron el bundle,
con Python y pySerial de `requirements-dev.txt` disponibles:

```bash
.venv/bin/python -B tools/prevalidar_captura_offline.py \
  --bundle results/local/devrep-rx02-r5-N01 \
  --output-new results/local/prevalidacion-r5-N01-r1
```

El directorio de salida debe ser nuevo, estar en `results/local/` y separado
del bundle. Elegir `r2` para otra revisión, conservando `r1`. Si todavía no
existe la captura, el comando devuelve el error del archivo requerido ausente:
no inicia una adquisición ni presenta una sesión inexistente como rechazada
experimentalmente. El archivo `prevalidation.json` conserva el resultado.

Código de salida **0**: apta para comprobar el procesamiento de esa sesión.
Código **2**: no cumple, está incompleta o falta un prerrequisito. El JSON
incluye `rejection_reasons[].code/detail`, con el mensaje exacto del auditor
y los motivos de etiquetas/elegibilidad/calidad originales. No se recortan
arranques, residuos o errores para cambiar el resultado.

No basta copiar solo el bruto: se necesitan manifiesto, plan, procedencia,
operaciones, eventos, recibo de cierre y los archivos originales del protocolo.
La auditoría física R5 también exige sus referencias de entrada/práctica,
condiciones y autorización consumida ligadas por hashes. Deben estar accesibles
en la copia de adquisición; no se inventan ni se publican esos archivos privados.
Una revisión o copia de fuentes diferente puede producir un rechazo preciso
de procedencia. Preservar la versión usada al capturar.

## Qué se separa

| Comprobación | Requisito y resultado |
| --- | --- |
| Integridad y replay | Auditor original: hashes, secuencias, bytes, reductores, metadatos, persistencia y recibo; no se aceptan flags grabados como sustituto de replay. |
| Identidad y almacenamiento | Elegibilidad nativa reproducida. Un fallo conserva sus motivos originales. |
| Calidad estricta | Se conserva el rechazo de la conexión completa y el de cada ventana, aunque haya características descriptivas completas. |
| Etiquetas | Exactamente E y S de la misma conexión, declaradas y conformes. Incertidumbre, falta de declaración o plazo incumplido impiden aceptación. |
| Pertenencia/cobertura | Todas las referencias originales, sin duplicarlas o repartir E/S entre sesiones; 30 s, bordes y métricas reproducidas. |
| Características | Parser/decodificador existente y `extract_eligible_window`; 52 tonos LLTF activos, media por fila y media/varianza poblacional por ventana. Sin relleno o remuestreo. |
| Modelo | Siempre `model_training_executed=false`, `inference_executed=false` y `model_evaluation_ready=false`. Prevalidar no concede permiso de uso. |
| Conservación | Inventario SHA-256 antes/después. Se bloquean rutas/IDs reservados y enlaces que puedan introducir fuentes externas. |

Se admiten las revisiones nativas singleton RX-02 histórica, C03 con checkpoints
y R5-N01, seleccionadas por procedencia exacta. Una revisión desconocida se
rechaza explícitamente: no se interpreta mediante un auditor parecido.

Para poder auditar R5 desde una copia pública se incorporaron **16 dependencias**
de código/configuración que estaban sin confirmar en la copia original. Son
copias exactas verificadas, no modificaciones de esos archivos ajenos. Incluyen
el contrato plantilla R1 y el conjunto de fuentes que el auditor exige por hash.
Las rutas físicas existentes mantienen sus barreras de autorización. La nueva
entrada llama exclusivamente al auditor y no a sus ejecutores. No se publicó
ninguna condición actual, práctica confirmada, preflight o autorización local.

## Qué impide usar hoy una captura para evaluar el modelo

El evaluador de `9f73b69` exige varias conexiones: al menos dos grupos completos
de entrenamiento y dos de evaluación. Todos los E/S de un `partition_group`
permanecen juntos. Ese mínimo verifica software; no justifica el tamaño de una
campaña. Hay que controlar también día, boot, montaje y otras correlaciones.

Además, los contratos exploratorios vigentes fijan `training=false`,
`calibration=false` y no habilitan evaluación. La ruta real del evaluador
necesita un contrato prospectivo de uso, ámbito y particiones aprobado, así
como su adaptador/auditor comprobado. Su selector anterior tampoco admite R5.
Esta entrega añade **prevalidación y extracción R5**, sin fingir que habilita
entrenamiento R5 ni editar sus planes históricos para satisfacer esos permisos.

La primera sesión real **válida** permite comprobar el recorrido de punta a
punta con evidencia física. No permite evaluar precisión, sensibilidad o
generalización del modelo. Para ello hacen falta varias sesiones independientes,
verdad terreno y una separación fijada por conexiones completas antes del ajuste.
**C04–C06 continúan reservadas y no se consultan en este flujo.**

El piloto SQLite conserva 1.192 muestras y rechazo por preámbulo, sin etiquetas
E/S; no se promueve a entrada válida. C01/C03 continúan exploratorias. El ensayo
humano R5-N01 y las capturas reales etiquetadas siguen pendientes. No se acredita
validación en una MIPYME.

## Comprobación sintética

```bash
PYTHONPATH=src:tools:tests .venv/bin/python -B -m unittest \
  test_edge_session_prevalidation -v
```

Ocho pruebas nuevas utilizan I/Q inventado. Dos bundles R5 completos se generan
con relojes escalonados y PTY propios: uno cumple el contrato nativo y otro
conserva rechazo por preámbulo. La consulta posterior no abre ni esos PTY.
Se comprueban replay, extracción sin permiso de entrenamiento, fuentes alteradas,
etiquetas inciertas, ineligibilidad, máscaras incompletas, reserva y salida
existente. Los audios son respuestas grabadas de software, no ensayo humano.

Las decisiones de auditoría inyectadas solo se admiten con `--synthetic-fixture`
y se rotulan `synthetic_decision_fixture_not_native_audit`. No sustituyen a los
ensayos con auditor nativo y nunca constituyen aceptación física. Sin esa opción,
un fixture inyectado se rechaza. La evidencia de esta entrega es **sintética**;
el recorrido con una captura real aceptada aún no se ha ejecutado.

SQLite se verificó antes con HTTP en memoria; su revisión visual conectada en
Ubuntu sigue pendiente. Ni esa verificación ni estas pruebas reescriben fechas
reales como fechas del Anexo G. Ver [seguimiento corregido](AVANCE_ANEXO_G_2026-11-13.md).

Regresión publicable ejecutada (102 pruebas, sin fallos ni omisiones):

```bash
PYTHONPATH=src:tools:tests PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest \
  test_edge_session_prevalidation test_edge_presence_evaluation \
  test_presence_synthetic_pipeline test_presence_adapter_review \
  test_presence_offline.ExtractionTests test_presence_offline.SyntheticHeadTests \
  test_sqlite_sessions_view.ViewTests test_device_panel test_csi_sqlite.DatabaseTests \
  test_session_offline.FeatureTests test_session_offline.SharedViewTests test_rx02_live_view -v
.tools/node-v22.20.0/bin/node --test tests/js/sqlite_sessions.test.mjs tests/js/device_panel.test.mjs
# Tercer contrato, con el artefacto local histórico explícito (no publicado):
.tools/node-v22.20.0/bin/node tests/js/replay_demo.test.mjs RUTA_LOCAL_AL_ARTEFACTO/index.html
```

[Evidencia agregada y hashes de esta entrega](../results/PR2_PREVALIDACION_OFFLINE_20261114.json).
