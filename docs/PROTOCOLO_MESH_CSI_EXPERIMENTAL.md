# Variante Mesh/CSI y transporte TCSI v1 — 24/11/2026

Estado: **fuentes experimentales y codec comprobado en memoria**. No es un
contrato de adquisición aprobado ni sustituye v3/v4. No se abrió UART, se
flasheó, se creó un hotspot ni se recogieron datos físicos. C04–C06 siguen
reservadas. Los objetivos del anteproyecto se conservan.

## Decisión provisional de transporte

Preparar **UART 921600, 8N1 y encuadre binario** como primer candidato. Se
conservan todos los bytes del buffer CSI recibido y los 19 campos RX utilizados
en la representación histórica, sin remuestrear ni convertir Im/Re. La nueva
representación añade nodo, padre, capa y época de topología.

| Opción | Presupuesto y consecuencia | Estado |
| --- | --- | --- |
| UART 115200 y CSV histórico | Solo el arreglo textual de 256 enteros necesita ≥516 bytes. A 100 Hz, ≥51.600 B/s frente a 11.520 B/s teóricos. | Insuficiente para ese perfil/tasa. |
| UART 921600 y TCSI v1 | 462 bytes por frame con 256 bytes CSI. A 100 frames/s: 46.200 B/s. Sumando una reserva de 20.000 B/s para eventos: 66.200 B/s, 71,83 % de 92.160 B/s teóricos. | Candidato implementado en fuentes; puente CH343, UART real y host pendientes. |
| UART 2000000 y CSV | Puede aportar más capacidad, pero requiere medir tamaño real, soporte del puente y coste del texto. Cambiar el baud también requiere un nuevo contrato de captura. | Alternativa sin implementar ni validar. |
| Red Wi-Fi | Requiere encuadre, control de pérdidas y presupuesto por salto; el tráfico adicional puede alterar el sensado. | Alternativa sin implementar. |
| USB nativo | Requiere comprobar conector, cableado, interfaz y persistencia; no equivale al puente CH343 observado. | Alternativa sin implementar. |

El límite del 80 % y la reserva de eventos son **reglas de ingeniería del
prototipo**, no metas académicas aprobadas ni garantías de capacidad. La guarda
`tcsi_budget_fits` rechaza una configuración que exceda ese presupuesto; por
ejemplo, 1024 bytes CSI a 100 Hz no se aceptan a 921600 con esa reserva.

Con 256 bytes CSI, 100 Hz y 180 h, habría 64.800.000 frames/RX y 29,94 GB
decimales/RX solo en frames CSI TCSI. Añadir eventos, ledgers, índices y copias.
Son estimaciones; no son datos capturados. No hay llenado artificial de muestras.

## Arquitectura implementada en fuentes

- Un proyecto independiente: `firmware/mesh_csi_experimental`. No modifica
  `csi_send`, `csi_recv`, `csi_recv_02` ni los capturadores/auditores existentes.
- ESP32-S3 con ESP-IDF **5.4**; raíz fija designada por nodo 0 (etiqueta TX-01),
  nodos 1/2 (RX-01/RX-02), árbol ESP-WIFI-MESH con hasta cuatro capas.
  Las etiquetas no verifican por sí mismas la identidad física USB/MAC.
- El usuario indicó que puede utilizar el **hotspot de Ubuntu**. Sigue pendiente
  comprobar que el adaptador acepte AP en 2,4 GHz, canal 11 y HT20. No se ha
  configurado en su equipo. No hace falta acceso a Internet para la comunicación
  Mesh interna; sí confirmar asociación del root y configuración IP local.
- El root envía probes identificados a los destinos de su tabla de rutas.
  Se registran envíos y recepción lógica, eventos Mesh, padre/capa y estado.
  El periodo configurado es candidato, no frecuencia RF o CSI lograda; Mesh
  puede bloquear la emisión. El bucle evita ráfagas de recuperación.
- Los sensores filtran por una **MAC transmisora RF configurada**, que debe
  verificarse antes del ensayo. STA y softAP tienen identidades distintas. No
  se reutiliza por suposición la MAC experimental antigua del TX.
