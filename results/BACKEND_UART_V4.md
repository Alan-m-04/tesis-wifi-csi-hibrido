# Backend UART v4 — implementación y verificación offline

Base exacta `414b461410fec83f83a149d6e88cf323bb69fe96`, rama `feat/backend-uart-presencia-v4`. [Contrato, inspección DTR/RTS y comando físico solo para revisión](../docs/BACKEND_UART_PRESENCIA_V4.md). [Práctica breve de sonidos sin ESP](../docs/PRACTICA_SONIDOS_V4.md). **No hay autorización física vigente y no se abrió UART real durante esta entrega.**

## Entregado

`presence_v4_uart.py` implementa el transporte con pySerial 3.5 POSIX fijado por hash: by-id/udev/serial/VID/PID y permisos efectivos, revalidación antes/después de abrir y comparación del descriptor con el nodo comprobado. Reutiliza `preserving_serial_type` sin modificarlo, sin purgas, escritura de comandos o cambios de firmware. Usa una sola apertura por RX, lector durante la segunda apertura, registro íntegro de chunks leídos y cero reintentos automáticos.

Los recursos se registran antes de abrir y se intentan cerrar ambos, también ante fallo parcial, interrupción o almacenamiento. Se reúnen lectores realmente; se comprueban estados/descriptores/pipes liberados y se persiste el recibo antes de emitir el aviso de ambos cierres confirmados. Un cierre fallido no se transforma en éxito ni se reintenta ocultamente al destruir el objeto. El cleanup de PTY del fixture es independiente y no se presenta como cierre físico del protocolo.

El backend conserva READY inicial y sus 10 s, ventanas prospectivas de 30 s, frescura, cobertura piloto, etiquetas y conexión de v4. Los únicos cambios compartidos son admitir modo/evidencia físicos de forma explícita y soportar el reloj/registro de decisión del backend UART. Los llamadores anteriores conservan modo offline por defecto y su orden de journal. Se mantienen todos los criterios y fuentes v1/v2/v3 sin cambios.

Antes de abrir exige 100 MiB libres; vigila 64 MiB de bruto, 256 MiB de bundle, reserva de 32 MiB y conexión máxima de 3600 s. Comprueba espacio para los informes finales y la reserva con el tamaño de JSON indentado. Un límite agotado suspende/cierra, sin recortar el chunk ya leído o sustituir ventanas. Falta de escritura/fsync/recibo impide acreditar un bundle completo o el aviso correspondiente; la evidencia parcial no se sobrescribe.

Preparación por defecto no descubre ni abre dispositivos. `--preflight-only` solo consulta metadatos/permisos. La ejecución requiere opción física explícita, plan local completado, referencia humana de autorización nueva y audio configurado; los marcadores `PENDIENTE` se rechazan. Esto no concede ni verifica automáticamente una autorización humana real. No hay relojes sintéticos, override de puertos o de tiempos por CLI física.

## DTR/RTS observado en software

La inspección fijó `serialposix.py` y `serialutil.py` de la instalación local en [el lock](../config/pyserial_uart_v4.lock.json). Asignar False con el puerto cerrado guarda solicitudes; al abrir, después de `os.open`/termios, pySerial intenta aplicar ioctl. Se comprobó **sobre PTY** que ENOTTY en DTR puede ser ignorado por `open()` y evitar que se llame al ioctl de RTS; los getters siguen False. También se ensayaron retornos simulados satisfactorios y un EIO que aborta. HUPCL permanece en termios cuando estaba establecido en el PTY de prueba.

El log registra solicitud, intento efectivo y error/retorno del software, sin equiparar False/retorno satisfactorio con tensión de pin. No se promete ausencia de transitorios, cambios de señal o resets al abrir/cerrar; kernel, driver, puente USB y placa reales siguen pendientes. El cierre de recursos no es una medición eléctrica y el proceso/kernel pueden cerrar descriptores también al terminar anormalmente, sin recibo de software.

