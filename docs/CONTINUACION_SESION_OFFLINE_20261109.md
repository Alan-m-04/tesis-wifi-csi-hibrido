# Sesión offline — continuación del 9 de noviembre de 2026

Rama: `feat/demo-offline-operacion-20261109`, creada desde `703cefd`.

## Revisión de procedencia del intento RX-02 de 240 s

El preflight original encontró a RX-02 por USB y aún incluía la declaración
previa de que las tres ESP estaban desconectadas. Se conserva el original y
se preparó una copia de condiciones que separa ambos hechos. El plan de la
revisión 2 utiliza `RX02-DIAG-VISOR-240S-R1` como `connection_id` y
`partition_group` en el bundle y en el replay. El comparador histórico exige
su propio ID. Los hashes históricos se cotejan con los archivos exactos de
la revisión archivada en Git y se verificó offline el diagnóstico histórico,
incluido su rechazo por preámbulo.

El informe local `results/local/preparacion-rx02-visor-240s-r1-revision-2/review-plan.json`
vincula el plan corregido con el SHA-256 del recibo original. La consulta de
metadatos nueva se hace desde Ubuntu y escribe en la carpeta de revisión 2.
El comando offline `--review-plan` permite comprobar el alcance antes de esa
consulta. La captura sigue sin autorización. [Comandos y alcance](REVISION_VISOR_FISICO_RX02.md).

## Preparación operativa del visor RX-02 de 240 s

`tools/visor_rx02_240s.py` integra la sesión diagnóstica de checkpoints, una
vista separada de solo lectura y el auditor nativo en otro proceso tras la
salida del capturador. El intento prospectivo queda ligado por `live_view`
al plan nativo, su procedencia, el preflight y una autorización única. Se
conserva el ID de contrato interno que exige el reductor histórico. Las
salidas de adquisición, vista y preparación se mantienen separadas.

Las pruebas offline usaron archivos fabricados y dobles de metadatos,
transporte y supervisor. El auditor nativo reprodujo en un intérprete
separado el bundle fabricado de 240 s y conservó el rechazo por preámbulo.
El visor observó las 1.200 filas inventadas con la cota de ocho y el cierre
solo se mostró confirmado tras la auditoría. Los arneses JS usaron DOM y
red simulados. Evidencia en `results/local/visor-rx02-240s-preparacion-offline-20261110-r1/`.

Estado de entrega: declaraciones actuales solicitadas en una consulta,
preflight para la terminal del operador y autorización física pendiente.
Al completar las condiciones se ejecutan `--preflight-only` y `--review`
según el documento operativo. Con el resultado de esa revisión se presenta
la ejecución y se solicita la autorización para un solo intento. Sin UART ni
captura durante la preparación. [Operación y preflight](REVISION_VISOR_FISICO_RX02.md).

## Revisión de memoria y propuesta RX-02 de 240 s

Se perfilaron el replay y la finalización de los registros ya existentes. Las
referencias de líneas, sus copias en eventos y las comprobaciones de espacio
crecen durante el servicio. El laboratorio añade sus propios medidores. El
mayor salto reproducido ocurre al materializar las 174.624 operaciones para
replay, con un pico aislado de 189.928 KiB. La estimación de espacio en la
finalización reconstruida alcanzó 46.820 KiB. El perfil del diagnóstico físico
histórico alcanzó 75.140 KiB durante su auditoría offline y conservó el rechazo
de calidad por preámbulo. Se conservaron las fuentes nativas y sus hashes.
[Evidencia, estructuras y límites](MEMORIA_ENSAYO_PTY_RX02.md).

La propuesta `RX02-DIAG-VISOR-240S-R1` fija rutas nuevas, una apertura, cierre
nativo, límites heredados, vista separada y auditoría posterior a la salida del
capturador. El descriptor y su comando son de revisión offline. La autorización
física sigue pendiente. Los perfiles y las comprobaciones quedaron en
`results/local/revision-memoria-visor-20261110-r1/`. Se preservaron originales,
rechazos, cambios ajenos y C04–C06. [Revisión de 240 s](REVISION_VISOR_FISICO_RX02.md).

## Continuación del 10 de noviembre de 2026

