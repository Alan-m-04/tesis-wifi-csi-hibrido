# controlled_dual_v3: implementación y validación offline

Base exacta `a3f10ea2bed354cebd1b3354f1fb30a69a646a2e`, rama `feat/ventana-disponibilidad`. Implementación en `4b4b4116c35df2a75839453d3a71500715f1b655`. **195 pruebas aprobadas: 162 Python y 33 Node; cero fallos, errores u omisiones.** Se verificaron además 12 vistas Firefox sobre los tres bundles finales. [Evidencia, hashes y resultados estructurados](VENTANA_DISPONIBILIDAD_V3.validacion.json).

Todo lo nuevo es código, documentación, memoria/PTY y auditoría de archivos. **Cero UART físicos abiertos, adquisiciones físicas, flasheos, cambios de firmware o entrenamiento. Ninguna autorización de captura vigente, creada ni consumida.** Los permisos del entorno para crear namespaces/escribir Git permitieron aislar ensayos y subir cambios; no autorizan dispositivos.

## Contrato implementado

La [definición normativa](../docs/PROTOCOLO_VENTANA_DISPONIBILIDAD_V3.md) se escribió antes del código en el mismo cambio: caída de flujo es terminación/fallo real de un lector antes de T1, incluso si se notifica tarde. Un silencio finito no demuestra desconexión; `max_gap_ns=null` deja explícito que no hay umbral máximo de silencio. La frescura de 1 s se usa antes del disparo.

| Dimensión | Resultado que informa v3 |
|---|---|
| Integridad/formato | Bytes, hashes, CSV, ledgers, offsets, identidad y perfil/continuidad; errores localizados y conservados |
| Disponibilidad | READY estricto y tres filas consecutivas por RX, frescura ≤1 s, máximo A+10 s; disparo prospectivo único |
| Cobertura temporal | Mínimo una fila plenamente incluida por RX, primera/última y todos los huecos/bordes; sin umbral de silencio ni interpolación |
| Campañas/modelos | No evaluada: cumplir disponibilidad/cobertura mínima no acredita estabilidad, frecuencia uniforme, presencia o aptitud para entrenar |

La primera decisión válida fija T0 real y T1=T0+30 s. Un lock publica chunks completos y protege la decisión; se comprueban todas las líneas conocidas del lote. Errores/reset en el mismo chunk impiden disparar; errores o paradas anteriores a T0 procesados tarde invalidan la activación sin mover T0 ni seleccionar otro intervalo. READY duplicado/conflictivo y reset/error después de READY son fatales. La disponibilidad no se rearma tras un fatal.

El control de reloj local conserva explícitamente la regla previa de v1/v2: delta uint32 entre 1 y 10 000 000 µs. Su incumplimiento rechaza por incompatibilidad con ese criterio, sin atribuir causa. Es distinto de los huecos de cobertura host, cuyo máximo permitido sigue siendo `null`; tampoco se eliminaron controles de callbacks o descartes para permitir silencios.

Una fila experimental requiere inicio de primera lectura ≥T0 y retorno LF <T1. Las fronteras, filas tardías, errores y fragmentos tienen índice trazable; ningún bruto se recorta. La parada reutiliza el lector v2: 250 ms y 65536 bytes adicionales por RX, solo si queda línea pendiente. Aborto/error no provoca drenaje indefinido. Se reúnen lectores antes de cerrar ambos puertos, también ante fallos.

Auditoría y canónico conservan `connection_full` y `experimental_window`; la calidad global exige ambos. La interfaz los muestra simultáneamente, con cobertura, fronteras, procedencia y exclusiones. Una conexión rechazada sigue visible aunque su ventana cumpla. Sin filas se muestra ausencia y no se fabrican matrices ni se aplica el consumidor oficial a muestras inexistentes. Las páginas sintéticas se identifican como tales.

## Pruebas ejecutadas y resultados

La suite completa final se ejecutó con `./tools/test_offline.sh results/local/visualizacion-csi-entrega/canonical.json`, en Bubblewrap con fuentes de solo lectura, red aislada y `/dev` privado. El log íntegro queda en `results/local/verificacion-ventana-disponibilidad/pruebas-finales-03.log`; su hash figura en el JSON. Los 38 tests Python y dos Node nuevos se añaden a la regresión existente.

Casos cubiertos en memoria y PTY: READY falso, fragmentado, ausente, de otro RX/perfil o duplicado; tres filas, interrupción/caducidad de racha, wrap uint32, continuidad y descartes; timeout exacto; múltiples filas en una lectura; prefijo previo a T0, LF en T1 y errores que cruzan fronteras; activaciones concurrentes; error/reset en el lote que completa disponibilidad; lectura anterior a T0 publicada tarde; notificación tardía de parada; aborto, error de un RX, fallo al abrir el segundo y error de cierre; colas, flujo sin LF, finalización tardía, alteración de T0 o traza aun recalculando hashes; canónico, consumidor oficial, preparación sin UART y visualización sin filas.

