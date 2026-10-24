# Validación del panel local de preparación

Base: `73099b3347ff5403ca789c7c87d398ec7928b09b`. Rama: `feat/panel-control-local`.

## Comprobaciones ejecutadas

- Python 3.12.14: 10 pruebas, 0 fallos, 0 errores. Ejecución independiente del panel; no se ejecutó aquí el conjunto de 60 pruebas de la rama CSI.
- API HTTP local comprobada con puertos efímeros: estado inicial sin mediciones inventadas, guardado de dos borradores independientes, exportación, validación negativa, comprobación de Host/Origin y rechazo de acciones no implementadas.
- Inventarios USB sintéticos: ausencia, identidad visible, identidad duplicada y lectura de atributos sysfs en un árbol temporal. No se certifica detección en el equipo físico del usuario.
- Perfil fuente comparado byte por byte después de cada caso; no se modifica.
- Activos HTML/CSS/JS servidos mediante HTTP. Sintaxis Python comprobada con ast y JavaScript con `node --check`.
- SHA-256 del log de pruebas local: `1bac3406194f6774c658fa67bfe4e94310bed8d3401ed87d043175eca948c0b2`.

## Límites explícitos

No se abrió UART, no se compiló/flasheó firmware, no se cambió ESP-IDF, no se ejecutaron capturas ni modelos. El servidor escucha únicamente en 127.0.0.1 y utiliza la biblioteca estándar de Python. El panel permite guardar borradores, no aplicar ajustes a las ESP32.

No se completó comprobación visual en navegador: el runtime de Playwright local carecía de Chromium y el navegador remoto no pudo acceder al servicio loopback de este entorno. No se instalaron navegadores ni se expuso el servicio para sortear esa separación. La presentación visual y el uso desde el Ubuntu real deben revisarse antes de integrar esta rama. Las comprobaciones HTTP y de persistencia sí terminaron correctamente.

Se mantuvieron los cambios en archivos nuevos bajo apps/control_panel/, tests/control_panel/ y documentación propia. No se modificaron los archivos del visualizador ni la rama de trabajo de la otra sesión. Ver [procedimiento de arranque y alcance](../docs/PANEL_CONTROL_LOCAL.md).
