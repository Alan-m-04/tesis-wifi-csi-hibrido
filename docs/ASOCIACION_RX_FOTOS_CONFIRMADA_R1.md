# Asociación de fotos e identidades confirmada

Alan confirma visualmente los extremos de ambos cables USB y declara que no
movió ni desconectó nada. Esa observación, junto con las series y rutas USB
consultadas previamente, cierra la asociación pendiente:

| Identidad | Nombre completo de la fotografía en `/home/alan-monar/Downloads` | Serie USB | Conexión confirmada |
|---|---|---|---|
| RX-01 | `ChatGPT Image Nov 3, 2026, 02_23_17 PM.jpg` | `5C93199744` | Hub marrón; ruta USB `3-7.1`, detrás de GenesysLogic |
| RX-02 | `ChatGPT Image Nov 3, 2026, 02_23_29 PM.jpg` | `5C93200689` | Directamente a la laptop; ruta USB `3-4` |

La identidad se apoya en metadatos USB más seguimiento visual del cable, no en
apariencia de placa, antena, LEDs o número tty. No se han vuelto a consultar los
dispositivos ni abierto sus UART para registrar esta confirmación.

El [registro previo de metadatos](IDENTIFICACION_RX_USB_MONTAJE_R1.md) describe
la información que faltaba entonces. Su JSON original se conserva sin cambios.
Artefacto nuevo: `results/local/identificacion-rx-usb-metadatos-r1/asociacion-confirmada.json`,
con declaración del operador, hash del registro USB y hashes de las fotos:

- RX-01: `af4fa3e1a25090ec8ec10732435d0033f37294a03474e4ff0288ad9d34f568a8`.
- RX-02: `ae60d38a0136f65312cd952876a61389a93a96f7d4791ebdcd15f05ea7bb760d`.

Queda pendiente revisar la articulación de la antena externa de **RX-01, foto
02_23_17 PM**. La asociación no confirma que pueda inclinarse sin girar
conectores o tensar el coaxial y no autoriza esa maniobra. El [plan r2](PLAN_ORIENTACION_ABA_CONTINUIDAD_R2.md)
sigue sin intervención B definitiva ni autorización de ejecución. Sin capturas,
movimientos, desconexiones, cambios de firmware o consumo de autorización nueva.
