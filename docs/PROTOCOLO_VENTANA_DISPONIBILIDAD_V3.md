# controlled_dual_v3: disponibilidad y ventana prospectiva

Implementación offline del diseño revisado, basada en `a3f10ea2bed354cebd1b3354f1fb30a69a646a2e`. v1/v2 conservan su significado y sus resultados. Los parámetros siguientes quedan fijados antes de implementar y ensayar; son operativos, no estabilidad validada.

## Definición previa de caída de flujo y cuatro dimensiones

**Caída de flujo** significa terminación prematura de un lector (normal inesperada, excepción UART, desconexión o aborto) antes de T1. Rechaza una ventana iniciada. Un silencio finito no prueba desconexión: no se define un umbral temporal de silencio para rechazar. `max_gap_ns = null` es una decisión explícita y versionada. La frescura de 1 s pertenece exclusivamente a disponibilidad antes del disparo; no se reutiliza como umbral durante la ventana.

- **Integridad/formato:** bytes/CSV/ledgers/hashes/identidades, gramática, perfil y continuidad local; cualquier error que intersecte la ventana o no pueda localizarse fuera la rechaza. Huecos de callback no se llaman pérdida RF.
- **Disponibilidad:** READY estricto, tres filas consecutivas por RX, frescura host de 1 s, máximo fijo de 10 s desde antes de la primera apertura; decisión única y prospectiva. Los eventos tardíos no retroceden T0.
- **Cobertura temporal:** mínimo una fila íntegramente incluida por RX. Se informan primera/última, número de filas, huecos interiores y de borde y máximo hueco, sin interpolar. No hay tasa mínima, uniformidad exigida ni umbral máximo de hueco. Una ventana con muy pocas filas puede cumplir este contrato mínimo y deberá mostrarlo explícitamente.
- **Idoneidad para campañas/modelos:** no evaluada y nunca aprobada por v3. Exige otro contrato prospectivo con mínimos de cobertura/tasa, etiquetas, geometría, sesiones independientes y evaluación apropiada. No se entrenan modelos.

## Contrato fijo

READY completo UTF-8/LF con tag y RX correctos, canal 11 HT20 UART0=115200 y fuente esperada; tres filas válidas consecutivas posteriores, callback +1, reloj uint32 progresivo según la regla existente y descartes constantes. Cabecera exacta y líneas vacías son neutrales. Residuos reinician racha y rechazan conexión completa. Reset/error/READY duplicado después de READY es fatal, sin rearmar. A se toma inmediatamente antes de primera apertura; D=A+10 s, sin reinicio al abrir RX-02. La primera decisión válida antes de D fija T0 real y T1=T0+30 s una sola vez.

Se publica cada chunk íntegro como lote antes de evaluar disponibilidad. Se conservan tiempos de lectura y procesamiento separados; un error/reset del mismo chunk que la tercera fila impide activación. Un evento tardío que demuestra incoherencia previa a T0 rechaza la activación; T0/T1 permanecen inmutables.

Se conserva una conexión completa desde cada apertura. La ventana [T0,T1) incluye solo filas válidas con inicio de primera lectura s >= T0 y retorno LF e < T1. Prefijos anteriores, LF exactamente en T1 y filas tardías quedan excluidos con referencia, sin recortar brutos. Errores cuya evidencia [s,e] intersecta la ventana, o cuya exclusión no puede demostrarse, causan rechazo.

Parada: solo completar línea pendiente hasta LF, como v2, con máximo 250 ms y 65536 bytes por RX desde T1 (desde D si timeout sin ventana). Aborto/fallo elude espera. Se preserva todo chunk, fragmento, tiempo y error; lectores reunidos antes de cierre de ambos. Parada no conforme, pérdida de trazabilidad, identidad o cierre fallido impiden aprobar ventana.

`connection_full` y `experimental_window` son resultados simultáneos y visibles. Una ventana conforme nunca aprueba la conexión completa. No se crea ventana retrospectiva sobre v1/v2. El comando de preparación no abre UART. Una ejecución física requiere nueva autorización explícita y ambiente actual.

## Coordinación y evidencia que se guarda

