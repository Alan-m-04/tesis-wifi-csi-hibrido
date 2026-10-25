# controlled_dual_v2: finalización acotada y conteos nominales

Implementación en `feat/captura-dual-v2`, creada desde `39c5cc3413ca5250320a5218f14dca2723bbb612`. **Preparada y probada con memoria/PTY; sin abrir UART físicos, repetir la captura ni crear/consumir autorización.** ESP-IDF v5.4 y los firmware permanecen intactos. Evidencia: [resultados y hashes](../results/CONTROLLED_DUAL_V2.validacion.json).

## Diferencias exactas respecto de v1

| Aspecto | controlled_dual_v1 | controlled_dual_v2 |
|---|---|---|
| Selección | Plan v1 existente | Plan con `protocol=controlled_dual_v2` y `stop_policy` fija |
| Ventana nominal común | 30 s | Los mismos 30 s; nunca se extienden |
| Arranque | Lee desde cada apertura, conserva preámbulo | Igual; lector acotado acepta deadline pendiente hasta que ambos lectores estén preparados |
| Parada ordinaria | Deja de iniciar lecturas al alcanzar el deadline; una lectura en vuelo puede retornar después | Si queda línea pendiente, permite llegar al primer LF, como máximo hasta deadline + 250 ms y 65536 bytes adicionales |
| Lectura posterior al deadline | No inicia otra | Un byte por petición, únicamente para la línea pendiente; timeout limitado al tiempo restante |
| Metadatos | Ledger de lecturas no vacías y ciclo de vida global | Añade tamaño solicitado/fase al ledger, informe real de parada por RX y eventos individuales antes/después de abrir/cerrar |
| Conteos | Filas comunes descriptivas | Se explicitan preámbulo, ventana nominal y filas completadas después del deadline; cada fila canónica conserva su fase |
| Auditoría | Conservada | Aplica los mismos requisitos de formato, perfil, residuos, cola y cobertura, más validación independiente de la política y eventos v2 |
| Error de lectura | Resultado original conservado | Separa integridad de bytes/metadata registrados, calidad de filas completas y rechazo por error de adquisición |
| Manifiesto | `tesis-controlled-capture-v1`, kind v1 | `tesis-controlled-capture-v2`, kind v2; no se reinterpretan los archivos v1 |

El CLI `tools/captura_dual_controlada.py` admite ambos planes. La plantilla v1 y el plan local consumido no se cambiaron; sus archivos físicos y resultados originales tampoco. Se extrajo el procesamiento de chunks a una función común dentro del lector: conserva escritura íntegra al bruto antes de parsing, campos CSV, validación estricta, encuadre, conteo de colas y límites de memoria. La ruta v1 sigue usando su bucle temporal anterior, sin finalización acotada.

## Regla de finalización

La política está fijada en `src/controlled_protocol.py` y en [la nueva plantilla](../config/captura_dual_v2_30s.template.json):

```json
"stop_policy": {"grace_ns": 250000000, "max_completion_bytes": 65536}
```

El coordinador reutiliza `src/bounded_frame_reader.py`, probado en el diagnóstico anterior. La primera lectura puede comenzar antes de abrir el segundo RX: no se espera a la ventana nominal para conservar bytes. El getter de deadline pasa de null a un único valor fijo; quitarlo o cambiarlo después es un error. Cuando ambos lectores están preparados, se fija `common_deadline_ns = common_start_ns + 30000000000` para ejecución física.

Al detectar el deadline, si no queda cola, el lector termina inmediatamente sin buscar otra trama. Si hay cola, inicia la finalización hasta el primer LF. El deadline de finalización es absoluto y nunca se desplaza por recibir datos. Cada lectura adicional solicita un byte; no consume deliberadamente una línea nueva. Si una lectura que ya estaba en vuelo devuelve un chunk con varias líneas y un prefijo final, se conserva todo y se completa ese prefijo pendiente dentro del mismo presupuesto. No se recorta un chunk recibido para fabricar un límite limpio.