El generador `tools/ensayar_controlled_v3.py` dejó cuatro sesiones **sintéticas separadas**, fijadas por bundle y hashes, en `results/local/verificacion-ventana-disponibilidad/ensayo-03/`:

| Ensayo PTY | Filas completas RX-01/RX-02 | Incluidas RX-01/RX-02 | Conexión completa | Ventana |
|---|---:|---:|---|---|
| `accepted-30s` | 6 / 6 | 2 / 2 | Conforme | Conforme |
| `connection-rejected-window-conforming` | 5 / 5 | 2 / 2 | Rechazada por arranque residual | Conforme |
| `late-error` | 5 / 5 | 2 / 2 | Rechazada | Rechazada por activación inconsistente |
| `timeout-10s-no-data` | 0 / 0 | 0 / 0 | Rechazada | No iniciada |

El primero ejercitó **30 000 000 000 ns nominales**, con espera configurada de 10 s: cada RX completó una fila después de T1 con 726 bytes adicionales y parada LF; esa fila tardía se conservó y quedó excluida. El último esperó realmente el plazo de 10 s sin datos y no creó una ventana vacía. Los otros ensayos usan 0.16 s y 700 ms solo por inyección sintética registrada; nunca alteran el plan físico fijo.

El primer ensayo produce intencionadamente un hueco de aproximadamente 29.89 s al final de su ventana: **el contrato mínimo lo permite y lo muestra**. No es flujo RF ni cobertura útil demostrada para una campaña/modelo. Este caso comprueba que no se introdujo tácitamente un umbral de silencio de 1 s dentro de la ventana.

Todos los PTY quedaron cerrados, sin cierre durante lectura ni errores de productores. Las auditorías independientes coinciden y cada exportación verificó diez originales por hash. Las 12 vistas finales (dos RX × dos LTF × tres estados) verifican estados simultáneos, conteos, fase de filas, selector, cuatro gráficos, etiquetas sintéticas y ausencia de matrices en timeout. Solo el control efímero de Firefox usa TCP localhost en su red privada; no hay HTTP, UDP CSI ni acceso a UART del host.

Bundles para revisión local:

- [Conexión y ventana conformes](local/verificacion-ventana-disponibilidad/analisis-entrega-accepted/visualization/index.html).
- [Conexión rechazada y ventana conforme](local/verificacion-ventana-disponibilidad/analisis-entrega-scopes/visualization/index.html).
- [Timeout sin ventana ni filas](local/verificacion-ventana-disponibilidad/analisis-entrega-timeout/visualization/index.html).

Se conservan ensayos/logs intermedios en directorios distintos. El primer ensayo de memoria tuvo 13/14 tests aprobados: una aserción sobre la racha después de un perfil inválido y un hueco de callback se corrigió para comprobar la condición de disparo; no se relajó el protocolo ni un rechazo. Un mock de fallo de cierre repetía su error en el destructor y se cambió para inyectarlo una sola vez. La revisión añadió rechazo fatal de READY conflictivo/ROM embebido tras READY y conflicto por parada previa notificada tarde; se repitieron las comprobaciones después de esos cambios. Los resultados finales citados corresponden a los hashes de `4b4b411`.

## Preservación y límites

139 archivos previos fijados antes del cambio permanecen idénticos, incluidos intento/visualización v2, fuentes de firmware y documentos originales. La visualización v1 coincide con sus tres hashes principales publicados, nueve copias originales y snapshot de validación. Las auditorías físicas v1/v2 son **exactamente iguales** a las almacenadas:

| Registro físico conservado | Filas RX-01/RX-02 | Calidad global | Ventana v3 |
|---|---:|---|---|
| v1 posterior al reinicio | 145 / 146 | Rechazada: residuos iniciales y colas de 129 bytes | No aplicada |
| v2 físico | 147 / 147 | Rechazada: residuos iniciales | No aplicada |

No se concatenaron sesiones, cambiaron criterios históricos ni generaron ventanas retrospectivas. Las 54 fuentes fijadas en el ensayo final coinciden con el árbol probado; el JSON publica hashes de las fuentes versionadas. Los brutos, planes locales y `results/local` siguen fuera de Git.

v3 está validado solo offline: no demuestra comportamiento físico, sincronización RF, frescura RF, binario instalado, estabilidad del enlace, causa de residuos ni idoneidad estadística. READY tiene posiciones diferentes en las fuentes RX-01/RX-02; las filas posteriores aportan progreso observable, no atestación. La planificación/driver/almacenamiento no garantizan tiempo real duro; se registran tiempos reales y se rechazan retornos fuera del presupuesto sin recortar.

## Comando preparado y continuación

```sh
.venv/bin/python -B tools/captura_dual_controlada.py \
  --plan config/captura_dual_v3_30s.template.json
```

Se ejecutó solo esta preparación, con resultado `PREPARED_NOT_EXECUTED` y sin apertura de UART. Revisar ahora implementación, definición de cobertura y límites. Una adquisición física exige **otra autorización explícita**, un plan local y directorio nuevos, ambiente actual y preflight correcto de ambas identidades. No se propone convertir estos ensayos ni los registros v1/v2 en evidencia física de v3.
