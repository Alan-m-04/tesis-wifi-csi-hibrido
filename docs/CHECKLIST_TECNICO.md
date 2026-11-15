# Checklist técnico — corte offline del 14 de noviembre de 2026

Rama conservada: `feat/demo-offline-operacion-20261109`; inicio `c518d07`.
Este corte consolida la evidencia de SQLite y la preparación sintética de
Edge AI. Los cambios previos de DEVREP/R5 se conservan fuera de los commits
de esta entrega. No sustituye el anteproyecto: presencia es el primer hito.

| Estado | Comprobación | Evidencia y límite |
| --- | --- | --- |
| [x] | Piloto SQLite disponible y coherente con sus fuentes | `tools/base_datos_csi.py verify`: `verified`, `integrity_check=ok`, sin errores de FK. Solo lectura; no se reimportó. |
| [x] | Indicadores SQLite ↔ CSV | [Evidencia JSON](../results/VERIFICACION_TABLERO_20261114.json): 1.192 muestras; 240,005564743 s apertura→cierre; 4,9792637522332885 Hz; 614,782902 ms de hueco host máximo. Trece campos/estados contrastados. |
| [x] | Calidad histórica separada de integridad/replay/cierre | Rechazo estricto por preámbulo conservado: `format:RX-02` ×20 y `preamble_anomaly:RX-02` ×1; otras cuatro validaciones conformes. No habilita un detector. |
| [x] | Consultar el tablero no modifica la base | Tres GET de API con el handler real sobre streams: SHA-256, tamaño, mtime y conjunto de archivos vecinos iguales; CSV idéntico. SQLite `mode=ro`, `query_only=ON`. |
| [x] | Rutas y presentación contractual de `/sessions` | Cuatro rutas HTTP 200 en memoria; 60 pruebas Python y tres contratos Node del tablero/replay. QA adicional con JSON real en DOM simulado. Comprobados valores, aviso y motivos separados, estados vacíos/error, vencimiento y consultas manuales; sin navegador real. |
| [x] | Intento de arrancar el servidor local registrado | Comando normal `--sin-replay`; bind rechazado con `EPERM`. [Informe](../results/AVANCE_OFFLINE_20261114.md). No se cambió el enlace exclusivo a localhost. |
| [x] | Revisión visual del piloto RX02-DIAG-VISOR-240S-R1 en `/sessions` | Captura local del operador del 14/11/2026 revisada: identidad, cuatro indicadores, rechazo por preámbulo, integridad, replay y cierre legibles y coincidentes. Evidencia y SHA-256 al final de este checklist. Revisión estática del piloto; no acredita disponibilidad continua del servidor, interacción o diseño adaptable. |
| [x] | Lectura de sesiones etiquetadas y extracción para Edge AI | [Flujo y comandos](EVALUACION_EDGE_AI_OFFLINE.md): CSI inventado → parser/referencias/decodificador existentes → LLTF52 por ventana. Sin relleno o remuestreo. |
| [x] | Separación de entrenamiento/evaluación por conexión | Dos grupos sintéticos de entrenamiento, tres de evaluación; E y S completas juntas. IDs/bundles duplicados y grupos cruzados bloqueados. No se selecciona modelo con evaluación. |
| [x] | Baseline sencillo y reporte sintético reproducible | [Reporte](../results/EDGE_AI_SINTETICO_20261114.md) y [JSON](../results/EDGE_AI_SINTETICO_20261114.json): `PresenceSpecialistPort` existente, RuView fijado/MIT; matriz 2×3, FP/FN, cobertura, abstenciones y detalle por sesión. |
| [x] | Abstenciones y rechazo de entrenamiento incompleto | 42 pruebas de presencia/evaluación, once nuevas; máscaras incompletas, modelo no separable, hashes alterados, particiones y permisos probados. Valores conocidos verifican fórmulas. |
| [ ] | Contrato y adaptador aceptado para uso real del modelo | Los contratos actuales exigen `training=false` y no permiten evaluación. Revisar prospectivamente el contrato, su auditor y el ámbito; no editar planes históricos o saltarse barreras. Comando futuro documentado, ruta real aceptada aún no validada. |
| [ ] | Capturas reales etiquetadas y aceptadas para desarrollar/evaluar | Pendientes de protocolo, condiciones, permisos y adquisición futura autorizada. Piloto diagnóstico sin etiquetas; C01/C03 exploratorias y C02 rechazada no se promueven. Separar también boot/día/montajes correlacionados. |
| [ ] | Ensayo humano R5-N01 con las ESP desconectadas | Sigue pendiente: teclado, sonidos, salida/regreso y audibilidad humana. Las pruebas de software previas no lo reemplazan. [Guía vigente](GUIA_DEVREP_R5_N01.md). No se ejecutó ni simuló como completado. |
| [ ] | Calibración y evaluación física independiente | No ejecutadas. Fijar método, grupos, ámbito, tamaño muestral y criterios antes de consultar evaluación. Un modelo sintético no se transfiere a datos reales. |
| [ ] | Validación en una MIPYME | Pendiente: sitio, montaje, condiciones, operadores, ética/consentimiento aplicable, continuidad, desempeño y límites operativos. No se afirma presencia validada o utilidad comercial. |
| [x] | Originales, rechazos y cambios previos conservados | [Inventario de preservación](../results/PRESERVACION_OFFLINE_20261114.json): comparación SHA-256 de originales locales accesibles y de los 69 archivos inicialmente modificados/no versionados. |
| [x] | C04–C06 continúan reservadas | No se abrieron sus contenidos; se excluyeron de recorridos de inventario y se rechazan en rutas/IDs del nuevo CLI. No se consumió la reserva ni autorización física. |
| [x] | Trabajo sin hardware ni dependencias nuevas | No se abrió UART, ejecutó preflight físico, capturó o flasheó. No se cambió firmware, parámetros, criterios o autorizaciones. Sin instalación o descarga. |