Se encontró el commit `37ce2e6` y la corrida de 900 s terminada antes del cierre
de Codex. Se auditó el bundle existente sin lanzar otro ensayo. El arnés pasó,
el auditor nativo confirmó replay, integridad y cierre del PTY, y los **4.500/4.500**
registros CSI se conservaron. El reloj del laboratorio midió 900,038 s y el
journal midió 899,982 s desde apertura hasta inicio de cierre. El p95 fue
238,67 ms hasta publicación y 1.668,00 ms hasta el consumidor lento. Este dejó
1.623 filas sin mostrar. El observador retuvo ocho filas como máximo. El RSS
nativo aumentó durante el servicio y su pico incluye la auditoría final.
[Informe con CPU, memoria, latencia y descartes](ENSAYO_SOSTENIDO_VISOR_CSI.md).

La integración con RX-02 quedó **solo para revisión documental**, reutilizando
el capturador diagnóstico y su auditor. Para avanzar se debe revisar la selección
de una salida diagnóstica nueva, el vínculo de procedencia/reloj y el alcance
del futuro observador. La autorización anterior sigue consumida. La prueba
humana de navegador continúa pendiente. [Propuesta y estado de revisión](REVISION_VISOR_FISICO_RX02.md).

Al retomar pasaron 49 pruebas Python seleccionadas y el arnés JS. La auditoría
y los logs quedaron en `results/local/visor-sostenido-auditoria-20261110-r1/`,
junto al inventario de preservación. Se conservaron 52 archivos con cambios
ajenos, 321 archivos protegidos y 41 archivos del ensayo previo. C04–C06 siguen
reservadas y sin abrir. No hubo preflight físico, UART, capturas físicas,
resets, flasheo, calibración, entrenamiento ni push.

## Entrega anterior: mediciones PTY e integración del observador

Código/pruebas: **`cf5ee3c`**. La documentación está en el commit posterior;
`git log -2 --oneline` muestra ambos. Sin push/merge. Se conservaron todos los
cambios ajenos y los originales; ningún UART físico fue abierto.

Se registró como **parcial** la declaración del operador de que el visor abre y
muestra LLTF52, RSSI y huecos sin rellenar. Todos los controles/estados y la
latencia de navegador todavía requieren revisión humana; no se afirma READY/CSI
físicos. Registro: `results/local/mediciones-live-pty-r1/comprobacion-parcial-operador.json`.

Se corrigió el rechazo erróneo de `storage_check` y se verificó el recorrido del
capturador completo `CheckpointRx02Session` con el backend PTY existente, su parser
y extracción LLTF52. Una constancia externa de reloj, ligada a hashes/ruta/boot,
permite observar ese laboratorio sintético sin modificar procedencia original.
No habilita planes ni fuentes físicas. C03/R4 solo se inspeccionaron, sin ejecutar
sus entradas físicas o reusar sus permisos.

Comparación vigente: seis ejecuciones de 8 s con orden alternado, baseline,
normal y consumidor lento. Las seis pasaron integridad/replay nativos, conservaron
40 filas/33 852 bytes por caso y una apertura/cierre sintéticos. El observador
recibió 40/40 en todos los casos; el consumidor normal, 40/40; el lento, 27/40,
con descartes visuales explícitos y originales intactos. Publicación normal p95
234–242 ms; consumidor p95 436–445 ms, desde lectura host.

Una ejecución normal adicional de 30 s recibió 150/150 filas y pasó auditorías.
El observador usó 3,84 % de un núcleo, máximo RSS 33 780 KiB e instantánea de
276 313 bytes; publicación p95 250,5 ms. Se midieron unos 17,1 MB de escrituras
lógicas del visor en 30 s: el archivo retenido es acotado, pero reemplazar toda
la instantánea tiene coste. No son medidas RF, TCP o render, ni garantizan carga
física o estabilidad prolongada. [Método, tabla y límites](MEDICIONES_OBSERVADOR_PTY.md).

Evidencia local en `results/local/mediciones-live-pty-r1/`: piloto y resultados
preliminares conservados; `comparacion-periodica-r2/` respeta el intervalo lento
también durante el drenaje final; `ventana-30s/` amplía la carga. Fuentes/entorno
quedan fijados con hashes en cada `measurement-plan.json`.

Pasaron **21 pruebas Python seleccionadas** y el arnés JS del visor; no se repitió
la suite completa. HTTP/render reales siguen fuera de esta medición. Los hashes
de 321 archivos protegidos y 52 con cambios ajenos permanecen intactos.

Comandos desde la raíz (las mediciones exigen una carpeta nueva):

