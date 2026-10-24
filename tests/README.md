# Pruebas reproducibles

Ejecutar `./tools/test_base.sh` con `.venv` y `requirements-dev.txt` preparados. Requiere Bubblewrap y Linux; falla si no puede aislar. Solo crea PTY sintéticos y archivos temporales; sin red ni UART física, repositorio montado de solo lectura.

40 pruebas ejecutadas aquí: 18 recuperadas del capturador dual, 20 nuevas de contratos e integridad y 2 regresiones offline de la referencia física. Estas últimas verifican hashes y el rechazo esperado; sin `data/raw/dual-60s-20261024T205854Z/captura` se omiten dos pruebas. Los subtests no se cuentan como pruebas adicionales. No se reivindican las 304 pruebas históricas.
