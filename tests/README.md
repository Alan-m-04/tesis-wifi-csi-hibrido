# Pruebas reproducibles

Ejecutar `./tools/test_base.sh` con `.venv` y `requirements-dev.txt` preparados. Requiere Bubblewrap y Linux; falla si no puede aislar. Solo crea PTY sintéticos y archivos temporales; sin red ni UART física, repositorio montado de solo lectura.

Histórico del segundo hito: 60 pruebas ejecutadas: 18 recuperadas del capturador dual, 20 de contratos/integridad del primer hito, 19 de correspondencia y 3 regresiones offline físicas. Estas últimas comprueban datos y el rechazo histórico; sin `data/raw/dual-60s-20261024T205854Z/captura` se omiten tres pruebas. Los subtests no se cuentan como pruebas adicionales.

Las pruebas de correspondencia son contratos matemáticos offline; no ejecutan JavaScript/Rust ni sus dependencias. El extracto `fixtures/ruview_record_parser.py` contiene dos funciones puras revisadas del recorder oficial fijado al commit de la auditoría; licencia MIT adjunta. Ningún socket/CLI de captura externo se ejecuta. No se reivindican las 304 pruebas históricas.

## Tercer hito

Con Node fijado preparado, `./tools/test_offline.sh RUTA_CANONICAL_JSON` ejecuta 72 pruebas Python y 31 Node: 103 aprobadas aquí, sin omisiones. Node incluye 26 sintéticas y 5 regresiones físicas offline; Python incluye 69 sintéticas y 3 regresiones físicas. Sin el JSON físico se omiten cinco pruebas Node; sin copias físicas se omiten tres Python. `tools/test_base.sh` sigue ejecutando solo Python.

El módulo oficial vendorizado se ejecuta con buffers en memoria, sin UDP. El control visual opcional usa Firefox ya disponible y TCP localhost en una red privada, no forma parte de los 103 casos unitarios.

## Cuarto hito

El mismo `tools/test_offline.sh` ejecutó ahora 93 pruebas Python y 31 Node: 124 aprobadas, cero omitidas. Los 21 casos nuevos cubren el protocolo, entrada antes de abrir (solo PTY privado), exclusividad consultiva, encuadre/límites, orden de cierre, interrupción/fallo de segunda apertura, fallo de hilo y ledger alterado. Un caso usa el fragmento histórico exacto en memoria; no equivale a una adquisición física nueva. La captura física propuesta no se ejecuta durante las pruebas.
# controlled_dual_v2

La integración v2 pasó 155 pruebas: 124 Python y 31 Node, sin fallos, errores ni omisiones. Las 13 nuevas verifican el coordinador con PTY privados, parada acotada, timeout/flujo sin LF, aborto/error, cierre de ambos puertos, persistencia de residuos, separación de filas tardías y auditoría/consumidor. Se conservan las regresiones v1 y del intento físico rechazado. Ver [protocolo y evidencia](../docs/PROTOCOLO_CAPTURA_DUAL_V2.md).
