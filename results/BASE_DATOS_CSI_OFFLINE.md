# Base CSI y análisis offline: piloto histórico verificado

Se implementó un índice SQLite derivado de los formatos existentes, con
dispositivos, sesiones, asociaciones, muestras CSI, referencias de archivos y
validaciones. El [esquema y los comandos del capítulo 3](../docs/CAPITULO_3_BASE_DATOS_CSI.md)
describen los relojes, fórmulas y límites. No se modificó el capturador ni se
abrió UART o adquirieron datos.

Piloto: **RX02-DIAG-VISOR-240S-R1**, ya auditado. Se reutilizaron el auditor
de diagnóstico/checkpoints, `rx02_physical_report.summarize`, las referencias
originales y el parser CSV vigente. Los hashes del manifiesto, informe,
evidencia JSON y auditoría guardada están fijados en
`config/csi_sqlite_pilot.review.json`. El replay actual coincide con el original.

| Indicador por sesión y receptor RX-02 | SQLite/CSV | Contraste |
| --- | ---: | --- |
| Apertura → cierre confirmado | 240,005564743 s | 240005564743 ns, informe original |
| Apertura → inicio de cierre | 240,003543760 s | 240003543760 ns |
| Filas CSI completas | 1.192 | 1.192 |
| Primera → última fila host | 239,191988869 s | 239191988869 ns |
| Cadencia entre retornos host | 4,9792637522332885 Hz | 4,979 Hz en el informe redondeado |
| Máximo hueco host entre filas | 614,782902 ms | 614,783 ms redondeados |
| Máximo hueco local, módulo 2³² | 601,971 ms | 601,971 ms |
| Calidad estricta | **Rechazada** | `format:RX-02` ×20, `preamble_anomaly:RX-02` ×1 |

Las métricas proceden de una vista SQL sobre las 1.192 muestras importadas y
se contrastan con los valores exactos del JSON de la consolidación original.
La densidad sobre apertura completa es 4,966551510 filas/s y se informa aparte
de la cadencia `(N−1)/(última−primera)`. Los relojes host/local siguen separados;
no son frecuencia RF ni estimación de pérdida de paquetes.

Integridad, replay, cierre, identidad, almacenamiento, checkpoints y diagnóstico
pasan; calidad estricta rechazada se conserva como octava validación. La
partición sigue siendo `diagnostic_only`, sin ventanas/etiquetas E/S y sin
permisos de calibración, entrenamiento o producción. Se conservan los bytes
exactos y campos CSV de cada muestra, incluidos data, RSSI, MAC, IDs, relojes,
metadatos y referencias; preámbulo/residuos permanecen en el bruto original.

## Dos importaciones y exportación realizadas

```bash
.venv/bin/python -B tools/base_datos_csi.py import-pilot
.venv/bin/python -B tools/base_datos_csi.py import-pilot
.venv/bin/python -B tools/base_datos_csi.py verify
.venv/bin/python -B tools/base_datos_csi.py export \
  --output-new results/local/base-datos-csi/csv-r2
```

La primera devuelve `imported`; la segunda, `already_imported`. Antes/después:

| Tabla | Primera importación | Segunda importación |
| --- | ---: | ---: |
| `devices` | 2 | 2 |
| `sessions` | 1 | 1 |
| `session_devices` | 2 | 2 |
| `source_files` | 16 | 16 |
| `csi_samples` | 1.192 | 1.192 |
| `validation_results` | 8 | 8 |

El SHA-256 del archivo SQLite también permanece idéntico entre ambas
importaciones. `PRAGMA integrity_check` devuelve `ok`; `foreign_key_check`
devuelve cero errores. Las 13 métricas/estados contrastados coinciden.
Las discrepancias de fuente o de registros existentes provocan error en vez
de reemplazar una sesión. Un fallo de métricas revierte la importación completa.

Base consultable: `results/local/base-datos-csi/piloto.sqlite3`.
CSV local: `results/local/base-datos-csi/csv-r2/RX02-DIAG-VISOR-240S-R1__RX-02.csv`.
Se publica una [copia agregada idéntica](BASE_DATOS_CSI_PILOTO/RX02-DIAG-VISOR-240S-R1__RX-02.csv);
base, bruto y muestras por fila siguen locales.

## Pruebas y conservación

**90 pruebas aprobadas**, sin fallos, errores u omisiones; incluyen 12 nuevas
específicas de SQLite. Se verificaron importación repetida, integridad relacional,
rollback de todas las tablas, datos/identidades en conflicto, copia de bytes
y metadatos, exportación exclusiva, consultas de solo lectura, huecos cero,
wrap local y frecuencia NULL en soportes insuficientes. La regresión relacionada
cubre auditoría diagnóstica, reporte físico, visor, C01, canonical CSI,
correspondencia y diagnóstico de huecos.

`./tools/test_base.sh` falló antes de ejecutar pruebas por no poder crear
namespaces Bubblewrap. La regresión se ejecutó directamente con
`csi_live_observer.guard` instalado para bloquear UART y rutas reservadas;
no se atribuye aislamiento Bubblewrap a estas pruebas.

Los **4.490 archivos anteriores protegidos** comprobados por hashes permanecen
intactos. Solo se actualizó la documentación de estado; README conserva sus
cambios anteriores. **C04–C06 no se abrieron ni usaron**. R5-N01 y su evidencia
anterior permanecen pendientes del ensayo interactivo; no se ejecutó la práctica,
preflight, autorización o captura R5 durante este trabajo.

Los logs, resultados de ambas importaciones, conteos, verificación SQL, hashes
y conservación están en `results/local/base-datos-csi/validacion-r1/`.
El [resultado estructurado](BASE_DATOS_CSI_OFFLINE.validacion.json) fija los
artefactos, fuentes y comandos de las pruebas. El adaptador inicial solo admite
el piloto elegido: otros formatos requieren adaptación y validación explícitas.