`availability_window.py` encuadra LF con memoria de parsing acotada, clasifica UTF-8/READY/perfil y conserva referencias de primera/última lectura, SHA-256 y offsets de todas las líneas. Los brutos nunca se sustituyen por ese prefijo de parsing. Un lock común protege lotes, estados y la decisión; no se evalúa entre las líneas de un chunk ya publicado. El lector publica después de persistir bruto, ledger y CSV. No hay una cola de muestras que pueda usarse para escoger un comienzo anterior.

`availability.events.jsonl` registra activación del lector, cada chunk con referencia al ledger/hash, líneas y validación, fin de lote, expiración de racha, disparo o timeout, conflictos, errores y final de lectores. `processed_ns` es distinto de `started_ns`/`returned_ns`. A/D y T0/T1 se conservan en la sesión. El evento `armed` cita los READY y las seis filas usadas. Un error de un chunk cuyo retorno ya ocurrió puede seguir pendiente de publicación por planificación o escritura: si contradice una activación ya hecha se registra `activation_inconsistent`, se rechaza y se conserva el mismo T0. No se promete conocer instantáneamente bytes todavía no procesados.

La caducidad de una racha se comprueba al procesar nueva evidencia y antes de decidir. Una fila que revela discontinuidad no cuenta para la nueva racha. Reset/error reconocido después de READY y callback reiniciado son fatales; texto informativo distinto de cabecera/vacío interrumpe la racha, aunque no sea corrupción por sí mismo. Una excepción de almacenamiento o trazabilidad impide aprobar.

`audit_availability.py` vuelve a recorrer brutos y ledgers y contrasta gramática, referencias, orden de lotes, frescura, rachas, evidencia del disparo, tiempos, abortos y cierre. No se limita a aceptar los booleanos registrados. Guarda ambos resultados, cobertura y un índice por línea/fragmento. `window-index.json` es una referencia derivada y fijada por el manifiesto de bundle; no es un recorte ni un segundo bruto.

Los motivos de inclusión son `preamble`, `crosses_start`, `crosses_both_boundaries`, `included`, `at_or_after_deadline`, `invalid_in_window`, `window_not_started` e `incomplete_fragment`. Solo `included` cuenta como fila experimental. Los errores se evalúan por su intersección temporal incluso cuando esa línea no tiene fila CSV. Las cabeceras y READY tampoco son muestras.

La integridad registrada se informa por separado de parada y requisitos compartidos; puede pasar con una cola preservada cuya parada rechaza el intento. `connection_full` puede ser conforme con formato/cierre correctos aunque falle la cobertura de ventana; la calidad global exige conformidad de ambos. Una conexión rechazada con ventana conforme mantiene rechazo global. El estado de timeout es `no_iniciada`, nunca una ventana ficticia vacía de 30 s.

| Evidencia | Efecto en conexión completa | Efecto en ventana |
|---|---|---|
| Residuo inicial, demostrado antes de T0 | Rechazo de formato | No contamina por sí solo la ventana; rechazo completo visible |
| Error/residuo/continuidad incorrecta que intersecta [T0,T1) | Rechazo | Rechazo, incluso si no existe fila CSV |
| READY ausente o frescura insuficiente hasta D | Disponibilidad fallida | No iniciada; no hay reintento |
| READY conflictivo/duplicado, reset o error después del READY aceptado | Aborto/rechazo | Sin disparo si aún no existía; rechazo si estaba iniciada |
| Error recibido antes de T0, procesado tarde e incompatible con su evidencia | Rechazo | Activación inconsistente; se conservan T0/T1, sin sustitución |
| Silencio finito con lector activo | Se informa cobertura | Sin umbral de silencio; al menos una fila incluida por RX |
| Terminación real de lector antes de T1, aunque su notificación sea tardía | Aborto/error | Caída de flujo; ventana incompleta/rechazada |
| Fila válida que cruza frontera o termina en/después de T1 | Conservada | Excluida con causa; no extiende el intervalo |
| Error enteramente posterior a T1 | Rechazo correspondiente | No contamina por sí solo sus datos; siguen vigentes requisitos compartidos |
| Límite de parada agotado, cola, identidad/cierre/ledger/almacenamiento fallidos | Rechazo/error | No aprobable por requisito compartido |