```bash
.venv/bin/python -B tools/demo_csi_vivo.py --seconds 45
# Abrir http://127.0.0.1:8767/ en Ubuntu; Ctrl-C termina la demo sintética.
.venv/bin/python -B tools/medir_observador_pty.py --output-new results/local/medicion-pty-NUEVA --duration 8 --repetitions 2
PYTHONPATH=src:tools:tests .venv/bin/python -B -m unittest -v test_csi_live test_csi_observer_lab
.tools/node-v22.20.0/bin/node tests/js/csi_live.test.mjs
# Práctica humana vigente, separada de la demo y todavía pendiente:
.venv/bin/python -B tools/practica_guiada_devrep_v3.py
```

Próximos pasos: revisar todos los controles/estados en navegador humano; medir
latencia hasta render y carga sostenida/competencia con disco antes de revisar
un adaptador físico ligado a contrato, identidad y relojes. No se preparó otra
captura. R4 sigue rechazado/cerrado y permiso consumido; R1–R3, declaraciones,
C01/C03 exploratorias, C02 rechazada y C04–C06 reservadas permanecen intactos.
Presencia requiere desarrollo/calibración y evaluación con conexiones completas
independientes; localizar personas requiere evidencia espacial propia.

## Entrega anterior: observador CSI sintético ejecutable

Implementación: **`a61a2f9`**, observador acotado, productor PTY y visor local.
Documentación/continuación en el commit posterior; `git log -2 --oneline` muestra
ambos. Rama actual conservada, sin push o merge.

Demo sin ESP desde la raíz:

```bash
.venv/bin/python -B tools/demo_csi_vivo.py --seconds 45
```

Abrir **http://127.0.0.1:8767/**. Espera inicial de 1 s, pausa de la fuente entre
5 y 9 s y recuperación; al finalizar queda detenido. Ctrl-C cierra la demo.
`--port 8768` permite otro puerto localhost. Sin servidor ni navegador:

```bash
.venv/bin/python -B tools/demo_csi_vivo.py --headless --seconds 12
```

Cada ejecución crea una carpeta `results/local/demo-csi-sintetico-…/` con original,
view/latest.json y resultados. `--output-new results/local/NOMBRE-NUEVO` requiere
salida nueva. `--observe-synthetic RUTA/original` inicia únicamente otro visor,
sin reiniciar la fuente ni rejuvenecer datos. Se rechazan fuentes físicas/
históricas, fuentes de otro boot y C04–C06. Se impide escribir el visor dentro
del original. [Comandos y límites completos](OBSERVADOR_CSI_SINTETICO.md).

Tres procesos: productor de PTY propio con `Rx02Journal` existente; observador
de archivos en solo lectura; servidor local de una instantánea reemplazable.
Reutiliza framer, parser/validador, decodificador y gráficas originales, sin
modificar el capturador. No hay colas/acks hacia la adquisición. Los botones
solo pausan/actualizan el visor. No hay presencia, personas o coordenadas.

Estados esperando/recibiendo/datos antiguos/detenido verificados. La edad viene
del timestamp host original, también después de reiniciar o reconectar. Las
trazas activas se borran si la muestra es antigua o el visor pierde respuesta.
Un productor muerto sin registro final no se presenta como cierre físico.
Se distinguen parada de fuente y de observador. La fuente física permanece
deshabilitada y toda esta demo está rotulada SIMULADO · SIN ESP.

Límites del visor: 300 filas/30 s, 64 operaciones por sondeo, registro/chunk de
16 KiB y snapshot de 2 MiB. Se informan expulsiones del buffer, actualizaciones
omitidas del navegador y líneas inválidas; el original no se descarta. HTTP usa
un handler con cola de 4 y timeout de socket; el cliente, una petición pendiente.
Estas cotas y la frescura de 2 s no cambian criterios experimentales.

**37 pruebas Python seleccionadas aprobadas**, más arneses Node del visor y la
reproducción. Incluyen consumidor lento, JSONL/CSI partidos, hashes, truncado,
límites, desconexión de navegador, interrupciones limpias/bruscas, muerte/reinicio
del observador y conservación del original. Una primera prueba quedó bloqueada
con eventos compartidos; se interrumpió y corrigió usando flags sin mutex.
La suite final pasó; no se repitió toda la suite del repositorio.

```bash
PYTHONPATH=src:tools:tests .venv/bin/python -B -m unittest -v test_csi_live test_device_panel test_session_offline.ReplayArtifactTests
.tools/node-v22.20.0/bin/node tests/js/csi_live.test.mjs
.tools/node-v22.20.0/bin/node tests/js/replay_demo.test.mjs
```

