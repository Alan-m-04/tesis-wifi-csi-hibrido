# Integración mínima del visor con RX-02 para revisión

La integración está implementada y verificada con archivos y dobles offline.
La revisión 2 asigna al visor su propia identidad nativa. La sesión prevista
solo adquiere y visualiza CSI/RSSI. Requiere un preflight por metadatos de esta
revisión y autorización física explícita. El ensayo sostenido anterior fue
sintético.
[Resultados de la auditoría PTY](ENSAYO_SOSTENIDO_VISOR_CSI.md).

## Preparación del operador

El archivo de condiciones local se prepara con la declaración actual del
operador y el [formato versionado](../config/visor_rx02_240s.condiciones.review.json).
La ocupación y el movimiento describen la operación. El plan contiene cero
slots y tres permisos de uso en `false`. RX-01 queda desconectada según el
contrato diagnóstico. La potencia TX puede declararse desconocida.

El preflight original se conserva en
`results/local/preparacion-rx02-visor-240s-r1/preflight.json`. RX-02 estaba
enumerada en ese recibo. La frase que decía que las tres ESP seguían
desconectadas describía el momento anterior a la conexión. La copia revisada
separa esa declaración previa, la enumeración registrada y lo que requiere
confirmación actual del operador. Se conservan los datos de desconexión y
continuidad de alimentación desconocidos.

Desde la raíz, revisar offline el plan y su vínculo por SHA-256 con el recibo
original:

```bash
.venv/bin/python -B tools/visor_rx02_240s.py --review-plan results/local/condiciones-rx02-visor-240s-r1-revision-2.json
```

Para obtener los metadatos nuevos desde la terminal del operador:

```bash
.venv/bin/python -B tools/visor_rx02_240s.py --preflight-only results/local/condiciones-rx02-visor-240s-r1-revision-2.json
.venv/bin/python -B tools/visor_rx02_240s.py --review
```

El preflight valida las declaraciones, comprueba pySerial y espacio, y consulta
la identidad y permisos de RX-02 por udev/stat/access. Escribe una vez
`results/local/preparacion-rx02-visor-240s-r1-revision-2/preflight.json`.
La consulta trabaja con metadatos y no abre UART. `--review` muestra la
referencia de autorización ligada al SHA-256 exacto del preflight nuevo y el
comando que se revisará. El recibo original sirve como antecedente y no habilita
la revisión nueva. La identidad, huella, condiciones, arranque, reloj y fuentes
se revisan antes de solicitar autorización.
La preparación conserva cualquier preflight previo. Si cambia su contenido,
el host/arranque, la identidad o el código, se debe revisar el cambio antes
de autorizar una ejecución. Mientras no exista autorización ni salida del
intento, un preflight obsoleto se puede archivar con otro nombre y repetir
la consulta de metadatos.

La autorización, cuando se conceda expresamente, se registra fuera del bundle
en `results/local/preparacion-rx02-visor-240s-r1-revision-2/authorization.json` con el ID,
la referencia exacta, el alcance de un intento y la declaración humana. El
supervisor coteja esa autorización y vuelve a comprobar los metadatos. El
capturador comprueba otra vez la huella en su constructor antes de abrir y
vincula el fd abierto a esa identidad. El modo de ejecución está bloqueado
hasta que exista esa autorización y ambas salidas estén libres.

## Procesos y resultados

- El supervisor sirve `http://127.0.0.1:8767/` en modo de solo lectura. Reserva
  el puerto y la salida de vista antes de iniciar los procesos. Ctrl-C en la
  terminal solicita el cierre nativo al capturador una vez. Los botones y el
  cierre del navegador actúan sobre la vista.
- El capturador ejecuta `CheckpointRx02Session` y el bucle diagnóstico de
  240 s. Escribe `RX02-DIAG-VISOR-240S-R1` como `connection_id` y
  `partition_group`, con la misma identidad en el resumen, los recibos y el
  replay. Mantiene los criterios, el reductor y la persistencia del diagnóstico.
  El comparador histórico exige `RX02-DIAG-CP-R1`, pues sus informes atribuyen
  procedencia y grupo a partir de esos campos. El bundle histórico se verifica
  con los hashes exactos de los archivos versionados en el commit archivado.
- El observador abre los archivos de origen en solo lectura, verifica la
  apertura RX-02 ligada al preflight y requiere la constancia de reloj del
  trabajador de captura. Publica en la salida de vista con los mismos límites
  de sondeo, ventana e instantánea. Un fallo de vista se informa de forma
  independiente. El estado de cierre confirmado viene del auditor.
