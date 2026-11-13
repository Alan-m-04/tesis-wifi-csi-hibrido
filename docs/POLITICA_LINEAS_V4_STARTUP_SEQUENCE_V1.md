# Política v4 de dos mensajes de inicialización, revisión 1

Contrato definido antes de implementar, desde `6af037b`. La selección nueva es
`line_policy_revision=v4-startup-sequence-1`. Las revisiones histórica y
`v4-app-main-return-1`, las plantillas y el protocolo CSI permanecen intactos.
La ausencia del campo sigue seleccionando `v4-strict-post-ready-1`.

No es una gramática general de logs. Solo reconoce dos líneas completas,
con LF o CRLF, dígitos ASCII y bytes exactos sin ANSI/prefijos/sufijos:

```text
I (<entero>) wifi:ic_enable_sniffer
I (<entero>) main_task: Returned from app_main()
```

El primer texto está registrado antes de READY en RX-02 y después en RX-01.
Las fuentes de RX-01 llaman `wifi_csi_init()` después de READY; RX-02 lo llama
antes. La API documenta la activación del modo promiscuo y las bibliotecas
locales contienen su símbolo, pero el cuerpo C del controlador es propietario:
no se afirma una prueba exhaustiva del orden interno de sus logs. El retorno
sí está explícito en `components/freertos/app_startup.c` del SDK fijado.

Reglas de la revisión nueva, independientes para cada receptor:

| Mensaje | RX-01 | RX-02 |
|---|---|---|
| `ic_enable_sniffer` | Una vez después del primer READY y antes del retorno. | Una vez antes del primer READY. No se permite después. |
| Retorno de `app_main()` | Una vez después de READY y de `ic_enable_sniffer`. | Una vez después de READY; no exige haber recibido el sniffer previo. |

Todas las excepciones deben procesarse antes de `begin + 10 s`, sin suspensión,
cierre solicitado/iniciado ni disponibilidad inicial. No se reinicia el plazo.
El sniffer debe preceder a toda fila CSI de ese RX, incluido CSI anterior a READY.
Un patrón reconocido fuera de orden, repetido, tardío o durante cierre suspende.
Esta restricción conserva un límite verificable; no promete aceptar órdenes
internos del controlador que no se puedan demostrar con las fuentes disponibles.

Se permiten cabeceras CSV exactas y líneas vacías interpuestas, que la gramática
compartida ya considera neutrales, y filas CSI válidas, comprobadas individualmente
sin modificar perfil o continuidad. En RX-02 esas filas también pueden preceder
a READY porque CSI se habilita antes. La tarea escritora es independiente y
puede escribir antes del retorno de `app_main()`. No se exigen adyacencia ni
ausencia de CSI para el retorno en esta revisión.

Para impedir que esas intercalaciones anticipen disponibilidad, la revisión nueva
exige los dos retornos antes del gate inicial, además de READY y tres filas frescas
por RX. Cada mensaje exceptuado vacía la racha de ese RX; no cuenta como CSI.
Así no reduce las exigencias de disponibilidad. La falta de retorno/sniffer
necesario termina por el timeout existente, sin petición de slot o reintento.

En la evidencia de la nueva revisión, el sniffer exacto se clasifica como `info`,
con `shared_kind`/`shared_reason` que conservan la clasificación compartida anterior
(`invalid`, `unrecognized_bytes`).
Se anotan el patrón y `line_policy_exception`; se conservan hash, tamaño, offsets,
lecturas y tiempos. El resumen expone qué mensajes se recibieron y la revisión;
procedencia y auditor exigen concordancia con el plan como en la revisión previa.

Cualquier otro texto posterior a READY conserva su tratamiento estricto.
`ic_disable_sniffer`, cambios de canal/configuración, errores, resets, READY
incorrectos/duplicados, CSI con otro perfil, discontinuidades, colas o líneas
mezcladas siguen rechazándose. No se recompone una línea CSI dañada por un log.
No se interpreta un timestamp impreso como reloj host ni prueba de ausencia de reset.

Los formatos iniciales distintos de estos dos mensajes **no cambian**: tags con
punto, logs `wifi:` sin espacio, residuos binarios y colas conservan su clasificación
y motivos. El prefijo binario de los registros existentes no es un mensaje normal
verificable. Los rechazos anteriores nunca se reauditan bajo esta revisión.

La revisión corrige dos incompatibilidades concretas; no resuelve por sí misma
la elegibilidad de una conexión con residuos iniciales. La conclusión de la
[revisión offline](../results/REVISION_ARRANQUE_V4.md) debe distinguir ese bloqueo
de la corrección sintética. No habilita adquisición, firmware ni calibración.
