# Estado inicial del repositorio nuevo

Fecha: 24 de octubre de 2026, Ecuador.

## Medido en esta base

Solo se preparó la estructura del repositorio y su documentación. No se han incorporado fuentes del proyecto restaurado, ejecutado sus 304 pruebas ni capturado CSI físico en esta base.

## Antecedentes declarados por el usuario

Ubuntu reinstalado, ESP-IDF v5.4, TX-01/RX-01/RX-02 compilables, canal 11, HT20 y CSI_DATA por UART. Captura dual anterior: 292 filas válidas en RX-01 y 291 en RX-02. Su validación estricta falló por arranques iniciales y una línea residual. No hay modelo Edge AI entrenado y validado para el entorno.

Estos antecedentes requieren importar y revisar sus evidencias para reproducirlos en el repositorio nuevo.

## Material disponible fuera de esta base

El trabajo anterior de auditoría e integración sintética es una referencia separada. No se incorpora automáticamente como implementación aprobada. RuView fue inspeccionado en el commit `fefb0f918eefa7db6daef8cc83787fc7d6f74187`; esa revisión es candidata, no una dependencia instalada de esta base.

El adaptador real y las decisiones de parser, orden I/Q, bandas LTF y reloj se aprobarán después de inspeccionar el código y las capturas de la tesis.

## Repositorio y siguiente hito

El siguiente hito es incorporar las fuentes verificadas. Repositorio remoto creado por el usuario: https://github.com/Alan-m-04/tesis-wifi-csi-hibrido . Visibilidad privada verificada mediante la API. Esta primera incorporación contiene solo estructura, documentación e instrucciones para Codex; no contiene firmware ni capturas.