- El supervisor espera la salida del capturador y registra su código antes de
  lanzar el auditor en otro proceso. La vista conserva `observer-result.json`,
  `audit-native.json` cuando hay auditoría nativa y `audit-result.json` con
  cierre, integridad, replay y diagnóstico. Un bundle sin manifiesto se
  informa como incompleto. La calidad estricta se conserva por separado.

## Capturador y contrato

Reutilizar `rx02_diagnostic.checkpoint.CheckpointRx02Session` y el auditor
`tools/diagnostico_checkpoints_rx02.py::diagnostic_report`. La sesión ya cubre
RX-02, serie USB `5C93200689`, by-id fijado por contrato y 115200 baudios.
Conserva el parser, READY, plazos, guardia de almacenamiento, checkpoints
`rx02-raw-sync-control-checkpoint-2`, cierre y recibo nativos. El diagnóstico
separa calidad estricta de conexión, continuidad, replay y cierre. Su informe
histórico conserva el rechazo de calidad por preámbulo. [Fuentes del contrato](../src/rx02_diagnostic/contract.py) · [Auditor diagnóstico](../tools/diagnostico_checkpoints_rx02.py) · [Informe del intento consumido](../results/RX02_DIAG_CP_R1.md).

La revisión histórica del contrato fijó el ID `RX02-DIAG-CP-R1`, la duración de
240 s y la salida de ese intento. La autorización histórica está consumida. El
supervisor nuevo fija el intento **`RX02-DIAG-VISOR-240S-R1`**, el bundle
`results/local/diagnostico-rx02-visor-240s-r1` y la vista separada
`results/local/vista-rx02-visor-240s-r1`. El intento pertenece a la partición
`diagnostic_only`, con cero ventanas E/S y permisos de calibración,
entrenamiento y producción en `false`. Su registro de autorización es propio.
[Descriptor para revisión](../config/visor_rx02_240s.propuesta.review.json).

## Límites y cierre de los 240 s

- Una apertura de RX-02 y cero reintentos. RX-01 queda fuera de la sesión, con
  su condición declarada según el contrato. Se requieren READY, el arranque
  esperado y tres filas frescas dentro del plazo inicial de 10 s. El watchdog
  de 1 s sigue vigente. Una suspensión, fallo de transporte/almacenamiento o
  interrupción del operador toma el camino de cierre temprano.
- El plazo de 240 s corre desde `opened` y determina cuándo solicitar el
  cierre en el bucle de servicio. La persistencia y el driver usan operaciones
  síncronas que pueden exceder ese plazo. Se conserva el drenaje condicional
  de una cola parcial con presupuesto de 250 ms y 65.536 bytes. La cola sin LF
  queda en el bruto.
- Se exige 100 MiB libres al inicio, reserva de 32 MiB, 64 MiB de bruto y 256 MiB
  de bundle. El journal conserva los topes de 500.000 operaciones, 100.000
  eventos, 25.000 líneas, 16 KiB por registro/chunk y 64 KiB de operaciones
  pendientes de checkpoint. El bruto se sincroniza antes del reductor. El
  chunk completo se conserva si una lectura cruza un umbral. Una guarda
  fallida puede dejar un bundle parcial, con el material escrito preservado.
- El cierre se verifica con lector detenido, una apertura y un cierre, fd
  liberado y recibo durable. El aviso nativo depende del recibo. El auditor
  exige manifiesto íntegro, replay, referencias al bruto, checkpoints con
  pendiente final cero y correspondencia de recibo y estado. Un cierre
  incompleto o no confirmado queda registrado como tal. La calidad estricta
  y el resultado diagnóstico se informan por separado.
- El auditor existente se lanza en otro proceso después de que salga el
  capturador, con el mismo resultado nativo de cierre y calidad. El capturador
  conserva `service-metrics.json` del diagnóstico. [Perfil de memoria offline](MEMORIA_ENSAYO_PTY_RX02.md).

## Referencias de la propuesta inicial

Desde la raíz, el primer comando muestra el descriptor prospectivo. El
segundo valida e imprime el contrato heredado en modo de revisión y devuelve
`PREPARED_NOT_AUTHORIZED` para el R1 histórico. Ambos leen archivos locales.

```bash
.venv/bin/python -B -m json.tool config/visor_rx02_240s.propuesta.review.json
.venv/bin/python -B tools/diagnostico_checkpoints_rx02.py \
  --plan config/diagnostico_checkpoints_rx02_r1.review.json
```

El descriptor sigue siendo un artefacto de revisión. La ruta operativa está
en el supervisor nuevo y depende del preflight y la autorización descritos arriba.

