# Backend UART de v4 — contrato de implementación y revisión

Base `414b461410fec83f83a149d6e88cf323bb69fe96`. Trabajo exclusivamente offline, con dobles y PTY; ninguna autorización física vigente. Se conserva el [contrato v4](PROTOCOLO_PRESENCIA_PERSISTENTE_V4.md), sus tiempos y calidades, y v1/v2/v3 intactos. El nuevo transporte no elimina READY inicial ni fabrica ventanas si falta.

## Apertura, identidad y límites

Preparar por defecto sin descubrir ni abrir dispositivos. Preflight explícito de metadatos únicamente: reutilizar `capture_csi_multi.resolve_ports`, `port_identity`, `require_identity` y los by-id fijos de `controlled_capture.PORTS`; exigir USB VID 1a86, PID 55d3, número de serie correcto, dos nodos distintos y permisos efectivos de lectura/escritura. No corregir permisos, usar sudo o abrir para probarlos. Revalidar identidad y huella del nodo inmediatamente antes y después de abrir; persiste una posible carrera entre comprobación y apertura, que no se convierte en garantía eléctrica o identidad RF.

Ejecución física solo por opción explícita tras autorización nueva, plan ambiental y montaje completos, referencia de autorización y audio configurado. Crear primero evidencia/almacenamiento y objetos serie cerrados. Registrar cada recurso ANTES de llamar `open`, incluso el que falla a mitad. Una sola apertura por RX, sin reintentos ni reconexión. A se fija antes de la primera apertura; ambas comparten los 10 s de disponibilidad inicial. Se usa pySerial POSIX 3.5 auditado y `preserving_serial_type`, exclusividad consultiva, 115200 8N1 sin control de flujo y lectura no bloqueante. No se escriben comandos ni se purga entrada/salida.

Reutilizar journal v4: todos los chunks leídos, offsets, tiempos y hashes; separación conexión/ventana/cobertura/etiqueta, recibo de ambos cierres y auditor por replay. Antes de abrir: >=100 MiB libres. Transporte con límites explícitos propios, ajenos a la calidad de ventana: hasta 3600 s de conexión, 64 MiB de bruto, 256 MiB de bundle y reserva de 32 MiB para evidencia/cierre. Vigilar durante operación y antes de finalizar; conservar el chunk ya leído incluso si cruza un presupuesto. Al agotar un límite, suspender y cerrar sin sustituir ventanas. Fallos reales de escritura/fsync no acreditan un bundle íntegro; se intentan ambos cierres aunque no se pueda persistir su recibo.

## DTR/RTS: inspección efectiva local

Se inspeccionaron los cuerpos instalados de `serial.serialposix.Serial.open`, `_reconfigure_port`, `_update_dtr_state`, `_update_rts_state`, `close` y setters de `serial.serialutil.SerialBase`, versión 3.5. La procedencia de cada ejecución fijará esos archivos por SHA-256.

1. Construir con `port=None` no abre. Asignar `dtr=False` y `rts=False` mientras `is_open=False` solo guarda `_dtr_state`/`_rts_state`. Asignar `port` estando cerrado tampoco abre; hacerlo estando abierto sí cerraría/reabriría, por eso el backend no lo hace después.
2. `open()` llama primero a `os.open(O_RDWR|O_NOCTTY|O_NONBLOCK)`, luego a `_reconfigure_port(force_update=True)`: flock consultivo y `tcsetattr(TCSANOW)`. Después, con `dsrdtr=False` y `rtscts=False`, solicita DTR/RTS con `TIOCMBIC` para False. El constructor base parte de estados True; se sustituyen antes de abrir.
3. El bloque de ambos ioctl captura EINVAL/ENOTTY sin fallar la apertura. Si DTR falla así, RTS puede no llegar a solicitarse en ese bloque. Se registrarán intentos, retornos/errores y solicitudes que no llegaron a ejecutarse; un getter False no prueba que el ioctl se aplicó o la tensión del pin.
4. El adaptador existente suprime exclusivamente `_reset_input_buffer` del arranque de `open()` y prohíbe flush explícito. Esa supresión no altera el orden de apertura/configuración/ioctl. No garantiza conservar bytes que el hardware/driver nunca entregó.
5. `close()` cierra fd y pipes; no ejecuta explícitamente un pulso DTR/RTS en ese cuerpo. La configuración inspeccionada no limpia HUPCL: su estado previo y los efectos de último cierre/driver/puente pueden influir en las señales. No se promete ausencia de transitorios, pulsos, cambios de nivel o resets físicos al abrir/cerrar; no se miden aquí. READY/reset observados se conservan y aplican el rechazo correspondiente.