Los huecos de cobertura se calculan con retornos LF host: diferencias consecutivas y bordes T0/primera y última/T1. Filas del mismo chunk pueden compartir timestamp y producir huecos cero; no se interpolan tiempos RF. Los campos de cobertura no convierten duración nominal en observación continua.

La comprobación heredada de reloj **local** también queda explícita: entre filas válidas, `delta=(actual-anterior) mod 2**32` debe estar entre **1 y 10 000 000 µs**, inclusive. Un delta fuera de ese rango se registra como discontinuidad según el criterio v1/v2 y rechaza el alcance afectado; no diagnostica la causa física. Esta regla ya existente no es `max_gap_ns` del host ni valida una cadencia RF. Por tanto, ausencia de umbral de silencio host no elimina la comprobación independiente de reloj local, callbacks o descartes.

El canónico conserva todas las filas completas representables, más sus referencias e inclusión. La visualización muestra permanentemente los dos estados, conteos/cobertura y T0/T1 sobre el eje host, incluso cuando solo hay pocas filas. El detalle permite inspeccionar errores y exclusiones. Un RX sin filas no recibe matrices inventadas: muestra ausencia de datos y no invoca el consumidor oficial sobre muestras inexistentes.

## Diferencias y límites respecto de v1/v2

v1/v2 no esperan READY ni tres filas antes de fijar el inicio; v2 cuenta el retorno LF dentro de sus 30 s nominales. v3 tiene espera prospectiva fija, disparo real único, evidencia explícita, regla adicional de primera lectura y dos alcances. Se reutiliza la misma finalización acotada de v2. El auditor de parada también admite ausencia de deadline en un aborto previo al disparo; eso no aprueba la parada. Las rutas v1/v2 y sus etiquetas siguen disponibles y sus pruebas se ejecutan como regresión; no se aplican reglas v3 a capturas anteriores.

READY no atesta una época de arranque ni el binario instalado; RX-01 lo imprime antes de habilitar CSI y RX-02 después de su inicialización. La causa de los residuos iniciales existentes sigue indeterminada. No se limpia entrada, pulsa reset, cambia firmware, alinea relojes RX, estima tiempo RF, interpola, rellena matrices ni recupera filas después de cerrar. Frescura/racha/plazo son parámetros operativos. El host/driver/almacenamiento no ofrecen tiempo real duro: se registran retornos, parada y cierre reales; una devolución de lectura fuera del presupuesto no se recorta para aprobar.

## Comandos preparados y reproducción offline

Preparar y revisar el contrato **sin abrir UART**, con ambiente aún sin completar y sin autorización creada:

```sh
.venv/bin/python -B tools/captura_dual_controlada.py \
  --plan config/captura_dual_v3_30s.template.json
```

El resultado esperado es `PREPARED_NOT_EXECUTED`. No se ejecuta `--preflight-only` en este cambio porque la validación es exclusivamente offline. Una futura ejecución física necesita otro plan local nuevo, ambiente actual, revisión de ambas identidades y una autorización explícita nueva; no hay autorización vigente ni un intento físico v3.

Pruebas en Bubblewrap con red aislada y `/dev` privado (PTY sintéticos):

```sh
./tools/test_offline.sh results/local/visualizacion-csi-entrega/canonical.json
.venv/bin/python -B tools/ensayar_controlled_v3.py \
  --output-new results/local/ensayo-v3-NUEVO
```

La suite cubre memoria/PTY y regresión histórica offline. Los ensayos persistidos incluyen una ventana sintética de 30 s con terminación tardía, conexión rechazada/ventana conforme, error procesado tarde y timeout real de 10 s sin bytes. Las duraciones abreviadas de otros casos se inyectan solo por backend sintético, se etiquetan y registran; el plan físico mantiene 10 s/30 s fijos. No constituyen medición del enlace.

Para auditar un **ensayo sintético nuevo** y generar su visualización, conservando el directorio de salida nuevo:

```sh
.venv/bin/python -B tools/analizar_captura_controlada.py \
  --run results/local/ensayo-v3-NUEVO/connection-rejected-window-conforming \
  --output-new results/local/analisis-v3-NUEVO
```

El código de salida 1 conserva el rechazo global aunque la integridad permita visualizar. Resultados reales, rutas, hashes y verificaciones de navegador se documentan en `results/VENTANA_DISPONIBILIDAD_V3.md` y su JSON de validación.