## Contrato de la interfaz de solo lectura

1. Seleccionar explícitamente un bundle nuevo de esa revisión. Validar antes
   de observar el protocolo, el ID, la partición, los hashes de plan y
   procedencia y la revisión de persistencia. Vincular la serie y el by-id
   declarados a la identidad y huella registradas en `opened` por la sesión
   nativa. Exigir procedencia `physical_capture`, backend `UART` y coherencia
   con el registro de consumo de la autorización futura. Excluir históricos,
   otras topologías y C04–C06. El observador recibe una ruta autorizada por el
   plan y carece de acceso al UART.
2. Vincular el `time.monotonic_ns` de captura y visor al mismo host, arranque y
   dominio de reloj. La sesión física usa ese reloj para lecturas y decisiones,
   y su procedencia actual carece del ID de arranque. El trabajador registra
   una constancia externa a partir de la ruta canónica, el espacio de nombres
   temporal y los hashes de plan/procedencia/consumo. El laboratorio PTY tiene
   su propio esquema y alcance. Ante un vínculo ausente o incompatible,
   suspender la publicación en vivo.
3. Leer incrementalmente `operations.jsonl` y `rx-02.serial.log` usando el
   recorrido probado de secuencias, offsets, hashes y framer. Validar el perfil
   CSI de la revisión antes de extraer LLTF52. Mantener máscaras, referencias
   al bruto y timestamps originales como enteros decimales serializados.
   Esperar si el registro o los bytes referenciados aún están incompletos.
   Truncado, reemplazo o contradicción detienen el visor. Los registros visibles
   se presentan como **CSI PROVISIONAL · RX-02**, con durabilidad y calidad
   final sujetas al auditor nativo.
4. Mantener un proceso lector separado y una instantánea reemplazable fuera del
   original. Se aplican las cotas ejercitadas en
   la corrida larga, con sondeo cada 250 ms, 64 operaciones por sondeo, ocho
   filas en 30 s y 2 MiB por instantánea. El capturador posee toda la apertura,
   lectura, decisión, persistencia y cierre. El visor puede detenerse o reiniciar
   sin enviar comandos al capturador. Mostrar antigüedad y pérdidas de vista.
   Confirmar cierre físico solo con el recibo y la auditoría final, separados
   del estado de visualización y de la decisión de calidad.

## Estado de verificación

La revisión offline del contrato existente devolvió `PREPARED_NOT_AUTHORIZED`
con el plan en `offline_only`. Se confirmó con el plan versionado, en el modo
de revisión de la CLI. El resultado previo y la comprobación nueva se guardaron
como `revision-contrato-diagnostico.json` en sus respectivos directorios de evidencia.
Al retomar pasaron **49 pruebas Python seleccionadas** y el arnés JS del visor.
Las pruebas incluyen el diagnóstico con PTY y reloj simulado, la barrera sin
autorización, suspensión por falta de disponibilidad, replay, corrupción y
cierre. También verifican el rechazo de fuentes físicas por el visor actual.
La revisión humana del navegador y el recorrido con el dispositivo siguen
pendientes. [Método y mediciones del ensayo sintético](ENSAYO_SOSTENIDO_VISOR_CSI.md).

Para la propuesta de 240 s se ejecutaron los dos comandos de revisión y se
cotejaron identidad, límites, rutas y permisos del descriptor. Se comprobó
que el ejecutor histórico rechaza el ID nuevo. Pasaron **seis pruebas** de
contrato con dobles para preflight, sesión y Serial. Los perfiles de memoria
reutilizaron los registros guardados. [Evidencia y límites](MEMORIA_ENSAYO_PTY_RX02.md).

La integración operativa pasó **28 pruebas Python seleccionadas** y ambos
modos del arnés JS. Un fixture de archivos con 1.200 filas y reloj de 240 s
ejercitó el drenaje y replay en otro intérprete, con rechazo de preámbulo
conservado. Se verificó también un bundle incompleto, rechazo de identidad y
reloj, cambios de preflight y fallo de vista. Los arneses usaron archivos y
dobles locales. [Continuación y ruta de evidencia](CONTINUACION_SESION_OFFLINE_20261109.md).

En la revisión 2 pasaron **30 pruebas Python seleccionadas**. Se verificaron
las identidades en el plan, el grupo, el replay y los recibos. La comparación
histórica rechazó el plan del visor. El replay del bundle histórico conservó
integridad, cierre y el rechazo de calidad por preámbulo. El preflight original
conserva su SHA-256 y la revisión offline no equivale al preflight nuevo.
