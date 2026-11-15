# Presentación compartida de operación y práctica

`src/devrep_operation_view.py` es la única presentación nueva: recibe el estado
del coordinador, el dominio explícito y su reloj. La práctica v3 y el adaptador
reutilizable `src/devrep_operator_interface.py` llaman al mismo renderizador.
No crea planes, identificadores, permisos ni ejecutores por intento.

| Evento | Acción visible | Sonido pertinente existente |
|---|---|---|
| Solicitud E | SAL DEL CUARTO AHORA Y CIERRA LA PUERTA | Hay que estar fuera antes de los dos tonos cortos. |
| Aviso de establecer E y espera posterior | PERMANECE FUERA | Dos tonos cortos al establecer; se espera fuera hasta el tono corto final. |
| Fin de E, tras reproducción satisfactoria | REGRESA Y ESCRIBE LA DECLARACIÓN | Un tono corto; prompt con la orden completa de E. |
| E reconocida y solicitud S | SIÉNTATE Y PERMANECE QUIETO | Dos tonos cortos al establecer S; conservar la postura hasta el aviso final. |
| Final de S | ESCRIBE LA DECLARACIÓN Y PULSA ENTER | Tono corto de fin de ventana y tres tonos largos finales; prompt con la orden completa de S. |

El prompt incluye `declare ID yes`, `declare ID uncertain MOTIVO` y **Tiempo
disponible para responder**. Su contador usa el vencimiento absoluto del plan;
abrir o repintar el prompt no reinicia ningún plazo. No acepta abreviaturas ni
convierte incertidumbre en confirmación. Una entrada inválida muestra el formato
esperado y mantiene la política nativa de parada.

Los textos se identifican como `[PRÁCTICA]` o `[ADQUISICIÓN FÍSICA]`. La práctica
distingue entrada inválida, incertidumbre, cancelación, vencimiento, error de audio
y error de interfaz, con registros y códigos de salida diferentes. Su final es
**FIN SIMULADO**. La vista física solo indica **CIERRE FÍSICO COMPROBADO** cuando
constan lectura detenida, cierre confirmado y reproducción del aviso. Un tono
por sí solo no demuestra cierre ni que una persona lo oyera.

Los trabajadores de audio originales y la práctica producen WAV idénticos para
los avisos correspondientes. El adaptador de presentación delega la adquisición
al coordinador nativo y al teclado/consola no bloqueantes existentes. Se verificó
con PTY y CSI sintético, sin abrir un dispositivo físico. Los ejecutores y fuentes
históricos R1–R4 permanecen intactos: no se ha seleccionado ni preparado un nuevo
punto de entrada físico ni reutilizado un permiso consumido.

## Práctica vigente, pendiente de ejecución humana

```bash
.venv/bin/python -B tools/practica_guiada_devrep_v3.py
```

Escribir `practicar` y Enter para comenzar. Cuando lo solicite la terminal,
introducir la orden completa correspondiente, solo si se cumplió la condición:

```text
declare PRACTICA-GUIADA-E yes
declare PRACTICA-GUIADA-S yes
```

Ante duda se usa `declare PRACTICA-GUIADA-E uncertain MOTIVO` o su equivalente S.
`abort` o Ctrl-C cancelan. Cada ejecución crea un directorio local nuevo con su
resultado. `guiada-e` por sí solo no tiene el formato de declaración.

El operador declaró que en una práctica anterior salió y oyó el tono final, pero
escribió solo «guiada-e». Se conserva como declaración posterior en el registro
de esta sesión, sin deducir la causa exacta de terminación ni cambiar etiquetas.

Las pruebas PTY completaron E y S con entradas sintéticas y verificaron la
secuencia y los patrones de sonido. No prueban audibilidad humana. La práctica
v3 manual sigue pendiente; esta sesión no preparó una adquisición.
