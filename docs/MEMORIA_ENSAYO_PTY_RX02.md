# Memoria del capturador y auditor RX-02

Se perfilaron offline el bundle sintético existente de 900 s y el diagnóstico
histórico de 240 s. Cada perfil se ejecutó en un proceso nuevo con Python
3.14.4. La finalización se reprodujo a partir de operaciones y bruto leídos
incrementalmente. Se regeneraron `summary.json` y `events.json` en una carpeta
temporal y sus hashes coincidieron con los archivos del ensayo. El replay
nativo se ejecutó aparte con puntos de muestreo antes y después de sus
asignaciones principales. Se usaron los registros existentes, sin repetir
la adquisición ni el ensayo sostenido. [Método y evidencia del ensayo](ENSAYO_SOSTENIDO_VISOR_CSI.md).

## Durante el servicio

| Tiempo desde el arranque, s | RSS muestreado, KiB | Eventos | Líneas | Operaciones escritas |
| ---: | ---: | ---: | ---: | ---: |
| 0,033 | 31.484 | 8 | 3 | 6 |
| 239,843 | 37.008 | 2.156 | 1.202 | 46.525 |
| 600,111 | 43.488 | 5.379 | 3.003 | 116.381 |
| 899,170 | 49.780 | 8.056 | 4.499 | 174.459 |

- El reductor conserva una referencia por línea en `states['RX-02']['lines']`
  y copia esa referencia en `events`. Cada comprobación periódica de espacio
  añade un registro a `storage_checks` y un evento. La conexión conserva
  también preámbulo, anomalías, fallos y señales. En el ensayo quedaron dos
  listas vacías de anomalías y fallos, y cero ventanas. En el replay incremental
  del estado final, líneas, eventos y comprobaciones sumaron **10.973.229 bytes**
  de objetos alcanzables sin duplicar referencias compartidas. Es una suma de
  `getsizeof` por objeto, independiente de la medición de RSS.
- La instrumentación del laboratorio añadió **834.736** muestras en arrays de
  8 bytes, **6.677.888 bytes** de datos antes de contar sobreasignación y metadatos.
  También retuvo 897 muestras periódicas de recursos. `Meter.summary()` ordena
  una métrica por vez y crea listas temporales de enteros Python al preparar
  el informe. Esas estructuras pertenecen al laboratorio.
- El bruto y el journal crecen en disco. El capturador procesa el chunk actual
  y mantiene hasta 65.538 bytes de prefijo de una línea parcial, contadores y
  hashes acumulados. Las entradas retenidas por línea son referencias y metadatos.
  Las 174.624 operaciones finales se materializan juntas durante el replay. Los
  17 descriptores y dos hilos muestreados permanecieron estables durante el servicio.
  El observador conserva su buffer separado de hasta ocho filas.

## Finalización y auditoría

| Etapa perfilada offline | Medición, KiB |
| --- | ---: |
| Finalización reconstruida, RSS antes de estimar espacio | 37.796 |
| Finalización reconstruida, pico tras estimar espacio y escribir JSON | 46.820 |
| Replay nativo de 900 s, RSS antes de cargar operaciones | 30.324 |
| Replay nativo de 900 s, RSS con lista de operaciones | 147.140 |
| Replay nativo de 900 s, pico del proceso aislado | 189.928 |
| Auditoría diagnóstica histórica de 240 s, pico del proceso aislado | 75.140 |

Al finalizar, `UartSession.finalize()` crea un resumen del reductor. El cálculo
de reserva materializa el JSON y su codificación UTF-8 para contar bytes. Se
reprodujo exactamente la reserva registrada de **4.620.779 bytes**. Después, el
journal construye otro resumen con la comprobación de espacio final y serializa
los archivos con `json.dump`. El pico de esta reconstrucción se alcanzó durante
el cálculo de reserva. [Finalización nativa](../src/presence_v4_uart.py) · [Escritura de evidencia](../src/presence_v4_journal.py).

El salto dominante aparece en `audit_rx02()`. Lee el bruto completo, lee los
**15.881.241 bytes** del journal como texto, divide en líneas y retiene la lista
de 174.624 registros JSON. El replay añade otro reductor con sus propios eventos,
líneas y comprobaciones. El auditor carga resumen y eventos guardados para
compararlos, vuelve a leer el journal como `bytes` y copia el prefijo del recibo
al calcular el hash. La CLI diagnóstica vuelve a decodificar el journal para
encontrar `closing`. El laboratorio histórico ejecutó el auditor mientras su
sesión de captura, su estado y sus medidores seguían en memoria. Su único
`ru_maxrss` de **212.848 KiB** abarca todo ese ciclo y el cálculo de cuantiles.
El perfil aislado localiza el mayor coste, con mediciones propias de esos
procesos. [Auditor del ensayo](../src/presence_rx02_journal.py) · [Auditor diagnóstico](../src/rx02_diagnostic/journal.py) · [CLI diagnóstica](../tools/diagnostico_checkpoints_rx02.py).

## Alcance de 240 s y operación prolongada

En el diagnóstico físico histórico, el servicio de 240 s registró **26.596 KiB**
de pico hasta el fin del servicio, 47.404 operaciones, 2.243 eventos y 1.283
líneas. El replay offline actual pasó integridad, cierre y diagnóstico, con el
rechazo de calidad por preámbulo conservado. El pico de auditoría de 75.140 KiB
pertenece al proceso offline que leyó ese bundle. Son antecedentes de una
ejecución cada uno. [Diagnóstico histórico](../results/RX02_DIAG_CP_R1.md).

El contrato usa 240 s desde `opened` para solicitar cierre, con salida temprana
por fatal. Se aplican topes de 500.000 operaciones, 100.000 eventos, 25.000
líneas, 16 KiB por registro/chunk y 64 KiB de journal pendiente de checkpoint.
El límite de conexión de la guardia de almacenamiento es 3.600 s. A las tasas
observadas de unas 194–198 operaciones/s, el presupuesto de operaciones se
agotaría en el orden de **42–43 min**, incluso con espacio libre. Esa estimación
depende de la carga y los topes pueden activarse antes. Un límite alcanzado
puede dejar bruto conservado sin manifiesto final. La memoria de replay crece
con el journal y los historiales retenidos. La revisión de 240 s contempla
auditar en un proceso separado tras la salida del capturador, de modo que las
dos historias no convivan. [Propuesta de revisión de 240 s](REVISION_VISOR_FISICO_RX02.md).

El análisis reproduce acumulación de evidencia y asignaciones temporales.
El servicio de 240 s pasó y el crecimiento observado corresponde a estructuras
con una vida útil identificada. Se conservaron las fuentes de captura y
auditoría fijadas por hash en los bundles. Una auditoría
incremental prospectiva requeriría una revisión que reproduzca manifiesto,
referencias, resumen, eventos y recibo con las mismas comprobaciones.

La evidencia local está en `results/local/revision-memoria-visor-20261110-r1/`.
`perfilar.py` reproduce las tres mediciones offline. Los JSON `*-r2.json` usan
una sola muestra por punto de traza y verifican además el cálculo de reserva.
Los perfiles iniciales se conservan en el mismo directorio.
