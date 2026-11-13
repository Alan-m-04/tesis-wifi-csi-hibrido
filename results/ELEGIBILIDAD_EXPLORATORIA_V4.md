# Elegibilidad exploratoria v4, revisión 1

Desde `1f974b0633e2c6d4e4d96bb2cb67f0c06ca09f90`, rama
`feat/backend-uart-presencia-v4`, limpia y coincidente con origin al comenzar.
El [contrato nuevo](../docs/ELEGIBILIDAD_EXPLORATORIA_V4_R1.md) se definió antes
de implementar. Esta revisión explícita resuelve el bloqueo del piloto
**exploratorio** separando su elegibilidad de la conformidad de conexión. No
cambia el criterio histórico de aceptación ni la interpretación de capturas antiguas.

El resultado es **listo para revisión del plan nuevo E/S, sin ejecución física**.
Faltan declaraciones actuales de ambiente/montaje/actor/audibilidad y autorización
nueva antes de adquirir. No se afirma una campaña física válida, calibración,
entrenamiento o presencia detectada.

## Comportamiento y límites

Selección: `eligibility_revision=v4-exploratory-1` y
`line_policy_revision=v4-startup-sequence-1`. Ausencia de revisión de elegibilidad
conserva `v4-connection-strict-1`; revisiones desconocidas o combinaciones distintas
se rechazan. El journal usa una fábrica explícita; el constructor histórico
rechaza planes exploratorios para evitar saltarse el reductor nuevo.

- **Conexión completa:** conserva motivos y estado estricto. Bytes no UTF-8,
  otros formatos iniciales o texto de arranque no interpretado mantienen su rechazo.
  `windows[].eligible` conserva el criterio estricto anterior.
- **Preámbulo:** prefijos [0, fin) por RX, hashes SHA-256 y referencias de todas
  sus líneas/lecturas, sellados al alcanzar disponibilidad. Las anomalías se
  marcan `anomalous_uninterpreted`; no se convierten en CSI ni se eliminan. Un
  error posterior no cambia retrospectivamente el estado del preámbulo sellado.
- **Ventanas:** T0/T1 y evidencia original se conservan. La cobertura exploratoria
  excluye chunks ya recibidos al fijar T0 y filas procesadas después de T1;
  exige los mismos mínimos de filas/bins/gaps sobre el conjunto conservador.
- **Elegibilidad exploratoria:** el resumen solo produce candidatas pendientes.
  El auditor emite un resultado separado con integridad/replay, identidad,
  almacenamiento, calidad, cobertura, etiqueta y cierres. No promueve una
  candidata que carezca de alguna prueba obligatoria.

La disponibilidad inicial añade una barrera global al completar ambos retornos
de `app_main()`: vacía ambas rachas y exige tres filas válidas/frescas por RX de
lecturas nuevas, iniciadas después de esa barrera. Los chunks que contienen el
último retorno no acreditan filas nuevas, aunque su texto aparezca después del
retorno. No se declara disponibilidad/gate con una línea pendiente. Los 10 s,
demoras, ventanas de 30 s, frescura y perfil CSI permanecen fijos.

La incertidumbre de una anomalía abarca desde su primera lectura hasta el máximo
de retorno y procesamiento. Una cola tiene extremo superior desconocido. Solo
se demuestra exclusión de [T0,T1) con `fin < T0` o `inicio >= T1`. Tocar T0,
cruzar fronteras, publicación tardía o no poder localizarla fuera impiden
elegibilidad. Un reset, error, discontinuidad, pérdida de disponibilidad o fallo
de operación sigue suspendiendo sin rearmado; una suspensión revoca todas las
candidatas de la conexión, incluso si una ventana había terminado.

No hay whitelist de texto genérico. Las únicas excepciones posteriores a READY
siguen siendo las dos frases exactas de la política revisada, con su orden por
RX. No se modifican `availability_window.py`, perfil CSI, firmware o las políticas
de línea anteriores. Los tiempos son del host; no acreditan llegada RF, latencia
del buffer o ausencia de transitorios/reset eléctrico.

Para la revisión nueva el backend registra la identidad verificada y huella del
fd al abrir, la observación inicial de espacio libre y los checks de presupuesto
durante operación y antes de finalizar. El auditor compara bindings y procedencia,
exige nodos distintos y el presupuesto fijo, coteja bytes con el replay, exige
check final y comprueba tamaño real del bundle. Estas pruebas no se inventan
para bundles antiguos. El replay verifica coherencia de registros; no es una
firma de origen ni una medición independiente de disco/dispositivos físicos.
Se mantiene la limitación del guard ante bloqueos o consumo concurrente de disco.

