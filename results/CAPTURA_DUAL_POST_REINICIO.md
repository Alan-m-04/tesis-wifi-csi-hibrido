# Captura dual posterior al reinicio — 25 de octubre de 2026

**Se ejecutó un único intento físico con ventana común exacta de 30 segundos. La sesión terminó y ambos puertos se cerraron, pero la validación estricta fue rechazada.** Se preservaron arranque, brutos, colas incompletas y errores. No hubo reintentos físicos, recortes, flasheo ni cambios de firmware. Datos resumidos y hashes: [validación](captura_dual_post_reinicio.validacion.json).

## Autorización, ambiente e identidades

El usuario dio una autorización nueva después del intento anterior fallido por permisos y confirmó de nuevo el ambiente tras reiniciar Ubuntu: solo en su cuarto, sentado y quieto frente a la laptop, un RX a cada lado, TX-01 a algo más de 2 m alimentado por cargador de pared, ambos RX por USB. Se registra como declaración del operador; no es una medición ambiental ni ground truth instrumentado.

Se crearon un plan y registros nuevos en `results/local/control-dual-post-reinicio-20261025-intento01/`; el plan anterior, marcado como intento consumido, permanece intacto. El proceso ejecutor tenía UID efectivo 1000 y dialout (20) activo. `os.access(..., effective_ids=True)` confirmó lectura y escritura sin abrir los UART durante esa comprobación. El preflight udev comprobó identidades, VID/PID 1a86:55d3 y dos nodos distintos; el capturador repitió la comprobación antes de cada apertura.

| Rol | Serie USB verificada | Nodo actual |
|---|---|---|
| RX-01 | 5C93199744 | /dev/ttyACM1 |
| RX-02 | 5C93200689 | /dev/ttyACM0 |

Los nodos se resolvieron desde by-id; su numeración difiere del intento anterior. `fuser` no informó procesos antes ni después (retorno 1, stdout/stderr vacíos). Postflight confirmó ambas identidades. No se abrió TX-01.

## Adquisición y rechazo real

Commit de adquisición: `f6bfb0f`. Directorio nuevo: `results/local/captura-dual-30s-post-reinicio-20261025-intento01/`. La envolvente comenzó a las 19:14:56.676487 UTC (14:14:56, Ecuador) y terminó a las 19:15:26.735950 UTC; duró 30.059434036 s, incluida apertura y cierre. La ventana común monotónica fue [663842227682, 693842227682) ns: exactamente 30 s. No implica sincronización RF.

| Resultado | RX-01 | RX-02 |
|---|---:|---:|
| Filas completas, también dentro de la ventana común | 145 | 146 |
| Bytes brutos | 129605 | 130592 |
| Callbacks completos | 0–144 | 0–145 |
| RSSI observado (dBm) | −47 a −45 | −51 a −49 |
| Tasa por intervalo host entre primera y última fila (Hz, aprox.) | 4.93 | 4.96 |
| Cola final sin LF (bytes) | 129 | 129 |
| Línea con texto ROM pegado a un prefijo residual | 1 | 1 |
| Integridad bruto/CSV/resumen/ledger | Aceptada | Aceptada |
| Calidad estricta de sesión completa | Rechazada | Rechazada |

Ambos brutos comienzan con bytes residuales seguidos de `ESP-ROM` en la misma línea física (29 y 28 bytes, respectivamente). Los mensajes de arranque y sus offsets permanecen intactos. Al finalizar quedaron prefijos incompletos de los siguientes registros CSI, callbacks 145 y 146: no se completaron ni incorporaron al CSV. Las colas empiezan en offsets 129476 y 130463. Los ledgers cubren los bytes realmente leídos, incluidas esas colas.

No se detectaron filas CSI completas malformadas, errores de arranque reconocidos, huecos entre callbacks completos, incrementos de descarte local ni reinicios posteriores al primer dato. Esos conteos no anulan el rechazo por arranque pegado y colas incompletas, ni demuestran ausencia de pérdidas RF. El flag original `format_reception_ok=true` de cada receptor se conserva; el auditor estricto completo da false. Adquisición y análisis offline devolvieron 1 por ese rechazo, sin error de ejecución serie registrado. No se atribuye causalidad eléctrica al arranque observado.

Los eventos verifican apertura de ambos RX, supresión del flush de entrada en cada apertura, lectores unidos y puertos cerrados, en ese orden. El proceso de adquisición terminó. Se preservaron todos los bytes devueltos por las lecturas; no se afirma cobertura de bytes nunca leídos.

## Auditoría y visualización offline

El análisis independiente verificó los 15 archivos del bundle por tamaño/SHA-256 y reprodujo exactamente la auditoría guardada durante la adquisición. Pasaron integridad, coincidencia bruto/CSV, continuidad de ledgers, perfil representable y postflight. Se verificó que 40 archivos previos y fuentes siguen idénticos, incluidos los intentos anteriores, los siete archivos de la captura histórica y las fuentes de los tres firmware. El binario instalado sigue sin hash atestado; se conserva ESP-IDF v5.4.

Se generó `results/local/analisis-dual-post-reinicio-20261025-intento01/visualization-offline/index.html`, con la etiqueta **«captura dual controlada con validación estricta rechazada»**. Usa exclusivamente esta sesión, con sus 145/146 filas y vistas LLTF/HT-LTF documentadas de 1×64; no rellena intervalos ni crea filas adicionales. Las nueve copias exportadas de archivos de captura y ledgers coinciden con sus hashes. Se ejecutaron `parsePacket` y `SpectrumCollector` de RuView fijado en `fefb0f9`, licencia MIT, y Node v22.20.0 con hashes comprobados, únicamente en memoria y dentro de Bubblewrap sin red ni dispositivos físicos.

El primer intento de exportación offline fue bloqueado por el sandbox externo al crear namespaces; el exportador se ejecutó después fuera de ese sandbox, manteniendo su propio aislamiento Bubblewrap y usando otra carpeta nueva. Esto no fue un reintento de captura. La carpeta inicial `visualization/` quedó vacía; `nota-exportacion.json` conserva la distinción.

Las cuatro combinaciones RX/LTF pasaron en Firefox headless: identidad, etiqueta de rechazo, límite del selector 144/145, selección de fila CSV 2 y cuatro gráficos renderizados. Se inspeccionó además la captura de pantalla RX-02/HT-LTF. El verificador fue una copia local del histórico, adaptada para leer etiqueta y conteos de esta sesión. El control de Firefox solo escuchó 127.0.0.1 dentro de una red aislada; sin servidor HTTP ni UDP CSI.

No se modificó código de adquisición/análisis ni se repitieron las 124 pruebas históricas: la verificación de esta ejecución comprende la adquisición real, la auditoría independiente, los contratos de exportación y las cuatro vistas del navegador. No se entrenó ni validó presencia. Cualquier otra adquisición requiere una autorización nueva.
