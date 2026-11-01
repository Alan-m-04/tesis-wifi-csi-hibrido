# Política de líneas v4: retorno inmediato de app_main, revisión 1

Contrato del 1 de noviembre de 2026, definido antes de integrar la corrección.
Complementa el protocolo v4 publicado; no modifica sus textos históricos ni
la gramática compartida de v1/v2/v3. Diagnóstico y evidencia original en
[DIAGNOSTICO_V4_POST_READY](../results/DIAGNOSTICO_V4_POST_READY.md).

La selección se hace exclusivamente mediante `line_policy_revision` en el plan:

| Valor | Tratamiento |
|---|---|
| Campo ausente o `v4-strict-post-ready-1` | Regla histórica: cualquier `info` posterior a READY suspende. |
| `v4-app-main-return-1` | Una única excepción contextual por RX, descrita abajo. |
| Otro valor, incluido `null` | Plan rechazado antes de crear recursos. |

Las plantillas existentes conservan la selección histórica. No se genera un
plan físico ni una autorización al integrar esta política. Para una futura
revisión debe seleccionarse explícitamente la nueva revisión en un plan nuevo.

Solo puede exceptuarse una línea completa de bytes coincidente con:

```text
I ([0-9]+) main_task: Returned from app_main()
```

Los paréntesis alrededor del entero y de `app_main()` son literales. El entero
usa dígitos ASCII. El terminador debe ser LF o CRLF; no se admiten ANSI, espacios
adicionales, otros niveles/tags, prefijos binarios, sufijos ni texto añadido.
No se compara el número impreso con el reloj host ni se deduce de él un reset.

Además deben cumplirse todas estas condiciones al procesar la línea:

1. Es la línea inmediatamente siguiente al primer READY estricto del mismo RX.
   Una línea vacía o cabecera interpuesta también impide la excepción.
2. Ese RX todavía no ha emitido ninguna fila CSI válida, ni siquiera antes de
   READY. La disponibilidad inicial de la conexión aún no existe.
3. El reloj de procesamiento host es estrictamente anterior a `begin + 10 s`.
   No hay suspensión previa, solicitud de cierre ni cierre iniciado.
4. La línea conserva clasificación `info`; se anota el patrón y, si se admite,
   la revisión aplicada en el evento de línea. No cuenta como CSI ni como READY.

La adyacencia al primer READY limita la excepción a una vez por RX. Un
duplicado, retorno posterior a CSI o cualquier otro texto posterior a READY
continúa suspendiendo. Errores, resets, READY conflictivo/duplicado, cambios
del perfil CSI, discontinuidades, silencio y colas incompletas conservan su
tratamiento. Se mantienen tres filas frescas por RX, todos los plazos,
fronteras, cobertura, etiquetas, cierres y prohibición de reintentos.

Los motivos de formato anteriores a READY permanecen en el resultado de
conexión. La excepción no borra residuos ni hace conforme un intento rechazado.
La evidencia solo verifica el retorno observado de RX-02; en RX-01 las fuentes
permiten ese retorno, pero su orden de inicialización difiere. Si allí aparece
otra línea interpuesta, esta política no la acepta. El binario instalado sigue
sin estar atestado; esta política no verifica firmware físico.

Cada bundle nuevo registra la revisión efectiva en `provenance.json`. Para la
nueva excepción también se registra en el resumen. El auditor selecciona la
regla desde el plan conservado y verifica la concordancia de procedencia. La
ausencia histórica del campo selecciona siempre la regla estricta y conserva
eventos/resúmenes reproducibles byte por byte en sus valores JSON. Una revisión
nueva sin procedencia explícita o una discrepancia se rechazan. Rehashear un
manifiesto no evita estas comprobaciones ni las del replay.

El intento V4-C01 original nunca se migra a esta revisión. Sus bytes, operaciones,
rechazo, recibo de cierre y autorización consumida permanecen intactos.
