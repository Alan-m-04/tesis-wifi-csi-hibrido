# Guía explícita de salida/regreso y práctica sonora, sin nueva captura

El operador declara después de R4 que permaneció dentro porque no apareció una
instrucción explícita para salir. Su texto literal se conserva fuera del bundle
en `results/local/devrep-rx02-r4-N01-declaracion-posterior-r1/declaracion.json`.
Documenta que no realizó vacío. No se antedata, sustituye la etiqueta pendiente
ni reclasifica E como sentado. No demuestra la condición S.

La auditoría offline reproduce integridad/replay de R4, sus eventos y rechazo:
E completa pero `label.status=pending`, `declaration_ns=null`, S no creada,
`missing_declaration_by_deadline`, `fatal=interrupt`, serie detenida y autorización
consumida. RX-02 tiene cierre histórico confirmado y lector detenido. El grant
conserva su estado al emitirse; el consumo efectivo figura en
`authorization-consumed.json` del bundle. Todos los originales quedan intactos.

La interfaz usada en R4 destacaba la declaración, pero mostraba las solicitudes
como eventos JSON y no daba una orden humana explícita de salir. Se añade
`src/devrep_guided_prompt_v2.py` sobre el teclado no bloqueante congelado. R4 y
su interfaz original no se modifican, de modo que sus hashes siguen auditables.
Esta revisión nueva no se activa sobre el intento consumido ni prepara otro.

## Instrucciones ligadas a eventos, con los mismos tiempos

| Estado/evento | Instrucción persistente |
| --- | --- |
| `slot_requested` E, A+30 s | **SAL DEL CUARTO AHORA Y CIERRA LA PUERTA**; estar fuera antes de los dos tonos. |
| Aviso de establecimiento E, gate y ventana E | **PERMANECE FUERA**. |
| T1 de E, antes de su aviso T1+10 s | **PERMANECE FUERA**; el fin de ventana por sí solo no permite regresar. |
| Reproducción satisfactoria del tono corto final E | **REGRESA Y DECLARA**, junto al prompt y su cuenta atrás original. |
| Declaración E aceptada y solicitud S en A+240 s | **SIÉNTATE Y PERMANECE QUIETO**. |
| Establecimiento, ventana S y espera de cierre | **SIÉNTATE Y PERMANECE QUIETO**, hasta los tres tonos largos. |
| Tres tonos largos de cierre confirmado reproducidos | Declarar S en el prompt visible. |
| Fallo, incertidumbre o suspensión | Detener y conservar evidencia; no se invita a regresar/declarar como si hubiera éxito. |

La guía delega el servicio al bucle anterior y al coordinador nativo. No modifica
policy, reloj, T0/T1, cola CSI, calidad, persistencia, cierre, solicitudes o plazos.
Los límites siguen A+210/A+420 s; redibujar letreros no reinicia un plazo. Para S
se oculta la invitación de declaración mientras falta el aviso largo de cierre;
el plazo absoluto y el validador nativo permanecen iguales. Entrada/salida
siguen no bloqueantes, acotadas y con restauración de terminal.

## Práctica completa con sonidos, sin UART

```bash
cd /home/alan-monar/tesis-wifi-csi-hibrido
.venv/bin/python -B tools/practica_guiada_devrep_v2.py
```

Escribir `practicar` y pulsar Enter inicia un reloj simulado. Después seguir las
cuatro instrucciones y sus sonidos: salir y cerrar puerta para E; permanecer
fuera tras los dos tonos; regresar al tono corto final y declarar E; sentarse
y permanecer quieto para S; esperar su tono corto final y los tres tonos largos
de cierre simulado antes de declarar S. El programa muestra estas órdenes:

```text
declare PRACTICA-GUIADA-E yes
declare PRACTICA-GUIADA-S yes
```

Se envían por separado en sus prompts, solo tras cumplir cada indicación y oír
los avisos. Ante incumplimiento o duda escribir `abort` o declarar `uncertain`
con el motivo: la práctica termina sin completar el ejercicio. No hay yes implícito.

La práctica usa los tiempos de la política/agenda R4 existente como guía: no hay
READY, disponibilidad RF, CSI, evaluación de presencia, etiquetas experimentales,
puertos abiertos o cierre real. Los estados y cierres son solo simulación sonora.
Los WAV se reproducen por la salida normal con `aplay`, en un trabajador separado,
y se eliminan al salir. No tiene opción UART, ejecución física o autorización.
`--rapida` acelera únicamente el reloj de práctica x10 y lo anuncia; no cambia
los tiempos experimentales ni está pensado para acreditar una condición física.

## Verificación realizada y límite de audio

56 pruebas offline aprobadas, cero fallos/errores/omisiones. Cubren los eventos de
la guía, persistencia de cada instrucción, prohibición de regreso prematuro en
T1, espera del sonido largo para S, fallo de audio, plazos originales, cinco WAV
con frecuencia/muestras/duración originales, teclado, ciclo E/S con CSI y teclado
en PTY propios, replay/cierre nativos y regresiones R4. No hay UART físico.

Además se ejecutó el proceso de práctica completo con teclado PTY y `aplay`,
reloj de práctica x10, durante unos 34 s. Se verificaron letreros en orden,
cinco WAV y reconocimiento E/S. Esa ejecución usó explícitamente el sumidero
ALSA `null`: es una prueba de reproducción por software, **inaudible**, no una
confirmación de escucha humana. La CLI entregada no usa ese sumidero y no tiene
opción silenciosa. La prueba con audio predeterminado agotó 10 s y este entorno
no expone `/dev/snd`; no se acredita audibilidad real. Debe comprobarla el operador
con el comando anterior desde su terminal normal, antes de otra preparación.

Los logs, transcript, cinco WAV y resultados están en
`results/local/revision-guia-sonora-devrep-v2-r1/`. Las pruebas son directas con
PTY propios; no se acredita aislamiento Bubblewrap. Los originales, notas y
fuentes históricas permanecen protegidos por hashes, incluidos R3 y anteriores.
No se prepara nuevo identificador, plan, salida, preflight, solicitud o grant
de captura. Sin adquisición, cambios de dispositivos, firmware, calibración,
entrenamiento o acceso a C04–C06.