## Pruebas y evidencia

**163 pruebas Python aprobadas, sin fallos, errores u omisiones:** 35 nuevas de UART/sonidos, 38 de v4 y 90 regresiones de disponibilidad/captura/parada v1/v2/v3. Ejecutadas directamente con memoria, serial dobles, PTY propios y archivos históricos de solo lectura; sin afirmar aislamiento Bubblewrap. Los dobles interceptan las rutas by-id antes de cualquier `os.open` serie y las redirigen exclusivamente a PTY creados por el proceso.

Cobertura nueva: preparación sin constructor ni descubrimiento; preflight sin abrir, identidad/PID/permisos/cambio de nodo; runtime distinto del lock; entrada anterior a apertura intacta y flush prohibido; orden DTR/RTS, ENOTTY/EIO y HUPCL; fd realmente abierto contra huella esperada; fallo de segunda apertura incluso mientras se lee RX-01; READY ausente y deadline antes de RX-02; dos ventanas separadas con una apertura/cierre por RX; desconexión de master PTY; fallo de fileno; KeyboardInterrupt; fallo de cierre, destructor sin reintento oculto; límites de espacio/bruto/tiempo/bundle y tamaño de informes; escritura/recibo fallidos con ambos cierres intentados; reloj tras latencia de persistencia; exportación/reproducción simulada y declaración humana separada de verificación automática.

Se conservan cuatro bundles sintéticos con manifiesto y replay en `results/local/backend-uart-v4/`:

- `dos-ventanas/`: dos ventanas de **30 s lógicos**, 300 filas por RX en cada una, con reloj por pasos y fuente sintética de 10 Hz. No es una medición física, una promesa de caudal o una calibración. Declaraciones de etiqueta y avisos son sintéticos.
- `segunda-apertura-fallida/`: ambos cierres intentados una vez; bytes de RX-01 registrados durante la apertura pendiente de RX-02; sin ventana inventada.
- `desconexion/`: cierre del master PTY produce error de lectura real de pySerial; se conservan error y cierres, sin reconectar.
- `cierre-fallido/`: RX-01 queda no confirmado, RX-02 se intenta igualmente; no se emite aviso de ambos cierres confirmados. El fixture libera sus recursos posteriormente fuera del protocolo.

El [JSON de validación](BACKEND_UART_V4.validacion.json) fija fuentes, logs, manifiestos, snapshots y resultados. Los brutos/operaciones/WAV quedan locales e ignorados. Las fuentes y resultados anteriores de firmware/captura, así como los 598 archivos del snapshot histórico, se conservan. Se auditan además bundles v4 sintéticos previos para comprobar que la extensión no modifica sus resultados.

`./tools/test_uart_v4.sh` conserva el fallo explícito de Bubblewrap: en este entorno devuelve 1 antes de ejecutar las pruebas porque no puede crear namespaces. No hay fallback en ese wrapper, modificación de kernel/permisos o afirmación de aislamiento que no se ejecutó.

Reproducción directa de las verificaciones offline, distinta del wrapper:

```sh
PYTHONPATH=src:tests .venv/bin/python -B -m unittest \
  test_uart_v4 test_persistent_presence_v4 test_availability_window \
  test_controlled_v2 test_controlled_v3 test_capture_preparation \
  test_capture_boundaries test_boundary_diagnostic -v
```

La práctica real de sonidos permanece **sin reproducir y con confirmación humana pendiente**. Solo se exportaron cuatro WAV; los tests de reproducción y respuesta sí/no usan dobles. La práctica nunca abre ESP ni marca audibilidad automáticamente.

Quedan pendientes por revisión/comprobación posterior: autorización nueva, montaje/ambiente, READY inicial y buffers/latencia reales, udev/permisos y driver USB reales, señales/transitorios/resets físicos, caudal/almacenamiento prolongado, fallos/cierres en esas placas y audibilidad desde fuera. No se calibró el detector ni se ejecutó una campaña física.
