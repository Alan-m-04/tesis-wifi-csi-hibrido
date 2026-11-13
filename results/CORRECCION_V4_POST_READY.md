# Corrección optativa v4 y preservación del intento rechazado

El 1 de noviembre de 2026 se retomó `feat/backend-uart-presencia-v4`, con HEAD
`15b75cd6ec6ad125204cf92d93e27f531cbee49b` y seguimiento de la misma rama remota.
Había cambios en README/estado y tres archivos nuevos: diagnóstico, parche y
pruebas de propuesta. El diagnóstico estaba terminado; la corrección solo
estaba probada en copia temporal. Se repitieron sus 176 pruebas (14,856 s,
cero omisiones) y se registró ese trabajo antes de integrar la política.

Se confirmaron directamente en el bundle original los bytes y eventos del
[diagnóstico existente](DIAGNOSTICO_V4_POST_READY.md): RX-02, línea 92, evento
183, rango `[4624, 4669)`, 45 bytes:

```python
b'I (545) main_task: Returned from app_main()\r\n'
```

SHA-256: `82ba255a7ab0a2cb2f27dccb58898e4b7798e1c4e877722ebc8b2e7ce329522d`.
La operación 105 contiene el final de READY y todo el retorno; comienza la
lectura en `31403325310735 ns`, retorna en `31403325373907 ns` y procesa ambas
líneas y la suspensión en `31403327961087 ns`: 610,561043 ms después de `begin`.
Los offsets, lecturas y tiempos completos permanecen en el diagnóstico.
Los 9 ms entre los números impresos por el dispositivo no miden un intervalo
de llegada host. No hay CSI ni slots; RX-01 termina con una cola `I` de un byte.

Las fuentes de RX-02 retornan después de READY y el SDK local ESP-IDF v5.4
imprime el mensaje al retornar `app_main()` antes de borrar la tarea principal.
Se contrastaron otra vez los hashes de las tres fuentes inspeccionadas con el
forense previo. Es compatible con fin normal de inicialización; no atesta el
binario instalado ni identifica la causa eléctrica del arranque anterior.
La gramática compartida clasifica esa línea como `info`; la regla v4 histórica
suspende cualquier `info` posterior a READY. Su decisión original era conforme
a ese contrato y permanece rechazada.

La [política explícita](../docs/POLITICA_LINEAS_V4_APP_MAIN_RETURN_V1.md)
se integra en el reductor v4 y en el journal/auditor:

- `line_policy_revision=v4-app-main-return-1` selecciona la excepción. Sin el
  campo, o con `v4-strict-post-ready-1`, sigue vigente la regla histórica.
  Revisiones desconocidas se rechazan. Las plantillas existentes se conservan.
- Solo bytes exactos de nivel I, tag `main_task`, frase completa y LF/CRLF,
  inmediatamente después del primer READY del mismo RX, antes de cualquier
  CSI y disponibilidad inicial, antes de `begin + 10 s`, sin suspensión o cierre.
  No se admiten ANSI, texto añadido ni otras frases/logs. Una vez como máximo
  por RX; no acredita disponibilidad ni sustituye las tres filas frescas.
- Se conservan clasificación `info`, bytes y metadatos. El evento registra
  patrón y revisión aplicada. La revisión efectiva queda en procedencia y, con
  la excepción nueva, en el resumen. El auditor exige concordancia con el plan;
  la ausencia histórica siempre selecciona la regla estricta. No hay migración
  retrospectiva ni comparación del bundle antiguo con resultados recalculados
  bajo la regla nueva.

Los resets, errores, READY conflictivo/duplicado, perfil CSI, discontinuidades,
silencio, colas y cierres conservan sus comprobaciones. La conexión original
mantiene además los residuos iniciales y la cola; esta corrección no la vuelve
conforme. En RX-01 las fuentes sitúan `wifi_csi_init()` después de READY: otra
línea interpuesta continúa suspendiendo. No se amplía la gramática para ella.

Las [25 pruebas de la política](../tests/test_v4_line_policy.py) incluyen todos
los cortes de byte de READY+retorno en ambos RX, lectura byte a byte, LF/CRLF,
conservación de offsets/hash, tres filas obligatorias, ausencia de READY/CSI,
timeout y frontera exacta de 10 s; duplicados, interposición, CSI previo,
disponibilidad/suspensión/cierre previos, ANSI y variantes malformadas;
reset/error/perfil después de admitir el retorno, reinicio del contador CSI,
líneas excesivas y cola sin LF. Incluyen bundles sintéticos con las dos
revisiones, metadatos manipulados y rehasheados, adaptador UART sobre PTY
propios y lectura inmutable del intento físico existente. Las entradas para
la excepción son exclusivamente sintéticas; no hay calibración física.

Pasaron **188 pruebas, cero fallos, errores u omisiones, en 14,154 s**:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python -B -m unittest \
  test_uart_v4 test_persistent_presence_v4 test_availability_window \
  test_controlled_v2 test_controlled_v3 test_capture_preparation \
  test_capture_boundaries test_boundary_diagnostic test_v4_line_policy -v
```

La suite conserva pruebas de memoria, serial dobles y PTY de los protocolos
previos. No se repitieron pruebas de modelos, gráficos o compilación de firmware,
que no cambian. `./tools/offline_sandbox.sh /usr/bin/true` retorna 1 por falta
de permisos para crear namespaces; no se cambió el wrapper ni se atribuye
aislamiento Bubblewrap a unittest ejecutado directamente en el entorno restringido.

Artefactos de esta reanudación, separados del intento:
`results/local/correccion-v4-post-ready-20261101/`. Contiene copia del trabajo
pendiente al retomar, logs, auditoría original reproducida, comprobación de
fuentes y manifiestos de preservación. Se verifican **2335 archivos previos**
intactos por tamaño y SHA-256, con datos, resultados locales anteriores,
firmware fuente y protocolos históricos. No se sobreescribieron registros ni
la autorización consumida. La auditoría conserva `integrity_ok=true`,
`replay_ok=true`, `fatal=post_ready_info:RX-02`, cero ventanas y ambos cierres
confirmados. El resumen [versionado de verificación](CORRECCION_V4_POST_READY.validacion.json)
recoge los hashes y resultados relevantes.

Antes de preparar otro intento quedan la revisión separada de los motivos
iniciales de formato (sin aceptar logs genéricamente), el efecto del orden de
inicialización distinto en RX-01 y un plan nuevo que seleccione explícitamente
la política. READY y flujo real de ambos RX, cobertura y etiquetas elegibles
siguen sin demostrar. PRUEBA02 sigue siendo declaración humana de audibilidad;
PRUEBA01 conserva su incertidumbre. Ningún dato nuevo permite validar montaje,
binarios instalados o audibilidad. Se requiere autorización nueva para toda
adquisición física; en esta sesión no se preparó ni ejecutó otro intento.
No hubo UART, captura, reset, reconexión, firmware o calibración del detector.
