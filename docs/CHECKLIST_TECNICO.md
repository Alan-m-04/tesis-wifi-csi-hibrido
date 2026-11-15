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
| [ ] | Servidor escuchando y revisión visual real de `/sessions` | Pendiente en terminal/navegador del operador. El entorno bloqueó sockets; Firefox headless terminó −11 tras `unshare(CLONE_NEWPID): EPERM`, sin captura. No se acredita render, legibilidad o diseño adaptable reales. |
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

El siguiente paso humano es revisar `/sessions` en el navegador del operador y
completar la práctica R5-N01 sin ESP. Después corresponde revisar el contrato
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
- [ ] Revisión visual conectada de SQLite en Ubuntu y práctica humana R5-N01:
  pendientes. El HTTP comprobado sigue siendo en memoria.
- [ ] Capturas reales etiquetadas y validación en una MIPYME: pendientes.

[Evidencia de esta continuación](../results/PR2_PREVALIDACION_OFFLINE_20261114.json).
Los 102 tests del corte anterior son evidencia histórica; la selección de 102
de esta continuación verifica software publicable y ocho casos nuevos sin
exigir los datasets privados que aquella selección consultaba en solo lectura.
