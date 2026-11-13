# Panel local de dispositivos por metadatos

Desde la raíz del repositorio:

```bash
.venv/bin/python -B tools/panel_dispositivos.py
```

Dejar esa terminal en ejecución y abrir **http://127.0.0.1:8766/** en el navegador.
Ctrl-C detiene el servicio. `--port 8767` permite elegir otro puerto local.
El servidor siempre se liga a **127.0.0.1**, sin opción de exponerlo en la red;
sirve el panel, su módulo JS, `/api/devices` y la reproducción histórica en
`/replay`. No instala dependencias nuevas.
El HTML requiere este backend para consultar el sistema operativo.

La vista adicional **Sesiones · SQLite offline**, en `/sessions`, reutiliza
el tablero y su hoja de estilo. Lee la base derivada de `403e794`, con calidad
estricta separada de integridad/replay/cierre. Para abrirla sin preparar C01/C03,
usar `tools/panel_dispositivos.py --sin-replay`. Esa página consulta únicamente
`/api/sessions`, sin consultar USB ni importar datos.
[Comandos, interpretación y supervisión en MIPYMES](VISTA_SQLITE_OFFLINE.md).

Para una sola consulta JSON sin servidor:

```bash
.venv/bin/python -B tools/panel_dispositivos.py --snapshot
```

El panel consulta al abrir y mediante **Consultar dispositivos**. Muestra una
instantánea con hora UTC de inicio/fin, no un monitor de conexión en tiempo real.
Cada RX muestra serie USB esperada, ruta by-id, si esa ruta se observó, nodo
actual comprobado, modo/uid/gid y acceso efectivo de lectura/escritura del proceso.
Si no hay una observación verificable, no inventa nodo ni permisos.

| Estado | Significado |
|---|---|
| Detectado | Serie, VID/PID y bus USB verificados en un nodo de la vista local. Permisos UART insuficientes no convierten esa detección en ausencia. |
| Ausente en la vista local | No hay coincidencias tras un inventario completo y accesible de esa vista. No demuestra desconexión física o falta de alimentación. |
| No verificable | `/dev` limitado/inaccesible, error de udev/stat, identidad contradictoria/duplicada o evidencia insuficiente. Una serie en USB/sysfs sin nodo tty verificable también queda aquí. |

La ausencia requiere que `/dev` sea un devtmpfs completo sin máscaras de las
rutas serie, que los inventarios `/dev`, tty/sysfs y USB/sysfs sean accesibles
y que las consultas de identidad no fallen. Es una barrera conservadora: si el
entorno no permite demostrar esa visibilidad, se muestra **no verificable**.
Las rutas `ttyACM*`/`ttyUSB*` se identifican por serie, nunca por número fijo.
Alias del mismo nodo se deduplican; una serie en varios nodos no se selecciona
automáticamente.

Se reutilizan `capture_csi_multi.RECEIVERS`, `controlled_capture.PORTS`,
`capture_csi_multi.port_identity` y `require_identity`. Las consultas usan
enumeración, resolve/stat/access, atributos USB/sysfs y `udevadm info` del
identificador existente. No construyen ni abren Serial, ni emiten un recibo de
preflight o autorización. No cambian los validadores históricos de adquisición.

**USB detectado no significa READY ni CSI recibido.** Ambos permanecen sin
observar en el panel. TX-01 alimentado externamente muestra **«no verificable
por USB»**; no se deduce su estado eléctrico o WiFi. La alimentación externa
es el escenario declarado, no una medición del panel.

Un fallo del backend o respuesta inválida elimina las observaciones anteriores
de nodo/permisos y muestra las identidades esperadas como no verificables. No
reutiliza una detección anterior como si fuera una consulta actual.

## Separación de la reproducción y estado experimental

La demo C01/C03 conserva su HTML autónomo y también se abre mediante el enlace
**C01/C03 · datos históricos**. El arranque del servidor reutiliza el generador
offline para crear/verificar ese artefacto; `/replay` sirve sus bytes en otra
página, sin consultar USB. La reproducción no consulta `/api/devices` y mantiene
`connect-src 'none'`. Solo el panel consulta metadatos actuales. No hay rutas de
captura ni acceso genérico al repositorio. Las consultas actuales no cambian la
identidad o calidad histórica de ninguna captura. R4 y los rechazos se conservan;
no hay otra adquisición preparada o autorizada. C04–C06 permanecen reservadas.

## Verificación realizada

16 pruebas Python con fixtures: estados, serie/VID/PID, permisos, alias,
duplicados, falta de acceso, USB sin tty, visibilidad de montajes, reloj y
reutilización del identificador existente. Incluyen HTTP sobre streams en
memoria, rutas de solo lectura, rechazo de hosts ajenos y enlace solo a loopback.
El arnés Node verifica campos, estados, TX externo, actualización manual y
eliminación de observaciones antiguas ante errores; usa DOM simulado.

La consulta real permitida en este entorno encontró una vista de `/dev` limitada:
ambos RX quedaron **no verificables**, sin afirmar desconexión. El intento de
arrancar el servicio falló con `EPERM` al crear el socket. No se solicitó una
excepción ni se intentó eludirla. Por ello, la navegación HTTP real y el aspecto
visual no pudieron verificarse desde ese entorno del agente.

Después, el operador confirmó que el panel abre en Ubuntu y muestra RX-02
detectado, RX-01 ausente y TX no verificable por USB. Se registra como observación
de esa consulta en Ubuntu, sin afirmar READY/CSI ni el estado actual posterior.
La declaración está en
`results/local/demo-tutor-navegacion-r1/comprobacion-panel-operador.json`.

La integración posterior añade enlaces entre páginas, valida inventarios
completos en el cliente y limita una consulta bloqueada a 12 s. El vencimiento
solo afecta a la consulta del visor, nunca a plazos de adquisición. No permite
consultas concurrentes desde el botón; respuestas incompletas, contradictorias
con el catálogo o que atribuyan READY/CSI se muestran como no verificables.
La nueva navegación requiere todavía revisión humana. Véase el
[guion de demostración](DEMO_TUTOR.md).

Evidencia en `results/local/panel-dispositivos-r1/`. No se ejecutó captura,
calibración, entrenamiento, resets, reconexiones o UART. Las pruebas del panel
no sustituyen la comprobación humana pendiente de los controles de reproducción.
