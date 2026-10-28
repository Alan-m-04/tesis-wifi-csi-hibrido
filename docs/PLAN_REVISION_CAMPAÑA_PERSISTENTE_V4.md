# Revisión y operación individual propuestas — v4

**Sin autorización física.** No ejecutar UART, preflight udev, reset, captura o calibración. Este plan acompaña al [contrato definido antes del código](PROTOCOLO_PRESENCIA_PERSISTENTE_V4.md). El [piloto anterior](PLAN_CAMPAÑA_PRESENCIA_PILOTO.md) conserva su carácter histórico; su laptop exterior y sus aperturas por slot no describen v4.

## Decisiones concretas para revisar antes de cualquier campaña

1. Mantener laptop, TX, ambos RX, cables, silla y recorrido en las posiciones actuales para E/S/W. Laptop **dentro**, alimentada/configurada para no suspender. No exigir que alcancen cables al exterior ni añadir teléfono, altavoces, extensiones u otro operador. Completar descripción, croquis, referencias medibles e incertidumbre del montaje y fijar su hash; hoy no están comprobados. El recorrido deberá caber sin mover equipos; no se asegura la longitud previa de 2 m.
2. Revisar 60 s de demora, aviso a los 30 s, otros 30 s desde reproducción completada, gate de 10 s, frescura/monitoreo de 1 s, ventana de 30 s y margen final de 10 s. No se ajustarán con CSI para salvar intentos. Si el recorrido de salida/entrada no cabe en el margen, aprobar otra revisión antes de adquirir.
3. Revisar los cuatro sonidos exportados, volumen, selección de salida, modo silencio y suspensión de laptop. Desde el punto exterior, silla y recorrido deben oírse y distinguirse dos cortos (establecer), uno corto (ventana terminada, conexión abierta), tres largos (ambos cierres confirmados), ocho rápidos (fallo). La reproducción por `aplay` solo comprueba su retorno, no audibilidad. No se ha reproducido ni oído audio durante esta entrega. Si falla discriminación/audibilidad, detener el plan con el equipo actual; no interpretar silencio o tiempo transcurrido como cierre.
4. Revisar la separación `connection`/`window`/`coverage`/`label`, incluidos >=120 filas, >=15/bin de 5 s y huecos/bordes <=500 ms por RX. Son candidatos operativos fijados para esta versión, sin garantía estadística o RF; no cambian ninguna auditoría v3. Cobertura insuficiente o etiqueta incierta suspenden los slots futuros, conservando las calidades de datos que sí cumplan.
5. El primer READY sigue siendo un bloqueo real: solo se acepta uno observado dentro del arranque del intento de conexión, más filas nuevas. Persistir evita exigirlo de nuevo por slot, pero NO demuestra que pueda obtenerse al abrir después de que el firmware ya lo emitió. Revisar una futura conexión inicial autorizada; si no aparece en 10 s, conservar fallo y cerrar, sin reabrir/resetear para buscarlo.
6. Revisar/promover por separado un transporte físico: udev por ambas identidades verificadas, exclusividad, apertura sin flush y sin cambios DTR/RTS, conservación de bytes/lecturas, fallos reales, cierre confirmado y permisos/almacenamiento. Esta entrega SOLO implementa PTY propios; no contiene un interruptor para abrir UART. No hay autorización implícita para esa promoción o para usar las placas.

## Secuencia humana de un slot

La operación se solicita desde la misma laptop, localmente y de una en una. No hay scheduler de campaña, red, servidor, dashboard o ejecución general de tareas.

1. Tras verificar disponibilidad inicial en ambos RX, declarar ID de conexión/visita, actor, montaje/hash, partición e ID/condición del siguiente slot prefijado. Marcar `last` antes del último, sin decidirlo por los datos. Se mantienen abiertas ambas conexiones en toda la visita.
2. Solicitar el slot estando junto a la laptop. Para E, salir y dejar la habitación sin personas antes de los dos tonos cortos; para S, establecer postura en la silla; para W, comenzar el recorrido acordado. Mantener puerta/ventanas según el montaje y no mover cables/equipos. Son declaraciones, no observación instrumental.
3. La demora no es una ventana de datos experimentales ni una calibración. El flujo íntegro sigue registrándose. Tras la demora, el host exige otras tres filas por RX; T0 se decide entonces y puede ser posterior al minuto nominal. La persona mantiene la condición sin consultar la laptop durante [T0,T1).
4. Al acabar los 30 s se registra el fin; diez segundos después se reproduce un tono corto. Significa **ventana terminada y conexión abierta**. En un slot intermedio se puede regresar a la laptop, declarar si la condición ya existía al aviso inicial y se mantuvo hasta este aviso, y solicitar manualmente el siguiente. Las entradas/transiciones entre slots permanecen en el bruto, fuera de sus ventanas. Si hay duda, declarar `uncertain` y motivo: se suspende, no se sustituye el slot.
5. Si era `last`, ese tono solicita el cierre; no lo acredita. Se detiene el bucle lector, se cierran ambos recursos una sola vez, se comprueba su estado cerrado y se persiste el recibo. Solo entonces se solicitan los tres tonos largos de cierre confirmado. Con fallo de cierre no hay ese aviso; se intenta el cierre del otro RX y se conserva el fallo. Si no se oyó un aviso esperado, no se presume éxito: la condición/operación queda incierta y se revisa el recibo desde la laptop, anotando cualquier entrada para comprobarlo.
6. Guardar declaración posterior, desviaciones y método de observación. Los tiempos de los avisos/retornos son del host; el momento físico de cruzar la puerta o cambiar postura permanece desconocido. No editar brutos/CSV ni deducir la etiqueta del CSI. El ensayo automatizado declara estados exclusivamente sintéticos; no genera etiquetas físicas utilizables.