Los límites de tiempo y bytes se aplican por RX. El timeout se reduce al presupuesto restante antes de leer. Un backend debe respetar su timeout finito; el sistema operativo no ofrece aquí tiempo real duro. Si una lectura retorna después del deadline de finalización, se conservan sus bytes y tiempos y `last_return_within_budget=false` impide aprobar esa parada. La envolvente completa incluye además parsing, persistencia y cierre: no se declara que esos trabajos terminen dentro de los 250 ms.

Agotar tiempo/bytes sin LF conserva la cola y causa rechazo. Error o aborto elude la espera de finalización y detiene al otro lector; se juntan los hilos antes de cerrar ambos objetos de puerto, incluidos errores de arranque. Un LF solo delimita una línea: no valida CSV/CSI ni elimina un residuo inicial. No hay flush, drenaje hasta silencio, reintento, reset ni cambio de firmware.

## Tiempos, conteos y rechazo

Cada `rx-*.summary.json` y su copia en `session.results` contiene `stop`: inicio/parada monotónicos y UTC reales, deadline nominal y de finalización, inicio de finalización, retorno de última lectura, bytes adicionales, cola conservada y motivo (`lf_boundary`, `time_limit_incomplete`, `byte_limit_incomplete`, `aborted` o `error`). Antes de arrancar un lector no se inventa un tiempo de parada: una segunda apertura fallida conserva la sesión parcial y el error de auditoría correspondiente.

El ledger conserva offsets, tamaños devueltos/solicitados, inicio/retorno real, UTC y fase de petición (`nominal` o `completion`). Sigue registrando lecturas no vacías; no se presenta como una traza de todas las peticiones y timeouts. La fase nominal de una petición no garantiza que su fila haya terminado dentro de la ventana: **para contar la fila se usa el retorno real del chunk que completó su LF**.

Por receptor, el auditor y el canónico distinguen:

- `preamble_rows`: retorno anterior al inicio común.
- `common_window_rows`: inicio común ≤ retorno < deadline común.
- `post_deadline_rows`: retorno ≥ deadline común, incluso si la petición empezó antes.

Las filas de finalización mantienen su timestamp y quedan en bruto/CSV/canónico/visualización. No se reasignan a los 30 s y no sustituyen el requisito de al menos una fila dentro de la ventana común para cada RX. No se interpola ni se rellena ningún intervalo.

`src/audit_bounded_stop.py` vuelve a recorrer el bruto y los eventos para comprobar fase, tamaños, cola pendiente antes de cada lectura de finalización, límite absoluto, presupuesto, contadores y último retorno. Contrasta los tiempos con apertura, lectores unidos y cierre por RX. Un motivo de parada o fase falsificados se detecta incluso al recalcular hashes.

En una sesión abortada, el deadline **planificado** puede quedar después del cierre real. v2 permite auditar los bytes de esa envolvente menor, pero el estado interrupted/error y el motivo de parada impiden aprobar la sesión. Este caso falló en el primer ensayo de desarrollo y se corrigió; no se relajan las condiciones para una sesión completed.

La integridad de lo registrado puede ser válida aunque haya error de lectura, cola incompleta o arranque residual. `complete_rows_quality_ok` describe el formato/perfil de las filas completas; `stop_quality_ok` describe la política; `quality_ok` global exige además adquisición completada, postflight, cobertura y todos los criterios estrictos. Una sesión con residuos iniciales sigue rechazada aunque termine limpiamente en LF. `stable_window=null`: no existe un recorte aprobado.

## Auditoría y visualización verificadas

