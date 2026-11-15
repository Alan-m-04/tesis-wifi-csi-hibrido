# Firmware ESP32-S3

| Rol | Proyecto | Resultado nuevo |
|---|---|---|
| TX-01 | csi_send | Compila con ESP-IDF v5.4 |
| RX-01 | csi_recv | Compila con ESP-IDF v5.4 |
| RX-02 | csi_recv_02 | Compila con ESP-IDF v5.4 |

Fuentes seleccionadas de la consolidación previa, copiadas literalmente y verificadas. Configuración canal 11, HT20, UART0 115200. Los receptores producen CSI_DATA. El CMake principal de componente TX se reconstruyó en la consolidación anterior; los tres C conservan la retirada previa de una inicialización de clave de ejemplo que no se usaba en la difusión sin cifrar. No se modifica el firmware durante esta importación.

ESP-IDF v5.4, commit `67c1de1eebe095d554d281952fde63c16ee2dca0`. Activar su entorno oficial y usar `tools/build_firmware.sh ROL` desde la raíz. No se incluyen SDK, binarios, sdkconfig generado ni entornos. Compilar no demuestra qué binario está actualmente flasheado.

Ver [NOTICE.md](NOTICE.md), [licencia Apache](LICENSE.Apache-2.0) y [procedencia por archivo](../docs/PROCEDENCIA_BASE.json).
