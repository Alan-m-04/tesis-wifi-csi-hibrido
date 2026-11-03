# continuity-dual-1 preparado exclusivamente offline

Base comprobada: `6450919618a8003a488c32e9d1925b84a9a80db3`, rama
`feat/backend-uart-presencia-v4`, limpia al reanudar. No existía implementación
pendiente de este diagnóstico. [Contrato](../docs/CONTRATO_CONTINUIDAD_DUAL_1.md)
definido antes de implementar; [plan y comandos](../docs/PLAN_CONTINUIDAD_DUAL_60S_R1.md).

Nuevo protocolo de observación de 60 s comunes, lectores independientes sin
entrada interactiva, arranque completo conservado, una apertura por RX y cero
reintentos. Un silencio >1 s sin fila válida es una incidencia recuperable del
diagnóstico; no modifica el watchdog de v4. Transporte/almacenamiento fallidos
detienen adquisición y cierran ambos una vez. Ni finalización nominal ni código
de salida 0 aprueban calidad o habilitan presencia/modelos.

Se reutilizan `UartEndpoint`, `audited_serial_type`, identidad/revalidación by-id,
lock de pySerial y `StorageGuard`, sin editar sus fuentes. `LineFramer` y el
validador CSI originales conservan perfil, errores, offsets, hash y referencias
de primera/última lectura. Journal y auditor propios separan adquisición física
de actividad offline; verifican cobertura del bruto, parsing, identidad,
autorización consumida y recibo de cierre. Los hashes aseguran consistencia,
no autenticidad criptográfica de una declaración del operador.

262 pruebas offline aprobadas en 23,949 s, cero omisiones: las 246 de regresión
y 16 nuevas con PTY propios/dobles de Serial. Cubren silencio/recuperación,
fragmentos sin LF y LF tardío, fallo de un RX y cierre de ambos, segunda apertura
fallida mientras se drena RX-01, identidad cambiada, cierre fallido sin reintento,
resets/errores/perfil incorrecto, callbacks y descartes, espacio agotado y escritura
parcial, alteración de brutos/referencias/identidad y reutilización de salida.
La ejecución por defecto y el preflight con metadatos sintéticos no construyen Serial.
Las pruebas se ejecutaron directamente; no se atribuye aislamiento de Bubblewrap.

Dos ensayos adicionales PTY con duración real nominal de 60 s, sin reloj acelerado:
el primero midió 60,008498417 s comunes, 288/289 filas y una incidencia recuperada
de 2,202694060/2,202848766 s en RX-01/RX-02. Conservó 23 bytes de cola por RX,
integridad/replay correctos y ambos cierres confirmados. Su fuente y artefactos
quedaron locales; el segundo utiliza el comando reproducible versionado abajo,
sobre el código final. Ambos son **evidencia sintética**, sin evidencia nueva RF.
El resumen verificable del segundo y los hashes están en
[CONTINUIDAD_DUAL_1.validacion.json](CONTINUIDAD_DUAL_1.validacion.json).

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python -B \
  -m unittest test_dual_continuity -v
.venv/bin/python -B tests/ensayo_continuidad_60s.py \
  --output-new results/local/ensayo-continuidad-pty-60s-NUEVO
```

Relojes/read/persistencia/procesamiento y referencias permiten contrastar huecos
del host, timestamps locales y contadores de callbacks/descartes. No localizan
de forma concluyente una pérdida entre RF/TX, callback, cola/tarea, UART, USB/driver
y planificación. El bloqueo de persistencia compartido sigue siendo medible;
fsync del ledger no tiene medición aislada. Relojes se muestrean sucesivamente.
No se garantiza cierre acotado ante un bloqueo del kernel/disco ni persistencia
de un recibo en disco averiado. Solo se conocen los bytes efectivamente leídos.

Se verificaron 2516 archivos anteriores idénticos: datos, autorizaciones,
firmware, código y protocolos históricos. Un archivo adicional, el estado general,
solo recibe un apéndice; su prefijo previo permanece igual. La copia local nueva y la salida
reservada están documentadas; la salida física no existe. No se ejecutó preflight
real ni se abrió UART; sin resets, reconexiones, firmware, calibración o entrenamiento.
Preparado para revisión, con declaraciones actuales pendientes y autorización
explícita nueva obligatoria antes de cualquier apertura física.
