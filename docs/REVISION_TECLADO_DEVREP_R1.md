# Declaración visible y teclado no bloqueante: revisión offline

R3-N01 conserva el rechazo: E completa con `label.status=pending` y
`declaration_ns=null`, S no creada, `missing_declaration_by_deadline`,
`fatal=interrupt`, serie detenida y autorización consumida. La auditoría offline
reproduce 23.104 operaciones, manifiesto, eventos, resumen y checkpoints.
RX-02 tiene cierre confirmado y lector detenido, con prueba
`pyserial_close_returned_and_all_fds_released`.

No existe ninguna operación `declare`. El journal no registra teclas crudas ni
líneas incompletas: eso no permite afirmar que el teclado no funcionó o que el
operador no escribió. El lector histórico esperaba una línea terminada con Enter;
el coordinador solo imprimía una línea informativa una vez, sin cursor destacado
o tiempo restante. No se reemplaza retrospectivamente la etiqueta pendiente.

## Nueva interfaz optativa, sin modificar las fuentes históricas

`src/devrep_keyboard_prompt.py` añade lector, salida y un bucle de operación que
delega solicitudes, declaraciones, paradas y cierre al `Coordinator` nativo.
Las fuentes que auditan R1/R2/R3 permanecen intactas. El ejecutor consumido R3
conserva su interfaz original; no se lo cambia para reintentar.
La entrada física futura deberá seleccionar y vincular esta interfaz nueva
explícitamente. No se prepara ahora ningún plan, ID, preflight, solicitud o
autorización de captura siguiente.

Cuando el reductor permite declarar después del aviso final del slot, aparece:

```text
ESCRIBE AQUÍ LA DECLARACIÓN Y PULSA ENTER
ID_DEL_SLOT | tiempo restante: 59 s
Si se cumplió: declare ID_DEL_SLOT yes
Si hay dudas: declare ID_DEL_SLOT uncertain MOTIVO
> texto que está escribiendo el operador
```

El plazo se obtiene de `initial_available + label_due_offsets_ns[index]`, en el
reloj de la sesión. Sigue siendo A+210/A+420 s; mostrar o actualizar el prompt
no inicia otro plazo. Se conservan las solicitudes A+30/A+240 s y los umbrales
nativos. El reductor decide si la declaración es válida o tardía. El prompt no
crea etiquetas ni completa `yes` automáticamente.

El lector usa `O_NONBLOCK`, una lectura acotada por iteración y un buffer de 8 KiB.
Mantiene UTF-8 parcial hasta Enter, permite Retroceso y Ctrl-U y trata CRLF como
una sola entrada. EOF no envía una línea incompleta; Ctrl-C/abort detienen.
La salida usa una escritura no bloqueante por iteración; el estado más reciente
reemplaza una cuenta atrás obsoleta y los mensajes tienen un presupuesto acotado.
Un terminal lento no espera dentro del servicio CSI. La entrada parcial sigue
visible al redibujar el prompt, sin desplazar un banner nuevo por cada tecla.
Se restauran atributos y flags del terminal al terminar, incluso con error.

## Pruebas y práctica sin UART

39 pruebas aprobadas, cero fallos/errores/omisiones en
`results/local/revision-teclado-devrep-r1/pruebas-offline-r2.log`. Incluyen:

- Lectura vacía/parcial no bloqueante, Enter, CRLF, UTF-8, Retroceso, Ctrl-U,
  EOF, Ctrl-C y límites de buffer; restauración del terminal y salida saturada.
- Cuenta atrás anclada al plazo original, prompt visible y redibujado en PTY.
- Servicio CSI sintético sobre PTY propio mientras el teclado usa otro PTY:
  E/S con Enter, ausencia de Enter, Enter tardío real, incertidumbre, abort,
  slot incorrecto y EOF. Integridad/replay, cierre único y rechazo se verifican
  con el auditor nativo. Son fixtures sintéticos, sin datos físicos nuevos.
- Proceso real de práctica sobre PTY propio y regresiones de práctica/preflight.

La práctica final ejecutada verificó E escrita sin Enter durante más de un
segundo, cuenta atrás cambiante, aceptación al pulsar Enter, corrección con
Retroceso y CRLF en S, redibujado y restauración. Transcript y resultado en
`practica-PTY-final.transcript.txt` y `practica-PTY-final.validacion.json`.
Esto comprueba el programa con entradas automáticas; no acredita todavía la
experiencia del operador humano. No se reprodujo audio ni se usó UART.

Para practicar manualmente desde la terminal normal Ubuntu:

```bash
cd /home/alan-monar/tesis-wifi-csi-hibrido
.venv/bin/python -B tools/practica_teclado_devrep.py
```

El programa muestra las órdenes `declare PRACTICA-TECLADO-E yes` y
`declare PRACTICA-TECLADO-S yes`, cada una en su prompt. Tiene 60 s por entrada
de práctica, explícitamente separados de los plazos experimentales. No exige
salir del cuarto. Funciona sin UART, audio, CSI, consumo de permisos ni etiquetas
guardadas. No tiene opción de captura. Ante incertidumbre/abort, entrada
inválida, EOF o vencimiento termina sin completar el ejercicio.

Los originales, sus rechazos y todos los permisos consumidos quedan protegidos
por hashes. Revisión y preservación en `results/local/revision-teclado-devrep-r1/`.
No se modifica firmware, calibración, entrenamiento ni se accede a C04–C06.