## Verificación exclusivamente offline

**234 pruebas aprobadas**, cero fallos, errores u omisiones, **23,571 s**: las
210 anteriores más [24 nuevas](../tests/test_v4_exploratory.py).

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python -B -m unittest \
  test_uart_v4 test_persistent_presence_v4 test_availability_window \
  test_controlled_v2 test_controlled_v3 test_capture_preparation \
  test_capture_boundaries test_boundary_diagnostic test_v4_line_policy \
  test_v4_startup_sequence test_v4_exploratory -v
```

Las nuevas pruebas cubren prefijo anómalo y ventanas futuras candidatas, barrera
global/filas nuevas, exclusión por bytes/índices de las filas del gate, líneas
pendientes, contacto/cruce de fronteras e intervalos desconocidos, procesamiento
tardío, errores/resets/texto genérico/CSI incorrecto/discontinuidades, silencio,
etiqueta incierta, cobertura insuficiente, almacenamiento y cierre no confirmado.
Se prueba manipulación rehasheada del preámbulo, offsets/hashes, tiempos/eventos,
procedencia, identidades y espacio inicial; una candidata sin pruebas del
transporte no se certifica. El CLI rechaza aplicar esta revisión a un plan histórico.

Se guardó además un arnés reproducible con pySerial sobre **PTY propios**, reloj
escalonado y bytes sintéticos, separado de cualquier captura física:
`results/local/elegibilidad-exploratoria-v4-20261101/synthetic-ES-final/`.
Su auditoría confirma integridad/replay e identidad/almacenamiento **del arnés**:

| Resultado sintético | Valor |
|---|---|
| Conexión completa | Rechazada: formato y preámbulo anómalo por RX. |
| Preámbulo | Íntegro, trazable, anómalo/no interpretado. |
| Ventanas E/S | Dos ventanas completas y declaradas en el arnés. |
| Elegibilidad estricta anterior | Falsa en ambas ventanas. |
| Elegibilidad exploratoria sintética | Verdadera en ambas, solo tras auditoría. |
| Calibración / entrenamiento / producción | No autorizados por esta revisión. |

La evidencia sintética no verifica identidades USB reales, audibilidad humana,
montaje, firmware instalado o desempeño del detector. No se usaron registros
físicos para calibrar, entrenar o fabricar ventanas elegibles bajo la revisión nueva.

El [auditor offline nuevo](../tools/auditar_exploratorio_v4.py) muestra los cuatro
resultados separados y puede guardar la auditoría completa sin sobrescribir:

```bash
.venv/bin/python -B tools/auditar_exploratorio_v4.py \
  --bundle results/local/elegibilidad-exploratoria-v4-20261101/synthetic-ES-final
```

Bubblewrap vuelve a fallar con código 1 al crear namespaces. Las pruebas directas
no acreditan su aislamiento; el wrapper conserva su fallo explícito.

## Preservación y plan para revisión

Se comprobaron **2370 archivos anteriores intactos** por tamaño y SHA-256:
datos, resultados locales, fuentes firmware, protocolos, políticas y plantillas,
incluidas las autorizaciones consumidas. Los informes versionados anteriores
permanecen sin modificar. El replay del v4 original se ejecuta con su política
histórica y conserva `post_ready_info:RX-02`, cero slots, integridad/replay y ambos
cierres confirmados; no se lo convierte a la revisión nueva ni se cambia su aceptación.

El [plan nuevo E/S](../config/piloto_exploratorio_v4_ES_r1.review.json) y su
[procedimiento de revisión](../docs/PLAN_PILOTO_EXPLORATORIO_V4_ES_R1.md) fijan una
conexión/grupo y dos slots `EXP02-E`, `EXP02-S`, con ambas revisiones explícitas.
Se prepararon después de pasar las verificaciones, sin ejecutar preflight o UART.
La preparación devuelve `PREPARED_NOT_EXECUTED`; la validación para ejecución
rechaza las declaraciones `PENDIENTE`. No se creó ni renovó una autorización.

[Resumen versionado de verificación](ELEGIBILIDAD_EXPLORATORIA_V4.validacion.json).
Los logs completos, auditorías sintéticas y manifiestos de preservación permanecen
en la carpeta local de esta revisión. No hubo UART, nuevas capturas físicas,
reset, reconexión, cambio de firmware, calibración o entrenamiento.
