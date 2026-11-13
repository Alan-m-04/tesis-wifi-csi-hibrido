# Protocolo preparado: captura dual controlada de 30 segundos

Cuarto hito, 25 de octubre de 2026. Base `56ea2702d362111faa4b470f69315547e65dd1a9`, rama `feat/preparacion-captura-dual`. **Preparación solamente: no se ha abierto UART física ni ejecutado la captura propuesta.** Se mantienen ESP-IDF v5.4, firmware y objetivos del anteproyecto. No hay flasheo, escritura a placas, UDP, streaming ni entrenamiento.

## Autorización y condición ambiental

Antes de abrir ambos receptores hacen falta autorización explícita del usuario y la declaración ambiental en `config/captura_dual_30s.local.json` (ignorado por Git). La plantilla versionada es `config/captura_dual_30s.template.json`. Ocupación, movimiento, ubicación/separación de TX/RX y alimentación de TX no se conocen actualmente y se dejaron como null. No se inventó un estado de habitación vacía ni se trasladó una condición del experimento anterior a esta sesión.

Los campos requeridos son `environment.condition`, `occupancy`, `movement`, `geometry` y `tx_power`. Deben registrar lo que declara/observa el operador; el programa no mide automáticamente el ambiente ni acredita ground truth. La ejecución falla antes de preflight/apertura si faltan campos o dicen PENDIENTE. Completar el plan no equivale a autorizar UART.

Por defecto, `tools/captura_dual_controlada.py --plan ...` solo imprime PREPARED_NOT_EXECUTED. `--preflight-only` inspecciona stat/udev sin abrir el puerto. **Solo `--execute-after-approval` habilita la ruta que abre dispositivos**; esa bandera no sustituye el permiso humano en esta conversación. No se ha invocado esa ruta con dispositivos reales en este hito.

## Identidades y configuración previstas

| Rol | Serie histórica exigida | Ruta estable exigida |
|---|---|---|
| RX-01 | 5C93199744 | /dev/serial/by-id/usb-1a86_USB_Single_Serial_5C93199744-if00 |
| RX-02 | 5C93200689 | /dev/serial/by-id/usb-1a86_USB_Single_Serial_5C93200689-if00 |

Son las identidades históricas esperadas; no se afirma que su presencia actual haya sido verificada por abrirlas. El preflight futuro exige dos nodos distintos, propiedades udev USB/VID 1a86/PID 55d3/serie, ausencia de series duplicadas y concordancia de by-id con udev. Se revalida la identidad antes de cada apertura y al terminar. Un fallo aborta, no cambia a otro ttyACM por su número ni solicita privilegios automáticamente.

