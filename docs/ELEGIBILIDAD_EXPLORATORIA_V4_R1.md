# Contrato v4: elegibilidad exploratoria, revisión 1

Definido antes del código desde `1f974b0`, el 1 de noviembre de 2026. Selección
explícita: `eligibility_revision=v4-exploratory-1`, junto a
`line_policy_revision=v4-startup-sequence-1`. Ausencia de selección conserva
`v4-connection-strict-1` y todos los resultados anteriores. Revisiones desconocidas
o combinaciones distintas se rechazan. No se migran bundles históricos.

## Cuatro resultados independientes

| Resultado | Significado |
|---|---|
| Conexión completa | Todos los bytes y motivos de rechazo. Un preámbulo anómalo mantiene `connection.quality_ok=false`; `windows[].eligible` sigue siendo el criterio estricto anterior. |
| Preámbulo | Prefijos completos [0, fin) por RX, hashes, offsets, líneas y tiempos. Estado anómalo/no interpretado cuando corresponde; nunca se declara CSI válido a un byte desconocido. |
| Ventanas prospectivas | T0/T1 irrevocables, filas incluidas, cobertura, calidad y etiqueta declarada. No se seleccionan intervalos retrospectivos para aprobar. |
| Elegibilidad exploratoria | Resultado adicional por ventana, reservado a esta revisión. El reductor produce candidatas pendientes; solo el auditor puede confirmar elegibilidad con todas las obligaciones verificadas. |

El preámbulo termina en la decisión de disponibilidad inicial y conserva todos
los bytes recibidos hasta entonces, incluidos arranque y filas de preparación.
Ninguno de esos bytes se reutiliza como CSI de ventana. Los brutos permanecen
append-only; el índice del preámbulo no los recorta o sobrescribe. Los motivos
de formato anteriores a READY y logs no interpretados se conservan como anomalías,
sin convertirlos en excepciones genéricas de texto. El tratamiento de líneas
posteriores a READY sigue siendo exactamente el de la política de arranque revisada.

## Disponibilidad y fronteras

1. READY estricto por RX y los dos retornos de `app_main()`, con el orden revisado,
   dentro de los 10 s originales. Sniffer y retorno conservan sus límites exactos.
2. Al completar ambos retornos se fija una barrera de procesamiento monotónica,
   índices de lectura y offsets conservadores al final de los chunks ya recibidos.
   Se vacían ambas rachas. Las tres filas iniciales nuevas de cada RX deben empezar
   en lecturas posteriores a esa barrera y con reloj de inicio no anterior a ella.
   Filas del mismo chunk que el último retorno no prueban ser nuevas.
3. No se declara disponibilidad inicial ni gate de slot con una línea pendiente
   sin LF en ningún RX. El presupuesto de disponibilidad no se amplía. Los slots
   conservan sus tres filas nuevas, demora, 30 s y cobertura originales.
4. Para toda anomalía se conserva su intervalo conservador: desde el inicio de
   la primera lectura que la toca hasta el máximo de retorno y procesamiento.
   Una cola pendiente tiene extremo superior desconocido. Falta/incoherencia de
   tiempos significa ubicación desconocida, nunca exclusión por suposición.
5. Para la ventana [T0,T1), una anomalía solo queda demostrablemente fuera si
   `fin < T0` o `inicio >= T1`. Contacto con T0, cruce de fronteras, publicación
   tardía o imposibilidad de localizarla fuera impiden elegibilidad. Una fila
   incluida debe además estar procesada antes de T1.
6. En T0 se sella también la frontera de bytes/lecturas de cada RX. La cobertura
   exploratoria solo cuenta filas de lecturas posteriores, fuera de esos chunks.
   No reutiliza las filas que eligieron T0 aun si un reloj sintético repite el mismo
   nanosegundo. Se vuelven a exigir los mismos mínimos de filas/bins/gaps sobre
   ese conjunto conservador, sin cambiar el perfil CSI o bajar los umbrales.

No se atribuyen tiempos RF o una época física de arranque a relojes host.
Resets, errores, CSI incorrecto, discontinuidades, texto no exceptuado después de
READY o pérdida de disponibilidad siguen suspendiendo sin rearmar. Esta revisión
es conservadora: cualquier suspensión en la conexión revoca sus candidatas
exploratorias, incluso si el fallo llegó después de una ventana completa.

## Obligaciones y auditoría

Se requieren ventana completa y sin motivos, cobertura piloto original, etiqueta
declarada, ambos cierres confirmados y ausencia de colas. La etiqueta sigue siendo
declaración del operador, no observación instrumental. El auditor exige también:

- manifiesto, referencias a todos los bytes, hashes, replay de operaciones,
  eventos, resumen y recibo de cierre correctos;
- concordancia explícita de revisión y fuentes en procedencia, sin seleccionar
  la revisión por el contenido del bruto;
- identidades by-id, serial, VID/PID, bus y nodos distintos, vinculadas en las
  operaciones de apertura al fd comprobado y a la procedencia del transporte;
- política UART de almacenamiento intacta, observación inicial >=100 MiB y
  observaciones de presupuesto/reserva durante operación y antes de finalizar,
  sin fallo de almacenamiento, y tamaño real del bundle dentro del límite.

Las comprobaciones de identidad y almacenamiento se registran solo en la revisión
nueva; no se inventan pruebas para bundles antiguos. Ausencia de evidencia
obligatoria impide certificación. Los ensayos con serial dobles/PTY siguen siendo
evidencia sintética, aunque pasen todas las comprobaciones del arnés. Un PTY puro
sin esas pruebas de identidad/presupuesto puede generar candidatas, no certificarlas.
La auditoría comprueba coherencia de registros, no firma criptográfica del operador
ni ausencia de consumo concurrente de disco, transitorios o latencia física.

La elegibilidad exploratoria **no** declara conforme la conexión, presencia
validada o autorización para calibración, entrenamiento o producción. Esos usos
permanecen `not_authorized_by_this_revision`. No cambia el perfil CSI, las
políticas anteriores, firmware, fuentes físicas, rechazos o autorizaciones.

Tras pasar las pruebas se preparará un plan E/S nuevo exclusivamente para revisión,
con ambas revisiones explícitas y campos ambientales pendientes de confirmar.
Preparar ese archivo no crea autorización ni habilita apertura; no se ejecuta
preflight físico ni adquisición durante esta entrega.