La demo real headless de 12 s recorrió los cuatro estados y recuperación con 54
filas inventadas; hash de todos los bytes enviados idéntico al bruto, integridad
y replay nativos conformes. Evidencia: `results/local/implementacion-live-r1/`.
HTTP se probó en memoria y DOM/canvas fue simulado: navegador real/legibilidad
siguen pendientes en Ubuntu. No se afirma rendimiento o captura física.

La reproducción histórica usa ahora
`results/local/demo-offline-c01-c03-shared-live-r1/index.html`, compartiendo las
funciones de gráficas. Datos, máscaras, escalas, etiquetas y rechazos idénticos;
contadores de dibujo iguales al artefacto anterior. 321 archivos protegidos y
52 archivos con cambios ajenos se conservaron. R4 y todos los estados anteriores
siguen intactos; sin UART físicos, firmware, calibración/entrenamiento o C04–C06.

Próximos pasos: revisión humana del visor y del guion para tutor; práctica v3
humana pendiente; carga/CPU/disco y latencia representativas antes de habilitar
un adaptador físico en solo lectura ligado a plan, identidad, boot y relojes.
El capturador físico sigue requiriendo revisión/autorización nuevas y no se
controla desde la interfaz. La vista futura seguirá provisional hasta cierre/
auditoría. Presencia y localización requieren su propia calibración/evaluación
independiente. No hay otra adquisición física preparada o autorizada.

## Entrega anterior: navegación y demostración para tutor

Implementación: **`d1841e9`**, navegación y controles. Este resumen, el guion y el
diseño se guardan en el commit de documentación posterior; `git log -2 --oneline`
muestra ambos. Sin push o merge.

Inicio desde la raíz:

```bash
.venv/bin/python -B tools/panel_dispositivos.py
```

Abrir **http://127.0.0.1:8766/** y seguir el enlace a **/replay**. Metadatos USB
actuales y CSI histórico tienen páginas, etiquetas y políticas de conexión
separadas. El servidor verifica el artefacto histórico antes de servirlo; navegar
a la reproducción no consulta USB. Ningún botón inicia captura. Ctrl-C cierra el
servidor; `--port 8767` cambia ambas direcciones conjuntamente.

Alternativa autónoma de reproducción:

```bash
.venv/bin/python -B tools/demo_offline.py
xdg-open results/local/demo-offline-c01-c03-shared-live-r1/index.html
```

Su enlace al panel requiere el servidor en 8766. Las versiones anteriores se
conservan; `tutor-r1/` es un prototipo de esta integración.

Se registró la comprobación del operador en Ubuntu: RX-02 detectado, RX-01
ausente y TX no verificable por USB, **sin READY o CSI verificados**. No se
infiere que ese estado siga vigente ni se sustituye la hora de consulta por la
hora de registro. Declaración en
`results/local/demo-tutor-navegacion-r1/comprobacion-panel-operador.json`.
La vista limitada de `/dev` registrada antes por el agente corresponde a otro
entorno y se conserva.

Se corrigieron pausa/cambio de velocidad entre fotogramas y fin inmediato de la
reproducción, sin cambiar timestamps o plazos experimentales. El panel ya no
acepta inventarios vacíos/incompletos; rechaza atribuciones READY/CSI, limita la
consulta del visor a 12 s y libera el botón ante error, sin detecciones antiguas.

Pasaron **30 pruebas Python seleccionadas** (29 en `pruebas-python.log` más el
nuevo caso de arranque en `arranque-python.log`), los arneses Node de metadatos y
reproducción en tres contextos: archivo, HTTP integrado y HTTP separado. HTTP en
memoria sirvió el HTML real y verificó rutas y separación de USB. No se repitió
la suite completa. Comandos equivalentes para reproducir la verificación:

```bash
PYTHONPATH=src:tools:tests .venv/bin/python -B -m unittest -v test_device_panel test_session_offline.ReplayArtifactTests test_presence_synthetic_pipeline test_presence_adapter_review
.tools/node-v22.20.0/bin/node tests/js/device_panel.test.mjs
.tools/node-v22.20.0/bin/node tests/js/replay_demo.test.mjs
REPLAY_HTTP=1 .tools/node-v22.20.0/bin/node tests/js/replay_demo.test.mjs
REPLAY_HTTP=separate .tools/node-v22.20.0/bin/node tests/js/replay_demo.test.mjs
```