- Inicialización CSI antes de `esp_mesh_start`, sin APIs Wi-Fi posteriores y
  sin promiscuo en este primer candidato. Esto respeta la restricción documental
  de autoorganización; **no prueba** que se reciban tramas CSI útiles. Debe
  comprobarse su necesidad/compatibilidad en placa antes de cambiar el diseño.
- El callback copia los datos de vida corta a una cola; un único escritor
  serializa muestras y eventos. Tamaño excesivo o cola llena incrementan
  `queue_drops`; no hay truncamiento de CSI. Un contador distinto de cero es
  evidencia de pérdida, no una captura completa.
- El escritor usa `uart_write_bytes` directamente, con UART0 8N1 y sin
  control de flujo, para evitar que VFS convierta los bytes LF del CSI en
  CR/LF. Registra el baud reportado por el controlador. La corrección física
  del enlace y el cierre/drenaje siguen pendientes de comprobación.
- Cambios de padre/capa/canal incrementan `topology_epoch`. Se conserva la
  geometría por segmento. La MAC fuente no se cambia automáticamente: una
  recuperación con otro padre puede dejar de producir CSI filtrado; debe
  registrarse y revisarse, no mezclarse con la geometría anterior.
- Sin credenciales locales válidas o presupuesto suficiente, retorna antes
  de inicializar Wi-Fi. No borra NVS automáticamente. Los valores de ejemplo
  están vacíos; no se publica ninguna contraseña.

ESP-WIFI-MESH utiliza un árbol y reelección/reconexión de padres; no se presenta
como una malla completa. El código de probes/eventos no acredita una ruta de
dos saltos: todavía hacen falta trazas correlacionadas de cada nodo, geometría
que requiera un intermediario y pruebas de recuperación con ruta alternativa.
La secuencia del probe lógico no se empareja automáticamente con cada callback
CSI; las tramas radio de control/retransmisión impiden asumir esa equivalencia.

## Contrato binario de ensayo

Todos los enteros son little endian; no se envían structs C por memcpy. CRC32
IEEE (vector `123456789` → `cbf43926`) cubre cabecera y payload, excluyendo
únicamente sus cuatro bytes finales. No ofrece autenticación criptográfica.

| Cabecera | Tamaño |
| --- | ---: |
| Magic ASCII `TCSI` | 4 |
| Versión 1, tipo (1 CSI / 2 evento), node_id (0–2), flags=0 | 4 |
| Secuencia de frames uint32 | 4 |
| Longitud payload uint16, reservado uint16=0 | 4 |
| Payload | variable |
| CRC32 uint32 | 4 |

Payload CSI, en orden: callback_id uint32, queue_drops uint32, topology_epoch
uint32, capa uint8, MAC fuente RF/nodo STA/padre (6 bytes cada una), 19 valores
int64, longitud CSI uint16, first_word_invalid uint8 (0/1) y bytes CSI originales.
Parte fija: 186 bytes. No se eliminan los primeros bytes marcados inválidos:
se conserva el indicador para la transformación posterior.

Orden de los 19 metadatos: rssi, rate, sig_mode, mcs, bandwidth, smoothing,
not_sounding, aggregation, stbc, fec_coding, sgi, noise_floor, ampdu_cnt,
channel, secondary_channel, local_timestamp, ant, sig_len, rx_state.
No se afirma conservar todos los campos posibles de `wifi_pkt_rx_ctrl_t`;
se conservan los utilizados por el CSV histórico. No se deducen LTF o índices
solamente de la longitud. El dominio del timestamp RX permanece uint32 local;
los eventos usan tiempo monotónico del nodo, no UTC ni sincronización RF.

Payload de evento: 1–256 caracteres ASCII imprimibles. Los campos de texto son
diagnóstico, no sustituyen un esquema de auditoría validado. Saturación de
eventos también cuenta como pérdida de cola.

`src/mesh_csi_wire.py` decodifica **solo bytes en memoria**: no abre archivos
de dispositivo, UART o red. Rechaza CRC, versión, flags, longitudes y colas
truncadas; no se resincroniza ni descarta residuos para fabricar una conexión
aceptada. Una excepción rechaza todo el stream, incluso si antes devolvió
frames. La secuencia se conserva, pero la continuidad entre frames/sesiones
todavía requiere un auditor: un frame correcto **no prueba calidad física**.
El resultado declara `acquisition_quality=not_evaluated` y
`model_use=not_authorized`.

