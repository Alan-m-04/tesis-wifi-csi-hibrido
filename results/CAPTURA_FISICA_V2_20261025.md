# Único intento físico controlled_dual_v2 — 25 de octubre de 2026

**Adquisición terminada, ambos puertos cerrados y sesión global rechazada.** La integridad registrada, las filas completas y la parada pasan en ambos RX; los residuos iniciales impiden aprobar la sesión completa. Se conservaron todos los bytes leídos y metadatos. Evidencia resumida: [resultados, tiempos y hashes](CAPTURA_FISICA_V2_20261025.validacion.json).

## Autorización nueva, plan y preflight

Se ejecutó una sola vez el código revisado de `7aaaa8a6af429753c1036c3d47de6705469587c8`, con autorización explícita nueva del usuario, condicionada a identidades correctas. El plan local nuevo es `config/captura_dual_v2_30s_intento01.local.json`; su copia inmutable y los registros de autorización están en `results/local/control-captura-dual-v2-20261025-intento01/`. La autorización quedó consumida en un registro nuevo al finalizar. No se reutilizó el plan consumido, directorio o permiso de v1.

El usuario confirmó estar solo en su cuarto, sentado y quieto frente a la laptop, un RX a cada lado y TX-01 a algo más de 2 m, alimentado por cargador de pared; ambos RX por USB a Ubuntu. Es una declaración actual del operador, no una medición ambiental ni una validación instrumentada de presencia.

| Rol | Serie USB verificada | Nodo resuelto | Acceso efectivo |
|---|---|---|---|
| RX-01 | 5C93199744 | /dev/ttyACM1 | Lectura y escritura |
| RX-02 | 5C93200689 | /dev/ttyACM0 | Lectura y escritura |

El preflight verificó VID/PID 1a86:55d3, bus USB, rutas by-id y dos nodos distintos. Se revalidó antes de cada apertura; postflight confirmó ambas identidades. El proceso ejecutor tenía dialout activo y ambos nodos eran root:dialout 0660. `fuser` no informó procesos antes ni después (retorno 1, stdout/stderr vacíos). No se abrió TX-01, flasheó ni modificó firmware; ESP-IDF v5.4 se mantiene.

## Resultados separados

| Evaluación | RX-01 | RX-02 |
|---|---|---|
| Integridad de lo registrado | Aceptada | Aceptada |
| Calidad de las filas completas | Aceptada | Aceptada |
| Calidad de parada v2 | Aceptada: LF | Aceptada: LF |
| Calidad global por receptor | Rechazada | Rechazada |
| Filas completas totales | 147 | 147 |
| Filas dentro de los 30 s nominales | 147 | 147 |
| Filas de preámbulo / posteriores al deadline | 0 / 0 | 0 / 0 |
| Bytes brutos / lecturas no vacías | 130321 / 2125 | 131945 / 2155 |
| Bytes de finalización adicional | 0 | 0 |
| Cola final sin LF | 0 bytes | 0 bytes |
| RSSI observado | −46 a −44 dBm | −53 a −48 dBm |
| Callbacks completos | 0–146 | 0–146 |

La integridad aceptada significa hashes/tamaños, concordancia bruto/CSV/resumen y ledgers contiguos con marcas congruentes, además de metadatos v2 válidos. No acredita ausencia de pérdidas antes de `read()` ni una captura perfecta del cable. Las filas completas pasan el formato y perfil documentado de 256 escalares; no hay filas completas malformadas, huecos entre callbacks completos, errores de arranque reconocidos, descartes locales incrementados ni reinicios posteriores al primer dato. No se infiere pérdida RF ni precisión de presencia a partir de estos conteos.

La sesión comenzó a las 20:11:44.505716 UTC (15:11:44.505716, Ecuador) y acabó a las 20:12:14.553486 UTC. La envolvente real fue 30.047753992 s, incluidas apertura y cierre. La ventana común monotónica [4071668847309, 4101668847309) ns fue exactamente 30 s. Se aplicó únicamente el límite revisado de deadline + 250 ms / 65536 bytes adicionales por RX.

Ambos lectores ya estaban en un límite LF al detectar el deadline, así que `completion_started_ns=null` y `completion_bytes=0`: **esta sesión no necesitó la rama de finalización de una línea pendiente**. RX-01 registró parada a 4101669519707 ns (+0.672398 ms respecto del deadline), RX-02 a 4101669253236 ns (+0.405927 ms). Los últimos datos retornaron 33.756321 y 30.701974 ms antes del límite, respectivamente; el ledger no registra las lecturas vacías posteriores. No se atribuyen bytes o filas a instantes anteriores a los realmente registrados.