DOM/canvas simulado y HTTP en memoria no completan la revisión humana de la nueva
navegación, todos los controles nativos o pantallas. No se repitió la apertura
de sockets/navegador ya bloqueada en el entorno del agente. La confirmación del
operador cubre el panel anterior, no toda la integración nueva.

Datos/máscaras/escalas/etiquetas/rechazos idénticos byte a byte; 321 archivos
protegidos y 52 archivos con cambios ajenos conservan hashes. Capturadores,
extractores y cabeza RuView no cambiaron. Sin UART, captura, firmware, modelos
físicos ni C04–C06. R4 permanece rechazado/cerrado, permiso consumido; los estados
anteriores se conservan. Evidencia: `results/local/demo-tutor-navegacion-r1/`.

Entregables: [guion de cuatro minutos](DEMO_TUTOR.md) y
[diseño mínimo de CSI en vivo](DISENO_CSI_EN_VIVO_MINIMO.md). El diseño propone
otro proceso que observa el journal en solo lectura y publica una instantánea
acotada; el capturador no espera a la interfaz. La vista sería provisional: el
marcador durable actual es final, no una API en vivo. No se implementó ni se
ejecutaron pruebas de ese observador; tampoco se afirma rendimiento físico.

Próximos pasos: revisión humana de navegación/controles y ensayo del guion;
práctica v3 humana pendiente; antes de implementar/habilitar el observador,
pruebas sintéticas de prefijos, errores, lentitud y carga PTY. Presencia requiere
desarrollo independiente aceptado/autorizado, política de anclas y evaluación
por conexiones/grupos separados con método y métricas fijados. Localización
requiere además método viable, geometría y verdad de referencia espacial.
No hay otra adquisición preparada o autorizada.

## Registro de entregas anteriores

Commits locales de implementación:

- `a227b52`: presentación compartida de práctica y operación, teclado y pruebas PTY.
- `36eaa0d`: demostración autónoma C01/C03 y extracción descriptiva de ventanas elegibles.
- `4771e64`: barreras sintéticas y revisión técnica de PresenceSpecialist.

Este informe se guarda en un commit de cierre posterior. No se hicieron push,
merges o publicaciones. Los 52 archivos con cambios previos permanecen idénticos
y fuera de estos commits, incluidos README, ESTADO_INICIAL y módulos R1/R2 sin
seguimiento. Las pruebas corresponden al árbol local existente, que conserva
esas dependencias previas; no se afirma una prueba desde un checkout limpio.

Actualización posterior del operador: la demostración abre y muestra mapas,
RSSI y variabilidad; el encabezado fijo se superponía al contenido al desplazar.
Se corrigió únicamente su CSS para mantenerlo en el flujo normal. La salida
vigente es `results/local/demo-offline-c01-c03-scroll-r1/index.html`; las
anteriores se conservan. Datos, escalas y JavaScript de reproducción permanecen
idénticos. El operador confirmó visualmente que el encabezado corregido ya no
cubre las gráficas al desplazar y que se muestran los datos y los detalles de
muestras. La comprobación humana de todos los controles sigue pendiente.
Evidencia del ajuste y declaración posterior en
`results/local/ajuste-demo-scroll-r1/`, archivo `confirmacion-visual-operador.json`.

Revisión offline siguiente: se corrigió un fallo reproducido que cerraba los
detalles abiertos y borraba la consulta de muestras en cada frame de reproducción.
La salida vigente pasa a `results/local/demo-offline-c01-c03-controles-r1/`;
conserva datos/escala byte a byte y el CSS de encabezado ya confirmado. El arnés
ampliado pasó todos los controles anunciados, velocidades, cambio de vistas,
pausa por visibilidad, fin automático y muestra limitada al cursor, con
DOM/canvas simulado. **La comprobación humana completa sigue pendiente.**
Corrección y arnés guardados en el commit local `35a35c1`.