115200, 8N1, timeout de lectura 0,1 s, exclusive=True de pySerial POSIX. Esa exclusividad es flock **consultivo entre procesos que lo respetan**, no garantía contra un proceso previo que no coopere. No se fuerza el cierre de procesos ajenos. DTR=False y RTS=False se solicitan antes de abrir; no se envían pulsos deliberados ni bytes por UART. Esto no garantiza el nivel eléctrico ni ausencia de glitches/reset del adaptador, y el cierre/driver puede afectar líneas. [La API oficial de pySerial](https://pyserial.readthedocs.io/en/latest/pyserial_api.html#serial.Serial.open) advierte de esa posibilidad; la revisión local de 3.5 fija el comportamiento auditado.

Perfil esperado del código: ESP32-S3, canal 11, HT20, fuente TX 1a:00:00:00:00:00, Im/Re int8 y modelo LLTF+HT-LTF documentado. El programa registra hashes de fuentes/configuración, commit Git y pySerial, **installed_firmware_sha256=null** y explicación de que el binario instalado no está atestado. No abre TX-01; su alimentación y geometría se anotarán por el operador.

## Arranque, tiempos y duración: decisión previa

1. Se reservan un directorio interno nuevo y los metadatos antes de abrir; se exigen al menos 100 MiB libres. Nunca se sobrescribe una sesión previa.
2. Al retornar la apertura de RX-01, se inicia inmediatamente su lector y sus archivos, antes de abrir RX-02. Los bytes pendientes no se limpian. Si falla la segunda apertura, se detiene/junta el primer lector y se conservan sus archivos parciales con estado error.
3. Cuando ambos lectores están preparados, se registra `controlled.common_start_ns`; `common_deadline_ns = start + 30.000.000.000 ns`. Ambos lectores comparten esa ventana host. No hay sincronización RF implicada.
4. La **sesión completa** también incluye el preámbulo previo a esa ventana y cualquier lectura iniciada antes del límite que retorne después por timeout. Sus límites reales `capture_start_monotonic_ns`/`capture_deadline_monotonic_ns` abarcan desde antes de abrir hasta después de cerrar. La duración total puede superar 30 s; no se renombra como una ventana estable de 30 s.
5. Cada lectura no vacía se conserva en bruto y en un ledger con offsets, tamaño, comienzo/retorno monotónico y UTC de retorno. Todas las filas completadas en ese bloque comparten el timestamp registrado. No se interpolan tiempos individuales ni se emparejan callbacks de RX distintos.
6. Al terminar, se detienen/juntan los lectores antes de cerrar puertos, también en fallo o interrupción de startup. Se conserva la cola sin LF, no se completa artificialmente. No hay drenaje indefinido al final ni promesa de preservar bytes nunca leídos fuera de los límites; se preserva íntegro todo lo que devolvieron las lecturas. El intervalo open/configuración/driver y pérdidas físicas no observables no se declaran cubiertos por una captura de cable perfecta.

**No hay ventana estable derivada en este protocolo:** stable_window=null. No se descarta warmup ni se busca retrospectivamente un recorte que apruebe. Se valida la sesión completa; un arranque defectuoso no desaparece aunque después haya muestras correctas. Los conteos dentro de la ventana común son descriptivos, no una segunda aceptación. Si se desea una ventana derivada en otro protocolo, habrá que fijar límites antes de ejecutar, mantener el resultado completo, registrar qué bytes/filas incluye y conservar ambos resultados separados. Una ventana aprobada nunca aprobaría la sesión completa.

## Defectos demostrados y correcciones de host

La [fuente oficial POSIX de pySerial v3.5](https://github.com/pyserial/pyserial/blob/v3.5/serial/serialposix.py) llama `_reset_input_buffer()` desde `open()`, que ejecuta TCIFLUSH. La ausencia de una llamada explícita en el capturador antiguo no impedía esa pérdida. `src/preserving_serial.py` deriva localmente de la clase auditada, evita únicamente ese flush durante open y prohíbe reset_input_buffer/reset_output_buffer explícitos. No se parchea el paquete instalado ni se cambia firmware. Se comprobó en PTY privado que los bytes escritos antes de abrir sobreviven y que no se llama tcflush; la clase original sí lo llama.

El capturador también subcontaba trailing_bytes después de vaciar su acumulador de **encuadre** por exceso de 65536 bytes sin LF. Ahora cuenta todos los bytes desde el último LF, aunque el acumulador de parsing se limite. Ese límite nunca vacía un buffer del dispositivo: el bruto conserva todos los bytes y oversized_lines marca el rechazo. El auditor offline cuenta también un tail excesivo sin LF. Se reprodujeron colas de 150000 bytes, líneas excesivas con recuperación y lecturas de un byte.

El lector restaurado conserva formato y criterios originales. Se añadió ledger opcional y modo de lectura desde apertura para la nueva orquestación; no se recorta/repara la línea histórica ni se relajan los flags. Su copia original recuperada permanece intacta fuera del repositorio; `results/preparacion_captura_dual.validacion.json` fija los hashes antes/después del código derivado.

## Criterios de validación

Se mantienen los flags de formato originales: muestras válidas, MAC/canal/estado, errores, longitudes, contador/tiempo de dispositivo y descartes locales. El auditor mantiene hashes, identidad CSV, igualdad bruto/CSV, perfil de 256 escalares y relojes, sin huecos callback ni reinicios posteriores al primer dato. No se inventa una expectativa exacta de 150 filas o una tasa uniforme de 5 Hz.

Para controlled_dual_v1 se exige además: sesión completed, ambos lectores, ventana común exacta dentro de la envolvente real, al menos un registro válido por RX dentro de esa ventana, ledgers completos/contiguos con hash y timestamps congruentes con el último byte de cada fila, identidad postflight válida y ausencia de tail incompleto o residuos reconocibles de encuadre (ESP-ROM pegado a un prefijo, fragmentos que empiezan por coma/comilla). Esto es más estricto, no una relajación del criterio histórico. Otros textos no CSI siguen en bruto; no se presume que cada mensaje de arranque sea una medición. La aprobación es de integridad/formato y cobertura declarada, no de rendimiento RF, precisión o campaña de presencia.

Las lecturas que atraviesen el límite de 30 s se registran completas en la sesión, con su tiempo real. Sus filas no se reasignan a instantes anteriores para hacerlas entrar en la ventana común. Un fallo/aborto, identificación incoherente o un bruto incompleto produce rechazo/error explícito. No hay reintentos automáticos, reset, limpieza de entrada ni cambio de firmware.

## Comando preparado (NO ejecutado)

Después de completar el ambiente y recibir autorización explícita, desde el repositorio:

```bash
cd /home/alan-monar/tesis-wifi-csi-hibrido
.venv/bin/python -B tools/captura_dual_controlada.py \
  --plan config/captura_dual_30s.local.json \
  --output-new results/local/captura-dual-30s-20261025-plan01 \
  --execute-after-approval
```

Antes de abrir, el comando valida el plan, las identidades y el espacio. El directorio propuesto aún no se creó como sesión física. Si ya existe en ese momento, aborta y habrá que elegir otro nuevo.

Archivos previstos:

```text
captura-dual-30s-20261025-plan01/
  plan.json                 # declaración ambiental y política fijadas
  provenance.json           # commit, hashes de código/configuración; firmware instalado desconocido
  preflight.json            # identidades por udev antes de abrir
  capture/
    rx-01.serial.log         # bruto completo de bytes leídos, también errores/arranque
    rx-02.serial.log
    rx-01.csv               # solo filas aceptadas; 31 campos y tiempos registrados
    rx-02.csv
    rx-01.summary.json
    rx-02.summary.json
    rx-01.reads.jsonl        # ledger de lecturas no vacías
    rx-02.reads.jsonl
    session.json            # envolvente real, ventana común y ciclo de vida
  postflight.json
  capture-manifest.json     # siete archivos principales y dos ledgers, SHA-256
  quality.json              # resultado de sesión completa; ninguna ventana derivada
  bundle-manifest.json      # hashes de adquisición/metadatos; no hash de sí mismo
```

Retorno 0 únicamente si la validación completa acepta; 1 ante rechazo/fallo de adquisición. Un plan inválido o preflight fallido aborta sin abrir UART; no se escala a sudo automáticamente. Un fallo de almacenamiento puede impedir completar metadatos: nunca se declara éxito en ese caso.

## Análisis y nueva visualización posteriores

Solo después de obtener una sesión, ejecutar offline en **otro directorio nuevo**:

```bash
.venv/bin/python -B tools/analizar_captura_controlada.py \
  --run results/local/captura-dual-30s-20261025-plan01 \
  --output-new results/local/analisis-dual-30s-20261025-plan01
```

Verifica el bundle-manifest, vuelve a auditar brutos/CSV/ledgers y guarda quality.json. Si la integridad permite interpretar el perfil documentado, genera visualization/index.html con el constructor aislado del tercer hito y el manifiesto de esa sesión, sin hardcodear 292/291 filas. El texto será «captura dual controlada con validación estricta aceptada/rechazada»; un caso sintético dice explícitamente prueba sintética. El antecedente de 60 s conserva «captura histórica con validación estricta rechazada». Un modelo LTF no respaldado falla, no fuerza dimensiones.

La página conserva relojes, máscaras y metadatos en el canónico, y usa el consumidor oficial solo con buffers. No necesita servidor y no habilita presencia. El analizador devuelve 1 para un rechazo aunque produzca visualización diagnóstica; esa salida no convierte el rechazo en éxito. No sobrescribe adquisición, manifests ni visualizaciones anteriores. Los brutos y salidas completas permanecen locales e ignorados; solo informes/código/manifiestos resumidos van a Git.
