# Avance verificable de tesis — corte 13/11/2026

Este informe relaciona el avance técnico con los ocho hitos referenciales
solicitados para el Anexo G. Último seguimiento indicado por el solicitante:
**12/11/2026**; último plazo indicado: **13/11/2026**. Son referencias de
seguimiento, no fechas atribuidas automáticamente a commits o adquisiciones.

## Fuente del seguimiento y porcentajes

La copia privada disponible `CT_ANEXO_G_TIC_DIRECTOR.docx` identifica esta tesis
y menciona nodos ESP32-S3, captura, visualización e integridad CSI y SQLite.
Sus celdas de fecha, plazo y porcentaje están vacías y señala revisión con el
director pendiente. No se encontró una versión con el último seguimiento
completo ni una sesión documental conectada. El documento no se publica.
El anexo local que sí tiene porcentajes pertenece a otra tesis y se excluyó
como fuente.

Las fechas de la matriz proceden de la instrucción del solicitante; los
porcentajes quedan **no verificados (NV)**. NV no significa 0 %. Falta cotejar
la versión vigente y transcribir sus porcentajes y plazos por fila como
referencias de seguimiento, sin convertirlos en exactitud experimental ni
aprobación del tutor. No se extrapolan cifras de informes quincenales o del
número de pruebas aprobadas.

## Matriz de hitos