## Comandos de revisión

Desde `la raíz del repositorio`, siempre con las ESP desconectadas:

```bash
# Para el operador, fuera del entorno que bloquea sockets:
.venv/bin/python -B tools/panel_dispositivos.py --sin-replay
# Abrir http://127.0.0.1:8766/sessions ; Ctrl-C cierra el servicio.

# Verificar SQLite y CSV sin servidor ni adquisición (salida nueva):
.venv/bin/python -B tools/verificar_tablero_sqlite.py \
  --output-new results/local/verificacion-tablero-NUEVA
.venv/bin/python -B tools/base_datos_csi.py verify

# Flujo completo de integración sintética (salida nueva):
.venv/bin/python -B tools/evaluar_edge_ai.py synthetic \
  --output-new results/local/edge-ai-synthetic-NUEVA

# Regresión relacionada, con PYTHONPATH también heredable por los subprocesos:
PYTHONPATH=src:tools:tests PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest \
  test_sqlite_sessions_view test_device_panel test_csi_sqlite \
  test_session_offline test_rx02_live_view test_presence_synthetic_pipeline \
  test_presence_adapter_review test_presence_offline test_edge_presence_evaluation -v
.tools/node-v22.20.0/bin/node --test tests/js/sqlite_sessions.test.mjs \
  tests/js/device_panel.test.mjs tests/js/replay_demo.test.mjs
```

Resultado final: **102 pruebas Python y tres contratos Node aprobados**, sin
fallos ni omisiones. Solo se ejecutó la regresión relacionada, no toda la suite
del repositorio. Bubblewrap no pudo crear namespaces; se usó ejecución directa
restringida y barrera Python de UART/reserva, sin atribuirle aislamiento de
Bubblewrap. Logs locales en `results/local/avance-offline-20261114-r1/`.

La revisión visual estática de este piloto queda completada mediante la captura
local documentada al final. El siguiente paso humano sigue siendo completar
la práctica R5-N01 sin ESP. Después corresponde revisar el contrato
prospectivo de datos etiquetados y la campaña válida; capturar requerirá una
instrucción física nueva. No se inicia esa campaña en este corte.

## Continuación publicable del PR #2

- [x] Anexo G aclarado: fechas referenciales de 2026 y estimaciones acumuladas
  10/15/20/25/35/40/50/55 %, con plazo final 13/11/2026; separado de fechas reales.
- [x] Cambios publicables de `9f73b69`/`eaf6713` incorporados sobre la base ya
  existente. Inventarios detallados y rutas personales retirados de los agregados
  publicados; datos y documentos privados permanecen locales.