## Comprobaciones realizadas y límites

Se compiló **wire.c para el host con GCC C11**, `-Wall -Wextra -Werror -pedantic`,
y se ejecutó contra el decoder Python mediante ctypes: **12 pruebas aprobadas**.
Incluyen preservación de bytes signed/int64/MAC, tamaños variables, vector CRC,
cada inversión de un bit del frame sintético, división en chunks y errores
persistentes, así como rechazo de configuraciones que exceden el presupuesto.
Enviar 100 frames sintéticos a una función no mide 100 Hz físicos.

**No se compiló app_main.c para ESP32-S3**: este entorno carece de ESP-IDF y
toolchain Xtensa. No se ejecutaron FreeRTOS, Wi-Fi, Mesh, CSI, el puente CH343 ni
la UART a 921600. No se afirman nuevas pruebas del resto del repositorio. El
informe machine-readable está en `results/MESH_CSI_EXPERIMENTAL.validacion.json`.

## Antes de usar en placa, en este orden

1. Compilar con el ESP-IDF 5.4 ya conservado en Ubuntu, primero sin conectar
   dispositivos. Desde el repo: `idf.py -C firmware/mesh_csi_experimental
   set-target esp32s3`; configurar localmente con `menuconfig`; después `build`.
   Revisar que sdkconfig, headers generados y contraseñas sigan ignorados por Git.
   Esta guía no incluye ni autoriza flasheo.
2. Resolver errores reales de compilación y comprobar la inicialización en el
   hardware con autorización específica. Confirmar AP/canal/ancho, MACs e
   identidades físicas, y la recepción CSI del enlace elegido.
3. Diseñar y validar offline un **nuevo capturador/auditor** para TCSI: baud,
   identificación USB, apertura sin pérdidas, residuos de arranque, conexión vs
   ventana, hashes/ledgers, continuidad de frames/callbacks, relojes y cierre.
   ROM/boot a otro baud no queda resuelto por este encoder. No conectarlo al
   capturador v3/v4 como si fuera compatible; no rebajar sus rechazos.
4. Obtener autorización explícita para la intervención física concreta. Los
   permisos de intentos históricos no se reutilizan. Probar individual → dual,
   5/10/25/50/100 Hz y después continuidad; fijar duraciones, tolerancias y parada
   antes de cada ensayo. Verificar Mesh+CSI concurrentes y recuperación aparte.
5. Mantener D01/D02 y tareas 2-1/2-4/2-5/2-6 sin cierre hasta disponer de la
   evidencia correspondiente. El punto 1-3 sigue parcial.

La campaña continúa prevista para enero de 2027: 20 días consecutivos,
09:00–18:00 (Ecuador), 180 h programadas; fecha/local pendientes. Puede
adelantarse si sistema y establecimiento están listos; no reducir los 20 días
para afirmar un resultado de campo antes de medirlos.

## Fuentes primarias

- Espressif, ESP-IDF v5.4, [guía ESP-WIFI-MESH para S3](https://docs.espressif.com/projects/esp-idf/en/v5.4/esp32s3/api-guides/esp-wifi-mesh.html).
- Espressif, [API y restricción de autoorganización](https://docs.espressif.com/projects/esp-idf/en/v5.4/esp32s3/api-reference/network/esp-wifi-mesh.html).
- Espressif, [CSI y callback](https://docs.espressif.com/projects/esp-idf/en/v5.4/esp32s3/api-guides/wifi.html#wi-fi-channel-state-information-configure).
- Espressif, [UART y configuración](https://docs.espressif.com/projects/esp-idf/en/v5.4/esp32s3/api-reference/peripherals/uart.html).
- Fuente base propia: commit `0feec428f323d285c6c986b9ae50f5aca37ac303`.
  Procedencia del ejemplo Mesh: `firmware/mesh_csi_experimental/NOTICE.md`.
