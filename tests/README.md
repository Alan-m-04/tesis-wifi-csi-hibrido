# Pruebas reproducibles

Ejecutar `./tools/test_base.sh` con `.venv` y `requirements-dev.txt` preparados. Requiere Bubblewrap y Linux; falla si no puede aislar. Solo crea PTY sintéticos y archivos temporales; sin red ni UART física, repositorio montado de solo lectura.

60 pruebas ejecutadas: 18 recuperadas del capturador dual, 20 de contratos/integridad del primer hito, 19 de correspondencia y 3 regresiones offline físicas. Estas últimas comprueban datos y el rechazo histórico; sin `data/raw/dual-60s-20261024T205854Z/captura` se omiten tres pruebas. Los subtests no se cuentan como pruebas adicionales.

Las pruebas de correspondencia son contratos matemáticos offline; no ejecutan JavaScript/Rust ni sus dependencias. El extracto `fixtures/ruview_record_parser.py` contiene dos funciones puras revisadas del recorder oficial fijado al commit de la auditoría; licencia MIT adjunta. Ningún socket/CLI de captura externo se ejecuta. No se reivindican las 304 pruebas históricas.