## Orden propuesto y particiones

Conservar como candidato el presupuesto de 18 slots y las seis permutaciones E/S/W, pero agrupar por **conexión persistente de visita**, no por filas/ventanas. No se ejecutan automáticamente:

| Conexión/visita propuesta | Slots en orden humano fijo | Grupo completo propuesto |
|---|---|---|
| V01, una apertura por RX | B01 E-S-W; B02 S-W-E; B03 W-E-S | Desarrollo exploratorio: hasta 9 ventanas |
| V02, otra visita, disponibilidad inicial pendiente | B04 E-W-S; B05 W-S-E; B06 S-E-W | Reserva completa futura: hasta 9 ventanas |

Toda V01 queda junta y toda V02 queda junta: no reutilizar el reparto 12/6 del plan anterior ni separar receptores/LTF/subventanas de una misma conexión. Dos conexiones/grupos NO acreditan independencia estadística suficiente, generalización o precisión; si V02 se usa para seleccionar método deja de ser reserva. El retorno de READY en otra visita no está demostrado. B01-E/B01-S siguen solo como anclas candidatas para una revisión posterior, nunca ajuste automático.

Los 18 slots son posiciones de intento, no una cuota de datos aprobados. Un fallo cierra/suspende la conexión y sus slots restantes. No hay reconexión, repetición, intervalo alternativo, reemplazo de ancla o sustitución por una ventana de mejores rasgos. Una nueva revisión/visita requiere conservar el fallo y una instrucción/autorización física nueva.

## Comandos disponibles ahora: exclusivamente offline

Preparar el ejemplo sintético sin abrir ni siquiera PTY:

```sh
.venv/bin/python -B tools/campana_presencia_v4.py
```

Ensayo persistido de dos slots SINTÉTICOS y auditoría por replay, con reloj virtual por pasos y 30 s lógicos por ventana:

```sh
.venv/bin/python -B tools/campana_presencia_v4.py --demo-pty \
  --output-new results/local/V4-PTY-NUEVO --stepped-fixture-clock
.venv/bin/python -B tools/campana_presencia_v4.py --audit results/local/V4-PTY-NUEVO
```

`--stepped-fixture-clock` usa pasos virtuales explícitos, no tiempo real. Para ensayar el bucle con reloj monotónico de pared, omitir esa opción y usar `--synthetic-speed 1` (unos 201 s para dos slots); otros factores aceleran también las pausas del host y pueden disparar el watchdog sin que haya desconexión. Un rechazo sintético se conserva y no relaja frescura ni provoca reintento automático.

Práctica manual con reloj real, fuente PTY sintética y avisos simulados por defecto. `--audio` opcional exige `aplay` ya disponible; no instala nada y puede reproducir sonidos reales de laptop. Esta práctica no mueve ni abre las ESP:

```sh
.venv/bin/python -B tools/campana_presencia_v4.py --operador-pty \
  --output-new results/local/V4-OPERADOR-NUEVO
# Opcional, solo para revisar sonidos: añadir --audio al ensayo manual.
```

Órdenes locales: `slot SYN-E`, después de su aviso `declare SYN-E yes` o `declare SYN-E uncertain MOTIVO`; luego `slot SYN-S last`, y su declaración posterior. `yes` confirma explícitamente establecimiento, continuidad y audición según la persona, con incertidumbre temporal desconocida. `close` solicita cierre y `abort` interrumpe; ninguna confirma cierre por sí sola. EOF no confirma etiquetas. Una orden rechazada no abre ventanas ni altera el journal.

Exportar los cuatro WAV sin reproducirlos, para una revisión posterior de audibilidad sin UART:

```sh
.venv/bin/python -B tools/campana_presencia_v4.py --export-cues \
  --output-new results/local/V4-SONIDOS-PRUEBA-NUEVOS
```

Son archivos marcados `PRUEBA-*`: escuchar una prueba de tres tonos no acredita cierre de dispositivos. Los logs, brutos PTY y WAV permanecen locales/ignorados. El ejemplo JSON está marcado sintético; no sustituye montaje, plan de visita, revisión del transporte ni autorización física.

Pruebas con aislamiento obligatorio:

```sh
./tools/test_presence_v4.sh
```

El wrapper conserva el fallo de Bubblewrap y no tiene fallback. En un entorno sin namespaces esa orden falla antes de ejecutar pruebas; una ejecución directa de unittest, si se realiza para revisión offline, se informa separadamente sin afirmar aislamiento Bubblewrap.