Se juntaron ambos lectores antes de los eventos de cierre por receptor. El proceso de adquisición terminó, sin excepción serie registrada. El comando de adquisición y el analizador devolvieron 1 por rechazo de calidad, no por permiso denegado ni fallo de apertura. No se reintentó.

## Residuos iniciales conservados

RX-01 comienza con `0x00` seguido de texto ROM en la misma línea física: bytes [0,27), línea 1. La primera lectura devolvió ese byte; las dos siguientes completaron ROM y CRLF. El auditor registra `embedded_boot_lines=[1]`.

RX-02 conserva dos fragmentos que empiezan por coma y carecen de encabezado CSI completo: [0,44) y [44,364), líneas 1 y 2. Ambos llegaron en la primera lectura de 364 bytes, antes de los mensajes ROM posteriores. El auditor registra `orphan_fragment_lines=[1,2]`. No se convirtieron en muestras ni se completaron matrices a partir de ellos. Sus longitudes, offsets y SHA-256 están en el resumen; los bytes íntegros siguen en el bruto local.

La causa de esos residuos y del arranque observado sigue indeterminada. No hay traza anterior a abrir/configurar ni medición eléctrica que permita atribuirlos automáticamente a WiFi, firmware, DTR/RTS o una placa. La supresión del flush se registró una vez por apertura, preservando estos bytes. Terminar en LF no elimina el rechazo del inicio.

## Comparación con v1: sesiones independientes

Se volvió a auditar v1 y el resultado coincide exactamente con su `quality.json` original. No se concatenaron ni recortaron sesiones, no se trasladaron timestamps y no se cambió su rechazo.

| Resultado | v1 anterior, RX-01 / RX-02 | v2 actual, RX-01 / RX-02 |
|---|---|---|
| Filas completas dentro de 30 s | 145 / 146 | 147 / 147 |
| Integridad registrada | Aceptada / aceptada | Aceptada / aceptada |
| Calidad de filas completas | Aceptada / aceptada | Aceptada / aceptada |
| Final de sesión | Colas de 129 / 129 bytes | LF, colas de 0 / 0 bytes |
| Residuos iniciales | ROM pegada en ambos RX | ROM pegada RX-01; fragmentos huérfanos RX-02 |
| Calidad global | Rechazada | Rechazada |

v1 no tenía el contrato de parada acotada de v2. La ausencia de cola en este intento es un hecho observado; **no demuestra una mejora RF ni que la extensión de v2 haya reparado una línea física**, porque no se utilizó ninguna lectura adicional. La rama de finalización pendiente sigue respaldada por las pruebas PTY anteriores, no ejercitada con hardware por esta sesión. Las diferencias de filas/RSSI entre sesiones no son una evaluación causal ni una campaña de presencia.

## Auditoría independiente, visualización y preservación

La carpeta nueva de adquisición es `results/local/captura-dual-v2-30s-20261025-intento01/`; el análisis separado está en `results/local/analisis-dual-v2-30s-20261025-intento01/`. Se comprobaron los 15 archivos del bundle por tamaño y SHA-256. La auditoría independiente reproduce exactamente la de adquisición y confirma postflight. Los 86 archivos fijados antes de abrir —fuentes, firmware, planes y registros anteriores incluidos— siguen idénticos.

La integridad permitió exportar `visualization/index.html`, con **«captura dual controlada v2 con validación estricta rechazada»**. Las nueve copias de captura/ledgers coinciden por hash con el manifiesto. Se verificaron las cuatro vistas RX/LTF y el selector de filas en Firefox: 147 filas, límite 146, 147 dentro del intervalo y cero después. Se inspeccionó la imagen RX-02/HT-LTF. RuView y Node fijados se ejecutaron únicamente con buffers; exportación y navegador dentro de Bubblewrap sin acceso a UART físicos. El control de Firefox escuchó solo localhost dentro de una red privada; sin HTTP ni UDP CSI.

No se modificó código ni se repitieron las 155 pruebas de integración: sus fuentes revisadas coinciden por hash con las ejecutadas aquí. La verificación de esta entrega comprende la adquisición real, auditoría independiente, hashes/ledgers, exportación y cuatro vistas del navegador. No hubo entrenamiento, aprobación de ventana derivada ni modificación de criterios. Cualquier otra adquisición necesita una autorización nueva.