El cierre se intenta una vez para cada objeto, incluidos objetos parcialmente abiertos. Se comprueban `is_open`, fd y recursos auxiliares; fallo/estado desconocido impide el aviso de ambos cierres confirmados. No se usa un temporizador como prueba. Se evita un reintento oculto del destructor serie; una anomalía de cierre queda visible y requiere revisión, no se convierte en éxito.

## Sonidos sin ESP

Se añadirá una práctica separada que solo exporta/reproduce WAV de laptop, sin importar el backend ni abrir PTY/UART. Por defecto exporta sin reproducir. La reproducción será explícita, con demora para salir y patrones separados. Una respuesta humana posterior se guardará como declaración; el retorno de `aplay` jamás marca audibilidad humana verificada automáticamente. Tres tonos largos durante esta práctica son un EJEMPLO de sonido, no prueba de cierre de dispositivos.

Código, pruebas, comandos para revisión y resultados reales se documentarán al cerrar el cambio. No ejecutar el comando físico durante esta entrega; no calibrar ni realizar campaña física.

## Implementación y límites comprobados offline

`presence_v4_uart.py` reutiliza los verificadores de identidad y el adaptador de apertura originales, el coordinador/journal de v4 y sus señales/ciclo de vida. La huella del código pySerial inspeccionado se fija en [el lock del runtime](../config/pyserial_uart_v4.lock.json); una versión/implementación/hash diferente impide construir puertos. No se instala o actualiza pySerial en esta entrega.

Un lector de arranque empieza al abrir RX-01 y conserva sus bytes mientras se configura RX-02. Un lock serializa el journal/coordinador; RX-02 solo es legible tras publicar su apertura comprobada. El lector se reúne de verdad antes de pasar al bucle de operación, y también ante fallo de segunda apertura. La llamada de apertura de driver que ya esté en curso no puede cancelarse como si fuera un temporizador: no se garantiza un plazo duro de retorno de `open`/ioctl/fsync. El presupuesto de 10 s sigue corriendo y no se reinicia.

En UART el bruto se persiste primero; luego se toma el reloj efectivo de decisión, se aplica la operación y se persiste su registro. Un fallo posterior de almacenamiento rechaza el intento y conserva el T0 elegido, sin sustituirlo. Así una pausa de persistencia previa no retrocede la disponibilidad o el disparo. El modo de journal anterior conserva su orden por defecto; no se reinterpreta ningún bundle histórico. La extensión de `validate_plan` solo admite modo físico cuando el nuevo llamador lo habilita explícitamente; preparación/PTY anteriores siguen rechazando un plan físico por defecto. El auditor acepta evidencia física futura sin abrir dispositivos y mantiene evidencia sintética en todos los dobles/PTY de estas pruebas.

El límite de conexión se mide desde el inicio del backend; bruto y espacio se vigilan durante lectura. El espacio/bundle se vuelve a consultar al menos cada 250 ms del reloj usado cuando el bucle puede ejecutarse. Antes de escribir los informes finales se estima su tamaño con el mismo JSON indentado y se exige espacio para ellos más la reserva. No es una reserva exclusiva de filesystem ni una garantía frente a consumo concurrente, bloqueo de kernel, caída de energía o pérdida de bytes anterior a su entrega por driver. La falta de espacio/tiempo no habilita reintentos ni flusheos. Una escritura/fsync/recibo fallida conserva evidencia parcial y cierres intentados, pero no acredita integridad completa ni aviso de cierre confirmado. Un fallo de cierre conserva estado desconocido/fallido; se intenta el otro recurso y no se promete liberación exitosa del que falla.