También se verificó en memoria el recorrido desde CSV/IQ inventado hasta
PresenceSpecialist, con conexiones sintéticas de calibración y consulta distintas.
Las barreras de auditoría son fixtures explícitos, no una validación de captura
física. Pasaron 35 pruebas Python seleccionadas (33 de software sintético y dos
del artefacto descriptivo real). No se modificaron cabeza, extractores o criterios;
no hubo UART ni calibración, entrenamiento o inferencia con datos físicos.
Evidencia: `results/local/revision-controles-presence-r1/`. Para calibrar/evaluar
faltan conexiones independientes aceptadas y autorizadas, política prospectiva
de anclas (RuView usa el primer `Empty`), particiones por conexión y grupos
correlacionados, método/métricas fijados antes de abrir evaluación. C04–C06 siguen
selladas. Detalles en la revisión del adaptador enlazada abajo.

Panel de dispositivos posterior, separado de la reproducción: ejecuta
`.venv/bin/python -B tools/panel_dispositivos.py` y abre
`http://127.0.0.1:8766/`. Consulta serie/by-id/nodo/permisos por los identificadores
existentes, sin UART ni preflight. Estados detectado/ausente local/no verificable;
READY y CSI siempre sin observar. TX externo: «no verificable por USB».
La consulta real del entorno dio RX-01/RX-02 no verificables por `/dev` limitado.
Pasaron 16 pruebas Python y el arnés JS del panel; HTTP se probó en memoria.
El socket localhost fue rechazado con EPERM, por lo que la navegación real sigue
pendiente. Instrucciones y alcance: [panel local](PANEL_DISPOSITIVOS_LOCAL.md).
Evidencia: `results/local/panel-dispositivos-r1/`. La demo, sus datos y todos los
rechazos se conservan; no se abrió UART ni se preparó otra captura.

## Entregado

- Una presentación compartida para las acciones E→S, órdenes completas y contador
  de tiempo disponible para responder. La práctica v3 la usa; el adaptador físico
  reutilizable se verificó sobre el coordinador nativo con PTY sintético, sin
  seleccionar un nuevo ejecutor físico ni modificar los históricos.
- Mensajes distintos de práctica, entrada inválida/formato esperado,
  incertidumbre, cancelación, vencimiento, error, final simulado y cierre físico
  comprobado. Plazos, política de aceptación y coordinadores experimentales intactos.
- HTML local con reproducción/pausa/reinicio/velocidad, selección E/S de C01/C03,
  comparación con escalas comunes, mapa de calor LLTF52, RSSI y variabilidad
  definida. Conserva máscaras, huecos, nanosegundos y referencias; muestra el
  rechazo de conexión separado de la elegibilidad exploratoria de ventana.
- Revisión del recorrido auditado hasta las características LLTF52 y pruebas
  sintéticas de la cabeza. Se corrigieron generadores de anclas agotados y
  registros sintéticos malformados. No se modificó la matemática de `train/infer`.

Detalles en [interfaz](INTERFAZ_OPERACION_COMPARTIDA.md),
[demostración](DEMO_REPRODUCCION_OFFLINE.md) y
[adaptador PresenceSpecialist](REVISION_ADAPTADOR_PRESENCE_20261109.md).

## Abrir la demostración

Desde `/home/alan-monar/tesis-wifi-csi-hibrido`:

```bash
.venv/bin/python -B tools/demo_offline.py
xdg-open results/local/demo-offline-c01-c03-tutor-r2/index.html
```