| Fecha referencial del Anexo G | % Anexo G | Hito y trabajo comprobado | Evidencia existente | Qué sigue pendiente / estado verificable |
| --- | --- | --- | --- | --- |
| 07/09/2026 | NV | Anteproyecto, alcance y caso de uso para MIPYMES de Riobamba. El repositorio declara el sistema híbrido CSI/Edge AI con procesamiento local; presencia es el primer hito y no el alcance completo. | [Instrucciones del proyecto](../AGENTS.md) y [estado histórico](ESTADO_INICIAL.md). | **Aprobación y entrega del hito académico no verificadas** mediante evidencia pública fechada. Cotejar el anteproyecto aprobado en privado y documentar criterios de aceptación, escenario y necesidades de la MIPYME sin publicar firmas ni datos personales. |
| 21/09/2026 | NV | Capítulo I: problema, justificación y objetivos aprobados, según el hito solicitado. Se conserva el alcance declarado en las instrucciones del repositorio. | [Alcance conservado](../AGENTS.md). No se encontró acta pública, versión fechada o revisión del tutor que acredite esa aprobación. | **No verificado** el capítulo aprobado en esa fecha. Falta cotejar la versión académica privada y registrar una constancia publicable de revisión. El código no acredita aprobación del escrito. |
| 05/10/2026 | NV | Capítulo II: fundamentos WiFi CSI, sensado pasivo y Edge AI, según el hito solicitado. Hay documentación técnica posterior de formatos CSI, compatibilidad y detector. | [Auditoría CSI/RuView](COMPATIBILIDAD_CSI_RUVIEW.md) y [selección y límites de presencia](DETECTOR_PRESENCIA_RUVIEW.md). Son documentos técnicos posteriores, no el Capítulo II fechado. | **No verificada** la entrega o aprobación del Capítulo II al 05/10. Cotejar bibliografía y redacción privadas; distinguir fundamentos teóricos de implementación y resultados. |
| 14/10/2026 | NV | Revisión de I/II: marco teórico general en II; implementación y pruebas en III, como criterio indicado por el solicitante. La documentación técnica de SQLite ya se organiza para III. | [Material técnico para Capítulo III](CAPITULO_3_BASE_DATOS_CSI.md). No hay evidencia pública de la revisión académica del 14/10. | **No verificada** la revisión de los capítulos I/II. Confirmar con el director la distribución y cierre de correcciones; conservar en III procedimientos, ensayos, resultados y límites, sin presentar este material como capítulo aprobado. |
| 24/10/2026 | NV | Prototipo ESP32-S3: fuentes TX-01/RX-01/RX-02 incorporadas y compiladas con ESP-IDF v5.4. Referencia física dual histórica de **60 s**, con **292/291 filas válidas**. | [Inventario y referencia de 60 s](INVENTARIO_BASE.md), [40 pruebas y tres builds](../results/BASE_VERIFICADA.md), [manifiesto de datos](../data/README.md), commits [8c54a1f](https://github.com/Alan-m-04/tesis-wifi-csi-hibrido/commit/8c54a1f) y [74d612a](https://github.com/Alan-m-04/tesis-wifi-csi-hibrido/commit/74d612a). | **Verificado técnicamente con límites.** RX-01 conserva rechazo estricto por una línea malformada inicial; RX-02 tiene aceptación registrada en esa referencia. No demuestra campaña válida, etiquetas de ocupación ni identidad del binario instalado. No confundir con el diagnóstico dual de 60 s del 03/11, de 171/296 filas. |
| 25/10/2026 | NV | Captura dual v2: **147/147 filas en 30 s nominales**, integridad y filas completas conformes, parada LF, ambos puertos cerrados y cero cola. Sesión global **rechazada por residuos iniciales**; v1 conserva 145/146 filas y colas de 129 bytes por RX. | [Informe físico v2](../results/CAPTURA_FISICA_V2_20261025.md), [validación y hashes](../results/CAPTURA_FISICA_V2_20261025.validacion.json), [v1 preservada](../results/CAPTURA_DUAL_POST_REINICIO.md), commit [cb504c4](https://github.com/Alan-m-04/tesis-wifi-csi-hibrido/commit/cb504c4). | **Verificado como intento rechazado.** Falta resolver el origen de residuos de arranque y validar datos elegibles sin relajar criterios. La extensión de finalización v2 no se ejercitó en ese intento físico: cero bytes adicionales. No demuestra mejora RF ni presencia. |
| 09/11/2026 | NV | Visualización histórica y diagnóstico en vivo de RX-02. La reproducción C01/C03 tiene evidencia del 09/11; el diagnóstico del visor se ejecutó realmente el **10/11** y conservó **1.192 muestras en aproximadamente 240 s**, integridad, replay y cierre. | [Reproducción histórica](DEMO_REPRODUCCION_OFFLINE.md), [revisión del visor](REVISION_VISOR_FISICO_RX02.md), [informe original del diagnóstico](../results/RX02_DIAG_VISOR_240S_R1.md), commits [reproducción incluida en adf2618](https://github.com/Alan-m-04/tesis-wifi-csi-hibrido/commit/adf2618249927ff499489b325f48df2520a74f57) (origen local `36eaa0d`) y [instantánea adf2618](https://github.com/Alan-m-04/tesis-wifi-csi-hibrido/commit/adf2618249927ff499489b325f48df2520a74f57) (origen local `952365c`). | **Verificado como diagnóstico histórico; calidad estricta rechazada por preámbulo.** Cero ventanas/etiquetas E/S, sin calibración, entrenamiento o producción. No hay conteo persistido de filas efectivamente presentadas por el navegador ni confirmación humana de audibilidad; el buffer visual acotado no representa pérdidas del bruto. |
| 12/11/2026 | NV | Capítulo III: piloto SQLite sobre las 1.192 muestras históricas; CSV agregado e importación idempotente; vista `/sessions` de solo lectura. R5-N01 preparada y con informe local de integración offline. Los commits de SQLite/tablero son del **11/11** y la preparación R5 del **10/11**. | [SQLite](../results/BASE_DATOS_CSI_OFFLINE.md), [CSV agregado](../results/BASE_DATOS_CSI_PILOTO/RX02-DIAG-VISOR-240S-R1__RX-02.csv), [tablero](../results/VISTA_SQLITE_OFFLINE.md), [R5-N01](../results/DEVREP_R5_N01_INTEGRACION.md); commits [instantánea 10e3f55](https://github.com/Alan-m-04/tesis-wifi-csi-hibrido/commit/10e3f5538eab0d8a00bdbe6b888d420883f275db) (origen local `6f5ae46`), [instantánea 59166f8](https://github.com/Alan-m-04/tesis-wifi-csi-hibrido/commit/59166f80310c9e78d7cc71723b2425d064780878) (origen local `403e794`) y [instantánea 9f20714](https://github.com/Alan-m-04/tesis-wifi-csi-hibrido/commit/9f20714aab3e555488c5d9eab15a246188b97141) (origen local `c518d07`). | **Implementación y evidencia offline comprobadas; aprobación del capítulo no verificada.** Tablero: contratos HTTP en memoria y DOM simulado, revisión visual/HTTP real pendientes. R5: **ensayo guiado humano pendiente**; parte de las fuentes de integración sigue sin confirmar en la copia original y no se incorpora como código en esta actualización documental. No hay evidencia posterior de captura R5. |

## Diagnóstico RX-02: contraste con el informe original

El [informe de origen](../results/RX02_DIAG_VISOR_240S_R1.md), su JSON local de
consolidación y el piloto SQLite coinciden: **1.192 filas completas**, IDs
0–1.191 consecutivos, `queue_drops=0`, cero errores de continuidad del parser,
**1.003.914 bytes brutos** y cero cola final. Apertura a cierre confirmado:
**240,005564743 s**; primera a última fila host: **239,191988869 s**; cadencia
entre esos extremos: **4,979263752 Hz**. No son frecuencia RF ni prueba de
ausencia de pérdidas anteriores al callback.

Máximo hueco host **614,782902 ms**; máximo local **601,971 ms**. Hay un hueco
mayor de 500 ms y ninguno mayor de 1 s en ambos relojes. La causa no queda
identificada. El journal termina con **78 checkpoints**, secuencia durable
48.609 y cero bytes pendientes. Integridad, replay y cierre conformes no
anulan `format:RX-02` ×20 y `preamble_anomaly:RX-02` ×1: la conexión mantiene
su **rechazo de calidad estricta**.

El observador procesó las 1.192 filas, terminó sin atraso y conservó ocho en
su última instantánea. Las 1.184 expulsiones del buffer describen su rotación,
no una pérdida del registro ni un conteo de filas que el navegador dejó de
mostrar. La audibilidad humana no está registrada. Es un diagnóstico sin
condiciones E/S etiquetadas, no un resultado experimental de ocupación.

## SQLite, tablero y R5-N01

El [piloto SQLite](CAPITULO_3_BASE_DATOS_CSI.md) separa dispositivos, sesiones,
muestras, fuentes y validaciones. La segunda importación conserva conteos y
SHA-256; `integrity_check=ok`, sin errores de claves foráneas. SQLite y el
CSV agregado coinciden en duración, muestras, cadencia, huecos y rechazo.
La base local y los CSV por muestra no se publican. El CSV versionado tiene
una sola fila agregada de sesión/receptor.

Los resultados históricos registran **90 pruebas** del piloto y **60 Python
+ 3 contratos Node** de la vista. Las consultas usan `mode=ro` y
`query_only=ON`; la vista muestra **RECHAZADA · PREÁMBULO**, separada de
integridad/replay/cierre. No hay verificación visual de la vista SQLite:
el intento de socket recibió EPERM y Firefox no completó el arranque. Tampoco
se atribuye aislamiento Bubblewrap a las pruebas directas que no pudieron
crear namespaces. La revisión humana del tablero sigue pendiente.

R5-N01 tiene preparación confirmada en `6f5ae46`. El
[informe local de integración](../results/DEVREP_R5_N01_INTEGRACION.md) y su
[resultado estructurado](../results/DEVREP_R5_N01_INTEGRACION.validacion.json)
registran **229 pruebas offline**, incluidas **42 específicas**, sin fallos,
errores u omisiones. Se contrastaron 53 hashes de artefactos y fuentes con
esa evidencia. Algunas fuentes son archivos locales todavía sin confirmar:
se publica el informe documental, sin atribuir a `6f5ae46`, `403e794` o
`c518d07` una implementación R5 que esos commits no contienen. Los comandos
del informe R5 requieren esas fuentes locales y no se garantizan desde una
copia limpia de esta rama.

No se encontró salida de adquisición R5-N01 ni evidencia que cierre su
práctica interactiva. Quedan pendientes ensayo humano, audibilidad,
condiciones actuales y, antes de cualquier intento físico futuro, preflight
y autorización nuevos. Esta publicación no ejecuta esos pasos.

## Alcance experimental pendiente

- **Edge AI con datos reales:** obtener sesiones elegibles y repetidas con
  verdad terreno vacío/ocupado, condiciones y calidad trazables; fijar
  calibración y evaluación por sesiones independientes, sin ajustar con
  reserva; verificar pesos o anclas, frecuencia, LTF, escala y geometría del
  componente elegido y medir errores con datos reales. La equivalencia
  sintética del adaptador o una comparación descriptiva C01/C03 no valida
  sensibilidad, especificidad ni generalización física.
- **Zonas:** definir geometría, ubicación de nodos, etiquetas espaciales y
  protocolo para distinguir zonas; medir confusiones con verdad terreno.
  Un receptor o una curva RSSI no acredita localización ni conteo de personas.
- **Mapas de calor:** definir coordenadas, agregación temporal, cobertura y
  contraste de ocupación por zona; evaluar el mapa con datos reales, sin
  inventar posiciones o rellenar mediciones ausentes.
- **MIPYME:** seleccionar y acordar un escenario real de Riobamba, justificar
  topología/alimentación y comunicaciones o Mesh que requiera el diseño,
  fijar privacidad, duración y criterios con el establecimiento; desplegar y
  evaluar el sistema completo. La demo local y el tablero histórico no son
  evidencia de una prueba en una MIPYME.
- **Escrito y seguimiento:** cotejar capítulos y aprobación en privado,
  cerrar correcciones con el tutor y recuperar los porcentajes/plazos de la
  versión vigente del Anexo G. No se declara terminada la tesis.

## Revisión Git, preservación y publicación

Al comenzar, `main` local y remoto seguían en
[`72ccb0a`](https://github.com/Alan-m-04/tesis-wifi-csi-hibrido/commit/72ccb0a),
estructura inicial. La rama remota `feat/backend-uart-presencia-v4` seguía en
[`81cdd20`](https://github.com/Alan-m-04/tesis-wifi-csi-hibrido/commit/81cdd20),
con [C03/C01](../results/RX02_C03_C01.md) publicados. La consulta del conector
GitHub y `git ls-remote --heads` coincidieron; ese estado no había cambiado.

La rama local activa era `feat/demo-offline-operacion-20261109`, HEAD
`c518d079e9882158f4ad63b8bf6c620bf47bd67a`, con 34 commits posteriores al
backend remoto. Esta copia **sí contiene** `952365c`, `6f5ae46`, `403e794` y
`c518d07`: no hace falta otra copia de Ubuntu para recuperar esos commits.
Existen modificaciones de README/estado/guía R5/prueba R3 y archivos sin
seguimiento de R1/R2/R5. Se conservaron en la copia original; el trabajo de
documentación se realiza en otro worktree y en
`docs/avance-anexo-g-2026-11-13`, con el contenido de `c518d07`.

Se revisaron 509 blobs distintos del historial a publicar, sin documentos
académicos, bases locales, brutos reservados ni coincidencias de los patrones
de credenciales y datos personales inspeccionados. Los informes R5 se copian
como evidencia documental verificada; el código sin confirmar permanece
local. El [registro de comprobación](../results/VERIFICACION_AVANCE_ANEXO_G_2026-11-13.json)
fija hashes, métricas y límites. Los conteos de pruebas citados son resultados
históricos contrastados, no nuevas pruebas físicas realizadas en este corte.

**C04–C06 siguen cerradas y reservadas, sin acceder a sus contenidos.** Se
conservan rechazos, particiones y originales; sin UART, adquisición, flasheo,
calibración o entrenamiento durante esta actualización. No se incluyen
documentos académicos privados, identificaciones, contactos, credenciales,
SQLite local, registros por muestra ni datos brutos reservados.

## Correspondencia entre origen local y publicación

Tras un reinicio del entorno, Git dejó de resolver `github.com`; el conector
GitHub siguió disponible. Se publicaron instantáneas con **árboles Git idénticos**
a los originales. Cambian los hashes de commit por su nueva fecha y ascendencia;
los hashes locales se conservan como procedencia, sin enlazarlos como si esos
objetos originales se hubieran subido. La primera instantánea incorpora el
avance posterior al backend remoto; las siguientes separan R5, SQLite y tablero.
El historial original de 34 commits posteriores a `81cdd20` sigue en la copia
local. No faltan allí los commits recientes; falta publicar ese historial con
sus hashes originales cuando Git vuelva a tener conectividad.

| Commit local de origen | Commit público de la instantánea | Árbol idéntico |
| --- | --- | --- |
| `952365c7246d76103c846777b7fe8a44e965fb53` | [adf2618](https://github.com/Alan-m-04/tesis-wifi-csi-hibrido/commit/adf2618249927ff499489b325f48df2520a74f57) | `1011f0813b058f2d03cf91aaf3a4406d997e1cc1` |
| `6f5ae46d8aa18b9a95f4af9aa5eb844f79ec6113` | [10e3f55](https://github.com/Alan-m-04/tesis-wifi-csi-hibrido/commit/10e3f5538eab0d8a00bdbe6b888d420883f275db) | `b5cb11aaba2775ceeb075d2ed1a0b4fcc5089acb` |
| `403e7942e667bad26d5852d8510daa2f9720829b` | [59166f8](https://github.com/Alan-m-04/tesis-wifi-csi-hibrido/commit/59166f80310c9e78d7cc71723b2425d064780878) | `3ccbd20612930c013291fef80395c2168e85a8f5` |
| `c518d079e9882158f4ad63b8bf6c620bf47bd67a` | [9f20714](https://github.com/Alan-m-04/tesis-wifi-csi-hibrido/commit/9f20714aab3e555488c5d9eab15a246188b97141) | `1de436c90ec4bc5595011ebaa8f6abd021f01afb` |