Se registran estados solicitados, intentos efectivos DTR/RTS y sus errores, supresión de flush de apertura, parámetros serie, identidades, permisos y recursos liberados. La prueba HUPCL usa termios sobre PTY; no observa tensiones o resets en ESP. La confirmación de cierre es de recursos de software, no medición eléctrica. La exclusividad de flock es consultiva entre procesos cooperantes.

## Preparación y preflight: no abren UART

Desde la raíz del repositorio, el primer comando solo valida/prepara el ejemplo pendiente. El segundo, si se solicita posteriormente, lee metadatos/permisos; con ESP desconectadas se espera un error de disponibilidad, sin abrir para comprobarla. No se ejecutó preflight contra USB reales durante este trabajo.

```sh
.venv/bin/python -B tools/campana_presencia_uart_v4.py
.venv/bin/python -B tools/campana_presencia_uart_v4.py --preflight-only \
  --plan config/campana_presencia_uart_v4.template.json
```

## Comando físico concreto: SOLO PARA REVISIÓN, no ejecutar ahora

El ejemplo versionado contiene `PENDIENTE` y no puede ejecutarse físicamente tal cual. Para una autorización futura se preparará una copia local nueva, completando ID único de conexión, actor, montaje/hash, partición, ambiente y referencia de práctica de sonido. Los slots se fijan antes; cada uno se solicita manualmente y `last` se declara antes del último. No hay lanzamiento automático de tres o dieciocho ventanas.

```sh
cp config/campana_presencia_uart_v4.template.json config/campana_presencia_uart_v4.local.json
# REVISAR Y COMPLETAR esa copia; no hay autorización vigente.
.venv/bin/python -B tools/campana_presencia_uart_v4.py \
  --plan config/campana_presencia_uart_v4.local.json \
  --output-new results/local/V4-UART-CONEXION-UNICA-NUEVA \
  --execute-after-approval \
  --authorization-reference PENDIENTE-NUEVA-AUTORIZACION-EXPLICITA
```

La referencia pendiente se rechaza; no es una autorización generada por el software. La opción y la referencia documentan la declaración humana, no verifican por sí mismas que exista permiso real. No se debe sustituirla hasta una instrucción nueva y explícita. La ejecución real exige audio de laptop configurado y `aplay` disponible; un retorno de reproductor no confirma audibilidad humana. No hay override de puertos/duración/frescura ni relojes sintéticos por CLI física.

Tras disponibilidad inicial, órdenes locales: `slot B01-E`; al regresar, `declare B01-E yes` o `declare B01-E uncertain MOTIVO`; después otro slot fijado. `slot B01-W last` marca el último. `close` solicita cierre, `abort` interrumpe; EOF deja etiquetas sin confirmar. Ninguna orden reabre recursos o sustituye slots fallidos. [Práctica breve de sonidos sin ESP](PRACTICA_SONIDOS_V4.md). [Pruebas y evidencia](../results/BACKEND_UART_V4.md).

## Pendientes físicos

READY fresco inicial sin suponer que abrir lo reemite; permisos/by-id/exclusividad en los USB reales; retención y caudal prolongado; almacenamiento y latencia del host; comportamiento eléctrico/posibles transitorios o resets al abrir/cerrar; cierre/error con el driver real; audibilidad desde fuera y montaje sin mover equipos. Todo ello necesita revisión/autorización posterior según corresponda. No se cambian firmware o protocolos anteriores, no se calibra y no se ejecuta campaña física.

Frescura conserva el significado de v4: lectura/publicación en reloj host, no tiempo de llegada RF ni prueba de época de arranque. Preservar entrada también preserva datos que ya estuvieran en buffers; no se los borra ni se declara su latencia físicamente validada. Un fallo de lectura puede ser desconexión u otro error de driver/acceso: se registra la evidencia sin diagnosticar automáticamente su causa eléctrica.