HTML autónomo, sin servidor ni instalaciones. El generador verifica el artefacto
existente y sus fuentes/originales. Un cambio de fuentes requiere otra ruta
`--output-new`; no se sobrescriben las versiones previas. Los directorios
`demo-offline-c01-c03/` y `demo-offline-c01-c03-v1/` son prototipos conservados;
`demo-offline-c01-c03-final/` es la versión previa al ajuste del encabezado.
`demo-offline-c01-c03-scroll-r1/` conserva la corrección de desplazamiento ya
confirmada. `demo-offline-c01-c03-controles-r1/` conserva la revisión previa.
`tutor-r2/` conserva la versión anterior de gráficas.
Usar **demo-offline-c01-c03-shared-live-r1/** para la revisión vigente.
No se inició un servicio en esta sesión.

## Práctica vigente

```bash
.venv/bin/python -B tools/practica_guiada_devrep_v3.py
```

Escribir `practicar` y Enter. E/S se envían separadamente cuando aparezcan sus
prompts, tras cumplir las indicaciones y oír los avisos:

```text
declare PRACTICA-GUIADA-E yes
declare PRACTICA-GUIADA-S yes
```

Ante duda, `declare PRACTICA-GUIADA-E uncertain MOTIVO` o equivalente S;
`abort`/Ctrl-C cancelan. La práctica v3 humana **sigue pendiente**. No hubo una
nueva ejecución humana durante esta sesión autónoma.

## Comprobaciones reales y límites

48 pruebas Python aprobadas: 46 de integración/extracción/cabeza/diagnósticos y
dos adicionales de práctica PTY y equivalencia de WAV. Comandos ejecutados:

```bash
PYTHONPATH=src:tools:tests .venv/bin/python -B -m unittest -v test_session_offline test_presence_adapter_review test_shared_operator_pty test_practice_diagnostics_v3 test_presence_offline.ExtractionTests test_presence_offline.SyntheticHeadTests
PYTHONPATH=src:tools:tests .venv/bin/python -B -m unittest -v test_shared_practice_pty
.tools/node-v22.20.0/bin/node tests/js/replay_demo.test.mjs
```

El arnés JS pasó controles, selección, velocidad, recuentos y escalas comunes
con DOM/canvas simulado. Las ventanas reales verificadas tienen C01 E=148/S=150
y C03 E=143/S=146 filas. No se ejecutó calibración, entrenamiento ni inferencia
con datos físicos; no se repitió la suite completa del repositorio.

El control de navegador fue impedido por `EPERM` al crear un socket local.
Firefox headless también falló al crear un espacio de nombres (`returncode=-11`);
no produjo captura de pantalla. No se deshabilitó el sandbox ni se solicitó
autorización adicional. En esa sesión automática quedaron pendientes el aspecto
visual y el comportamiento en navegador real. La confirmación posterior del
operador cubre el desplazamiento corregido y la visualización de datos/detalles
de muestras, sin validar todos los controles. Los WAV idénticos se comprobaron con reproductor externo simulado;
no se demuestra sonido emitido o audibilidad humana.

321 archivos protegidos y los 52 archivos con cambios previos conservan sus
hashes. Las cuatro fuentes editadas que tenían versión previa fueron archivadas
y comparadas byte a byte con el commit base. El AST de la cabeza numérica y sus
funciones aritméticas coincide con el original. Evidencia local:

```text
results/local/sesion-offline-20261109/
  git-inicial.json
  protegidos-antes.json / protegidos-despues.json
  cambios-ajenos-antes.json
  fuentes-antes/
  preservacion-despues.json
  declaracion-operador-practica.json
  pruebas-finales-python.log / pruebas-practica-pty.log / pruebas-finales-js.log
  browser-screenshot/result.json
```

El manifiesto del HTML identifica fuentes, originales y sus hashes. No se
abrieron UART/dispositivos serie ni datos C04–C06; no se consultó hardware actual.
No hubo adquisición, flasheo, reset, reconexión, calibración o entrenamiento con
datos físicos.

## Estado experimental conservado y próximos pasos

R4-N01 permanece rechazado, RX-02 cerrado con recibo original y autorización
consumida; E no se reetiqueta. R1/R2/R3 conservan rechazos y declaraciones
posteriores. C01/C03 son exploratorias; C02 sigue rechazada. C04–C06 permanecen
reservadas y no se usaron para desarrollo, selección de métodos o escalas.

Declaración literal nueva del operador: «En una práctica anterior sí salí y
escuché el tono final, pero escribí solamente “guiada-e”». Se registró como
antecedente humano, sin afirmar la causa exacta de terminación ni cambiar
etiquetas experimentales.

Pendientes concretos para la próxima sesión:

1. Completar la comprobación humana de la navegación, todos los controles y la
   comparación, incluida legibilidad en escritorio y pantalla estrecha, sobre
   la versión integrada `/replay` o `tutor-r2`.
   El operador confirmó el desplazamiento sin superposición y la visualización
   de datos y detalles de muestras en `scroll-r1`; no confirmó todos los controles
   ni tamaños de pantalla. El arnés ampliado verifica software, sin suplir esa
   confirmación humana.
2. Ejecutar la práctica v3 humana con sonidos; revisar su nuevo registro y si se
   entendieron las acciones y las órdenes completas. Conservar incertidumbre si
   no se oyó un aviso o no se cumplió una condición.
3. Antes de cualquier futura captura, revisar explícitamente la selección del
   adaptador reutilizable, fuentes, plan, identificador, salida, preflight y
   autorización nuevos. **No hay otra adquisición preparada o autorizada.**
4. Para una futura detección, definir desarrollo suficiente y particiones por
   conexión completa antes de autorizar calibración. Mantener C04–C06 selladas.
