# Verificación de la base propia — 24 de octubre de 2026

`./tools/test_base.sh`: **40 pruebas, 0 fallos, 0 errores, 0 omitidas**, 3,520 s. Desglose: 18 recuperadas, 20 sintéticas nuevas, 2 regresiones offline sobre una captura física anterior. Red bloqueada, repositorio de solo lectura, dispositivos privados de Bubblewrap; ninguna UART física abierta.

Se comprueban parseo y captura dual sintética, matrices inválidas, canal y MAC incorrectos, corrupción y falsificación CSV, hashes, identidades, duplicados y saltos callback, wrap uint32, reinicios, timestamps UTC y ventana compartida, cola incompleta y códigos CLI. Se conserva el rechazo original de la referencia RX-01 (una línea malformada): no se relaja la calidad para hacer pasar las pruebas.

| Build nuevo | Retorno | Tiempo | Flasheado |
|---|---|---|---|
| TX-01 | 0 | 28,462 s | No |
| RX-01 | 0 | 32,538 s | No |
| RX-02 | 0 | 33,854 s | No |

ESP-IDF v5.4 (`67c1de1eebe095d554d281952fde63c16ee2dca0`), objetivo esp32s3; GCC 14.2.0 (esp-14.2.0_20241119), CMake 3.30.2, Ninja 1.12.1 y esptool 4.12.0. Entorno Python aislado con pyserial 3.5, sin dependencia NumPy para esta base mínima. Los logs íntegros permanecen en `results/local/`; el JSON adyacente fija el hash del log de pruebas.

No se ejecutaron 304 pruebas anteriores: solo el conjunto explícitamente incorporado. Compilación exitosa no demuestra identidad del firmware instalado ni integración RuView/Edge AI.
