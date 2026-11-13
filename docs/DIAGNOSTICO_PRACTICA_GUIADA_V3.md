# Práctica guiada: causas de salida y avisos exclusivos del ejercicio

La causa exacta de la ejecución manual anterior no puede recuperarse de los
archivos disponibles: la versión v2 no guardaba sus entradas ni un resultado
detallado. El transcript conservado corresponde a la prueba automática anterior,
que terminó correctamente; no es la sesión del operador. Se solicitó el último
mensaje de su terminal para identificar esa ejecución, sin atribuirle una causa
no observada.

La revisión del código sí identifica dos problemas: agrupaba cancelación,
incertidumbre y formato inválido en `practice_abort_uncertainty_or_invalid_input`,
y algunas salidas iniciales/excepciones devolvían código 1 sin explicación.
Además reutilizaba letreros de adquisición, como «INTENTO DETENIDO» y «CIERRE
CONFIRMADO», aunque no existía UART en la práctica.

## Revisión v3 independiente

Se añade `src/devrep_practice_diagnostics_v3.py` y
`tools/practica_guiada_devrep_v3.py`. Las versiones anteriores permanecen intactas.
Se reutiliza la cronología de simulación v2, sin cambiar tiempos, políticas,
validadores o ejecutores experimentales. Los mensajes se clasifican así:

| Causa | Mensaje principal | Código de salida de práctica |
| --- | --- | --- |
| Formato/ID incorrectos, línea vacía, `yes` prematuro o motivo ausente | **ENTRADA INVÁLIDA EN PRÁCTICA**, con explicación y orden esperada | 2 |
| `declare PRACTICA-GUIADA-… uncertain MOTIVO` | **PRÁCTICA DETENIDA POR INCERTIDUMBRE**, con el motivo literal | 3 |
| `abort`, Ctrl-C o entrada cerrada/EOF | **PRÁCTICA CANCELADA**, con origen indicado | 1 |
| Declaración no recibida dentro del plazo simulado | **PLAZO DE PRÁCTICA VENCIDO**, con fase y límite A+210/A+420 s | 4 |
| Aviso sonoro no reproducido o `aplay` ausente | **FALLO DE AUDIO EN PRÁCTICA** | 5 |
| Error de terminal/entrada/salida | **ERROR DE INTERFAZ DE PRÁCTICA** | 6 |
| Ambas entradas reconocidas | **EJERCICIO COMPLETADO**, exclusivamente de práctica | 0 |

Un ID físico como `RX02-DEVREP-R4-N01-E` en este programa produce una explicación
específica: pertenece a adquisición física y el ejercicio espera
`PRACTICA-GUIADA-E/S`. No se transmite a ningún dispositivo. `uncertain` sin motivo
es formato incompleto, y una declaración tardía no sustituye el motivo original
de vencimiento. Una línea sin Enter permanece sin enviar; EOF no la convierte
en una declaración aceptada. No hay aceptación implícita de `yes`.

## Avisos de práctica separados

Toda la presentación está identificada con **[PRÁCTICA]**. Conserva las órdenes
de salir/permanecer fuera/regresar/sentarse para ensayar, pero dice **FIN SIMULADO**
y **aviso final simulado**. No anuncia cierre de RX-02, conexión confirmada,
rechazo físico o conservación de un bundle de adquisición. Las cancelaciones y
errores de entrada del ejercicio no emiten la alarma física de ocho tonos.
Los cinco avisos de ensayo satisfactorio mantienen los patrones de aprendizaje;
ningún sonido, criterio o umbral de adquisición física se modifica.

## Uso y diagnóstico persistente

```bash
cd /home/alan-monar/tesis-wifi-csi-hibrido
.venv/bin/python -B tools/practica_guiada_devrep_v3.py
```

Escribir `practicar` y pulsar Enter inicia el reloj simulado. Las declaraciones
mostradas por el ejercicio son:

```text
declare PRACTICA-GUIADA-E yes
declare PRACTICA-GUIADA-S yes
```

Se envían separadamente cuando aparezcan sus prompts, tras cumplir las
indicaciones y oír los avisos. Para detener el ejercicio: `abort`; ante duda,
`declare PRACTICA-GUIADA-E uncertain MOTIVO` o su equivalente S.

Cada ejecución crea un directorio nuevo `results/local/practica-guiada-v3-…/`,
sin sobrescribir otro. Imprime su ruta y guarda `resultado-practica.json`, con
código, causa, fase, origen, orden esperada y texto aún sin enviar; además
`eventos-practica.jsonl` registra las órdenes recibidas y resultados de
reproducción por software. Son registros exclusivamente de práctica, con
`practice_only=true`, sin datos CSI o etiquetas experimentales. Los WAV del
ejercicio quedan en `audio-practica/`. La reproducción no acredita por sí sola
que el operador los oyó.

## Verificación y conservación

67 pruebas aprobadas, cero fallos/errores/omisiones: clasificación de causas,
arranque inválido en proceso real, `aplay` ausente, incertidumbre con/sin motivo,
abort/Ctrl-C/EOF, entrada sin Enter, vencimiento original, ID físico incorrecto,
registro persistente y finalización E/S. Incluyen regresiones de guía v2,
teclado y R4 con PTY propios. Los escenarios nuevos de diagnóstico usan audio
inyectado, sin reproducir sonido real; no se afirma audibilidad verificada.

Logs, demostraciones controladas y hashes en
`results/local/revision-causas-practica-v3-r1/`. Los 273 archivos protegidos,
incluidas fuentes y evidencias anteriores, se conservan idénticos. R4 permanece
rechazado, con E pendiente, cierre confirmado y autorización consumida.
No se abrió UART, consultó USB actual, cambió firmware, calibró, entrenó o
preparó otro identificador, plan, preflight o autorización de captura.
