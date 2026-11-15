**RX02-DEVREP-R5-N01, vacío → sentado, preparado para revisión offline.**

Se propone una conexión independiente de RX-02, con dos ventanas de 30 s,
solicitudes automáticas y la interfaz compartida vigente. Tu actividad actual
haciendo tarea y moviéndote por el cuarto queda registrada como contexto de
preparación. Las condiciones experimentales se establecerán cuando las solicite
un intento futuro autorizado.

El diagnóstico auditado del visor acredita una adquisición de 240 s, 1.192
filas conservadas y 1.192 procesadas por el observador, con cierre confirmado.
Su calidad estricta sigue rechazada por el preámbulo y tuvo un hueco host de
614,783 ms. La evidencia respalda el recorrido de adquisición y visualización
ejecutado. La propuesta conserva los mismos criterios de calidad y cobertura.
[Informe del visor RX-02](../results/RX02_DIAG_VISOR_240S_R1.md).

| Aviso de la interfaz | Acción del operador en el intento futuro |
| --- | --- |
| **SAL DEL CUARTO AHORA Y CIERRA LA PUERTA** | Salir para E antes de los dos tonos cortos. |
| **PERMANECE FUERA** | Mantener vacío hasta el tono corto final de E. |
| **REGRESA Y ESCRIBE LA DECLARACIÓN** | Regresar y escribir la declaración E completa en su prompt. |
| **SIÉNTATE Y PERMANECE QUIETO** | Esperar la solicitud S y mantener la postura durante S. |
| **ESCRIBE LA DECLARACIÓN Y PULSA ENTER**, tras cierre comprobado y tres tonos largos | Escribir la declaración S completa en su prompt. |

Las dos órdenes previstas, cada una cuando aparezca su prompt y solo si se
cumplió la condición y se oyeron los avisos, son:

```text
declare RX02-DEVREP-R5-N01-E yes
declare RX02-DEVREP-R5-N01-S yes
```

Ante incumplimiento o duda, declarar `uncertain MOTIVO` para ese ID o escribir
`abort`. Cada prompt conserva su contador de tiempo restante. La agenda actual
solicita E en A+30 s y S en A+240 s, donde A es la disponibilidad inicial real.
Los plazos de declaración son A+210 s para E y A+420 s para S. Se mantiene el
límite de solicitud de cierre A+390 s, con cierre temprano ante fallo y cero
reintentos.

El plan [R5-N01](../config/devrep_r5_N01.propuesta.review.json) fija una salida
nueva y un grupo de conexión propio, `development_future`, con calibración,
entrenamiento y producción en `false`. Selecciona la presentación actual
`devrep_operator_interface` / `devrep_operation_view` y reutiliza el perfil
técnico de capturador, agenda, persistencia y criterios existentes. El documento
de revisión mantiene el ejecutor físico deshabilitado. Su entrada física
con la identidad R5 se completará al revisar esa etapa.

El siguiente comando valida el plan y proyecta los avisos en memoria. Se puede
ejecutar durante la preparación actual. Sus entradas, sonidos y cierres son
simulados y quedan identificados así en el resultado:

```bash
.venv/bin/python -B tools/revisar_devrep_r5_n01.py --check-guidance
```

La comprobación usa el renderizador vigente y conserva política y agenda.
Comprueba la espera del tono final de E antes de invitar a regresar y el cierre
comprobado más el resultado sonoro antes de ofrecer la declaración S. La
audibilidad y las condiciones físicas de un futuro intento siguen pendientes
de revisión. R4 y los demás rechazos permanecen conservados. C04–C06 siguen
reservadas.

Pasaron 12 pruebas offline de revisión, presentación, teclado y patrones de
sonido. La proyección y sus referencias por hash quedaron en
`results/local/preparacion-devrep-r5-N01/`.
