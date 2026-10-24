# Captura y validación

`capture_csi.py` y `capture_csi_multi.py` son copias literales verificadas de los originales recuperados. El dual conserva identificación USB, salida exclusiva, logs brutos y validación estricta. No se ejecutó adquisición física en este hito.

`validate_capture.py` es código nuevo: audita offline los siete archivos de una sesión, manifiesto, hashes, CSV frente a líneas brutas, identidades, ventanas temporales, secuencias locales, perfil y resultado original. CLI: `.venv/bin/python src/validate_capture.py DIRECTORIO --manifest data/dual_60s_20261024.manifest.json`. Retorna 0 al aceptar, 1 al rechazar calidad y 2 ante entradas inválidas. La referencia histórica retorna 1 deliberadamente. No abre UART.

Los saltos del contador callback se informan aparte: no prueban pérdida RF. No se han implementado conversión compleja ni adaptador RuView.