- [x] [Prevalidación offline de una sesión](PREVALIDACION_CAPTURA_REAL_OFFLINE.md):
  auditor nativo, etiquetas, elegibilidad, cierre y características, con motivos
  exactos de rechazo y sin ajuste de un modelo. Dependencias R5 verificadas.
- [x] Un caso R5 nativo sintético apto y otro rechazado por preámbulo conservan
  hashes y producen reportes por CLI. Ocho pruebas nuevas; regresión publicable
  de 102 pruebas Python aprobada, sin omisiones, y tres contratos Node aprobados.
  El contrato replay usó un artefacto local histórico explícito; no se publica.
- [ ] Primera captura real válida procesada: no disponible en esta entrega.
- [ ] Modelo evaluado con varias sesiones independientes: no realizado.
- [x] Revisión visual estática del piloto SQLite en Ubuntu: captura local del
  operador contrastada; los indicadores y estados solicitados coinciden. La
  comprobación HTTP automatizada anterior sigue siendo en memoria.
- [ ] Práctica humana guiada R5-N01: pendiente; la captura del tablero no la verifica.
- [ ] Capturas reales etiquetadas y validación en una MIPYME: pendientes.

[Evidencia de esta continuación](../results/PR2_PREVALIDACION_OFFLINE_20261114.json).
Los 102 tests del corte anterior son evidencia histórica; la selección de 102
de esta continuación verifica software publicable y ocho casos nuevos sin
exigir los datasets privados que aquella selección consultaba en solo lectura.

## Revisión visual del piloto — evidencia local del 14/11/2026

Se abrió y revisó la imagen original aportada por el operador,
`Screenshot From 2026-11-14 21-27-25.png`, conservada únicamente en su carpeta
local de capturas. La imagen no se copia ni se sube al repositorio.
Tamaño: **267.878 bytes**. SHA-256 del original:

```text
524952c7ba80c8655238d879f8aeb15371108d9f6e11b49bb41c2a3579e93588
```

| Elemento visible | Comprobación en la captura |
| --- | --- |
| Sesión / receptor | `RX02-DIAG-VISOR-240S-R1 · RX-02` |
| Muestras CSI | `1192`, equivalentes a 1.192 muestras |
| Duración apertura → cierre | `240,005564743` s |
| Cadencia host | `4,9792637522332885` Hz |
| Hueco máximo host | `614,782902` ms |
| Calidad estricta | Aviso «CALIDAD ESTRICTA RECHAZADA POR PREÁMBULO» y estado «RECHAZADA · PREÁMBULO» |
| Motivos originales | `format:RX-02` ×20 y `preamble_anomaly:RX-02` ×1 |
| Integridad | «verificada» |
| Replay | «verificado» |
| Cierre | «confirmado» |
| Diagnóstico | «conforme», separado del rechazo estricto |
| Contraste CSV visible | La página indica que los indicadores y la calidad coinciden con su CSV |

Los cuatro indicadores se contrastaron también con el CSV agregado versionado.
La hora de consulta visible es `2026-11-15T02:27:08.293325+00:00`, equivalente
al 14/11/2026 a las 21:27:08 en UTC−05:00; no es la fecha de adquisición CSI.
El archivo identifica la captura de pantalla del 14/11/2026 a las 21:27:25.
La barra de URL no aparece en la imagen: la vista se identifica por su contenido
y por el contexto aportado por el operador.

**Revisión visual de este piloto completada.** La fila, el aviso y los estados
solicitados son legibles y coinciden. Se registra lo visible en esta captura
estática; no se ensayaron botones, navegación, otros tamaños de ventana o
funcionamiento continuo. Se conserva como antecedente el fallo de socket/Firefox
del entorno del agente y la comprobación HTTP en memoria; no se convierte
ese antecedente en una prueba nueva de servidor o navegador automatizado.

La sesión conserva su rechazo por preámbulo y su carácter diagnóstico. No se
promueve a captura válida para un modelo. **El ensayo guiado humano R5-N01
sigue pendiente**. Sin UART, adquisición, entrenamiento, cambios en SQLite o
acceso a C04–C06 durante esta revisión.
