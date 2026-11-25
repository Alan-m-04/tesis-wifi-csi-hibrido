# Procedencia y licencia

La variante experimental conserva ESP-IDF v5.4 y es independiente de los tres
firmware históricos. El codec TCSI y el decoder son código nuevo bajo
Apache-2.0 (`firmware/LICENSE.Apache-2.0`).

El orden de inicialización Mesh, la creación de netifs y el patrón de eventos
se adaptan del ejemplo oficial Espressif `internal_communication`, marcado
Public Domain / CC0. Revisión consultada: tag v5.4; blob Git inmutable del archivo
`examples/mesh/internal_communication/main/mesh_main.c`:
`585df23cc9c10c9126c9e0542965e32d6a8705b4`.

Header de API Mesh contrastado en tag v5.4:
`components/esp_wifi/include/esp_mesh.h`, blob
`7a7e85cf893b51b10fa18651b2eaf45a6736fb7a`.

La configuración CSI y selección de los 19 metadatos se basan en el firmware
propio histórico, commit `0feec428f323d285c6c986b9ae50f5aca37ac303`, archivo
`firmware/csi_recv_02/main/app_main.c`, cuyo aviso atribuye a Espressif Systems
(Shanghai) CO LTD, 2025–2026, Apache-2.0. Se conserva esta atribución.

No se incorpora firmware RuView ni pesos externos. Consultar
`docs/PROTOCOLO_MESH_CSI_EXPERIMENTAL.md` para límites y verificación realizada.
