# Extracto oficial auditado para uso offline

`esp32.js` es una copia byte a byte de `harness/ruview/src/devices/esp32.js`, RuView `fefb0f918eefa7db6daef8cc83787fc7d6f74187`. Licencia MIT adjunta, SPDX intacto. SHA y referencia permanente en PROVENANCE.json. El package.json local es un envoltorio ESM privado, no el paquete npm upstream.

Única dependencia importada: node:dgram incorporado en Node. Se ejecutan parsePacket y SpectrumCollector; no captureEsp32 ni kernel. No se instala RuView ni su árbol de dependencias. El puente propio bloquea createSocket y se prueba en red aislada. Ver docs/CONTRATO_CONSUMIDOR_RUVIEW.md.