La auditoría v2 está integrada en `tools/analizar_captura_controlada.py`, el canónico y el exportador existente. Las etiquetas incluyen v2 y distinguen explícitamente evidencia sintética de física. La visualización muestra por RX los conteos nominales/posteriores/preámbulo, motivo/tiempo de parada y fase de la fila elegida. Las cuatro vistas incluyen todas las filas observadas; no se descartan las posteriores. RuView sigue ejecutándose solo con buffers, commit y runtime fijados, sin UDP ni modelo de presencia.

Pasaron **155 pruebas (124 Python y 31 Node), cero fallos, errores y omisiones**. Las 13 pruebas nuevas comprueban el coordinador con PTY privados: finalización correcta, timeout, flujo sin LF, aborto, error de RX-01, residuos iniciales, CSI malformada, fallo/interrupción de la segunda apertura, cierres después de lectores unidos, auditoría/canónico/consumidor y adulteración de motivo/fase. La prueba del CLI verifica que el modo predeterminado no abre UART y que un ambiente pendiente o límites distintos impiden la ejecución.

Se guardó además un ensayo **sintético** con 30 s nominales reales del reloj host: dos filas por RX, una dentro de la ventana y otra completada después, con LF y cero cola. Ambas paradas acabaron dentro del presupuesto. Un segundo ensayo sintético abreviado de 0.12 s, permitido solo mediante inyección de backend, termina en LF pero se rechaza por ROM pegada a residuos iniciales. La interfaz muestra su duración real, no lo llama una medición física de 30 s. No hay ninguna nueva medición física ni se simula una campaña completa.

Ambos bundles se auditaron otra vez por tamaño/SHA-256 y exportaron copias exactas. Firefox comprobó las ocho vistas (cuatro por ensayo), estado aceptado/rechazado, selector de fila, conteos y texto que excluye del intervalo nominal la fila posterior. Se inspeccionó además una imagen de RX-01/LLTF del ensayo aceptado. Los controles de navegador solo escucharon localhost dentro de una red privada. Los 51 archivos fijados antes de trabajar, incluidos históricos, intento físico rechazado, plan consumido, informes y fuentes de firmware, siguen intactos.

Reproducción, únicamente memoria/PTY y datos offline:

```bash
./tools/test_offline.sh results/local/visualizacion-csi-entrega/canonical.json
.venv/bin/python -B tools/ensayar_controlled_v2.py \
  --output-new results/local/ensayo-v2-otra-carpeta-nueva
```

El segundo comando crea su propio Bubblewrap con red y dispositivos físicos aislados; tarda algo más de 30 s. Los logs y artefactos de esta verificación están en `results/local/verificacion-controlled-dual-v2/`, ignorados por Git. No se suben brutos, visualizaciones con matrices ni `results/local`.

## Revisión pendiente y comando físico NO ejecutado

La causa de los prefijos iniciales, el comportamiento eléctrico al abrir/cerrar, las pérdidas anteriores a `read()`, la sincronización RF y el hash del firmware instalado siguen sin resolverse. v2 mejora el límite de parada del host; no demuestra ni corrige una causa de arranque WiFi/firmware. No habilita entrenamiento ni valida presencia.

Para revisar el plan sin descubrir dispositivos ni abrir UART:

```bash
.venv/bin/python -B tools/captura_dual_controlada.py \
  --plan config/captura_dual_v2_30s.template.json
```

El futuro comando de adquisición, preparado **solo para revisión**, sería:

```bash
.venv/bin/python -B tools/captura_dual_controlada.py \
  --plan config/captura_dual_v2_30s.local.json \
  --output-new results/local/captura-dual-v2-30s-plan01 \
  --execute-after-approval
```

**No se ejecutó ese comando, no se creó su plan local ni su directorio de adquisición y no hay otra autorización.** Antes de usarlo habría que copiar la plantilla, completar una declaración ambiental vigente, revisar este protocolo y recibir una nueva autorización explícita. El intento v1 rechazado y su autorización consumida no se reutilizan. El preflight volverá a comprobar series/by-id antes de cada apertura, como en v1.
