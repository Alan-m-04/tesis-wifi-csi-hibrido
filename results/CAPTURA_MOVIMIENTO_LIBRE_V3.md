# Captura física v3 de movimiento libre — consolidación offline

**Conexión completa rechazada; ventana experimental conforme; resultado global rechazado.** Se consolida el intento existente, sin abrir UART ni adquirir datos en este trabajo. No se altera el [intento sentado anterior](CAPTURA_FISICA_V3.md), sus archivos o su rechazo.

Condición declarada: **«una persona presente, movimiento libre; sesión exploratoria»**. Fuera de la campaña piloto, calibración y entrenamiento. Una ventana conforme acredita el contrato operacional de adquisición; no es presencia detectada, sincronización RF ni aprobación para modelos.

## Procedencia y comprobaciones

Intento `captura-dual-v3-movimiento-libre-20261026T035823Z-intento-unico`, adquirido desde `cef86ef1df0de1a65c34826e04763bf37e0031b4`. Inicio registrado del capturador: **2026-10-26 04:08:25.433469 UTC**; final: **04:08:56.648825 UTC**. Son horas del host, no observaciones de la actividad humana.

[Resumen reconstruible con referencias, tamaños y SHA-256](CAPTURA_MOVIMIENTO_LIBRE_V3.resumen.json). Se verificaron:

- 17 entradas del bundle de adquisición y diez archivos de captura/ledgers/traza; no se sustituyeron originales.
- Las 14 fuentes/perfil de la procedencia contra los blobs del commit de adquisición y el árbol actual; pySerial POSIX fijado por la auditoría histórica y compartido con la sesión sentada.
- Plan autorizado, una sola invocación, cero reintentos y autorización consumida. Se conservan el plan de preparación y su corrección ambiental autorizada.
- Auditoría nueva idéntica a las guardadas en adquisición, análisis y canónico; canónico reconstruido idéntico al original. No se creó otra ventana.
- Las 55 entradas del manifiesto local posterior, que excluye explícitamente su propio hash; no tiene la autoentrada vacía del manifiesto auxiliar de la sesión sentada.
- Copias de exportación y resultados guardados de las cuatro vistas Firefox. No se vuelve a ejecutar el navegador por esta consolidación.

Referencias principales, sin incorporar sus brutos a Git:

| Archivo del intento local | SHA-256 |
|---|---|
| `bundle-manifest.json` | `0957e3f98ea4cf5c72c780504eca296dec361b49d7dad92533c799e1664f2999` |
| `capture-manifest.json` | `138f1f4eeef3382823b4b1496f76f30a64c355b0ba63b7a3eec7c2facc6dbf8c` |
| `plan.json` autorizado | `270b409454366dc8cef23eb80efa15e9861c0f0ad95fae681746fba408ba9819` |
| `provenance.json` | `8219c372ec000c2471dfb039cd09d67b8b3195f4036637499b4ab31e202a9876` |
| `quality.json` de adquisición | `97740e7e701adcd4ceded55d46c9e1475e972fce500c1acf59ce76793223df3b` |
| Manifiesto local posterior `resultado-manifest.json` | `0a48a2b6313ba33ebd6c6ac75e4e87731bc6c86ca25473aa9ac65de4672a787f` |

Los prefijos completos son `results/local/preparacion-dual-v3-movimiento-libre-20261026T035823Z/` y su subdirectorio del intento indicado. El resumen identifica cada ruta, bruto, CSV, ledger, traza, plan, autorización, cierre y auditoría. No contiene matrices IQ ni sustituye esos archivos.

## Transición declarada y límites de etiqueta

El usuario corrigió el momento de inicio al autorizar: comenzaría sus actividades **inmediatamente después de enviar el mensaje**, no estaba confirmado moviéndose al enviarlo. Se preserva [esa declaración original](local/preparacion-dual-v3-movimiento-libre-20261026T035823Z/control/ejecucion-autorizada-intento01/transicion-declarada.json). El instante físico de inicio y fin es desconocido; la hora de registrar la declaración no lo reemplaza. No se afirma movimiento continuo durante los 30 s ni se localizan transiciones desde CSI.

Declaró estar solo y mantener laptop, TX, RX y cables en sus posiciones, TX con cargador de pared y RX por USB. No hay coordenadas medidas, recorrido definido ni atestación de geometría repetida. Son metadatos declarados, no observación instrumental. La autorización fue para un intento, sin resets enviados, reconexiones o cambios de firmware; el texto de arranque conservado no establece su causa.

## Disponibilidad y ventana original

Preflight inmediato por metadatos: RX-01 USB `5C93199744` → `ttyACM0`; RX-02 USB `5C93200689` → `ttyACM1`, VID/PID `1a86:55d3`, dispositivos distintos, `dialout` y R/W efectivos. Se usaron rutas by-id, sin fijar la identidad por el número tty.

| Instante monotónico host | ns |
|---|---:|
| A, antes de primera apertura | 32672592117744 |
| D, límite de disponibilidad | 32682592117744 |
| T0, decisión prospectiva | 32673761518285 |
| T1 | 32703761518285 |

D−A=10 s; T1−T0=**30 s exactos**. Disparo a **1.169400541 s** desde A. READY estricto devuelto a 0.573690927 s / 0.585469120 s para RX-01/RX-02, seguido de las tres filas por receptor. Sin timeout, conflicto de activación o caída de lector registrada.

| Medida | RX-01 | RX-02 |
|---|---:|---:|
| Bytes brutos conservados | 134406 | 134241 |
| Filas completas | 152 | 152 |
| Incluidas en [T0,T1) | 149 | 149 |
| Excluidas completas | 3 preámbulo | 3 preámbulo |
| Filas tardías / cola incompleta | 0 / 0 bytes | 0 / 0 bytes |
| Primera incluida: callback / línea bruta | 3 / 97 | 3 / 99 |
| Última incluida: callback / línea bruta | 151 / 245 | 151 / 247 |
| Primer retorno LF (ns) | 32673972552741 | 32673950624998 |
| Último retorno LF (ns) | 32703750461762 | 32703752309388 |
| Hueco de borde inicial | 211.034456 ms | 189.106713 ms |
| Hueco de borde final | 11.056523 ms | 9.208897 ms |
| Máximo hueco observado, incluidos bordes | 391.360981 ms | 391.837077 ms |

Hay 148 huecos interiores por receptor. El resumen conserva todos sus valores, primeras/últimas lecturas, offsets y hashes por referencia. Las tres filas de disponibilidad quedan fuera; se conserva la regla `primera_lectura>=T0` y `retorno_LF<T1`. 149/30=4.966667 filas/s nominales no implica muestreo uniforme. Los huecos host no miden pérdida RF ni se rellenan. v3 no establece un umbral máximo de silencio; no se aplican retrospectivamente criterios del piloto.

## Calidad de los cuatro aspectos y rechazo conservado

**Integridad registrada conforme:** hashes, bruto/CSV, ledgers y traza coinciden. **Filas completas conformes:** cero CSI malformado, fuente/perfil inesperados, saltos de callback, discontinuidades de reloj local o incremento de descartes registrados. No equivale a cero pérdidas RF.

**Parada/cierre conformes:** ambos terminaron por `lf_boundary`, con cero bytes de finalización adicional, cero colas y sin filas tardías. La política seguía siendo 250 ms/65536 bytes; no hizo falta ejercitar la extensión. Los lectores se reunieron antes de cerrar RX-02 a **04:08:56.610895 UTC** y RX-01 a **04:08:56.648568 UTC**. La comprobación posterior no mostró procesos visibles usando los nodos; no es garantía global de exclusividad. Se confirmó el cierre al usuario antes del análisis offline.

**Conexión/global rechazados:** RX-01 conserva 22 eventos `unrecognized_bytes` y uno `embedded_boot_marker`, incluidos fragmentos de las primeras líneas. RX-02 conserva 22 `unrecognized_bytes`. Todos terminaron antes de T0; no se borran ni se consideran automáticamente corrupción WiFi/firmware. La ventana es **conforme** por las reglas v3, y eso no aprueba la conexión completa. Capturador y analizador devolvieron 1 por el rechazo global, sin reintentos.

## Artefactos y reproducción

[Visualización original local](local/preparacion-dual-v3-movimiento-libre-20261026T035823Z/analisis-movimiento-libre-intento-unico/visualization/index.html), con los dos estados visibles. La nueva [comparación descriptiva](COMPARACION_FISICA_V3.md) conserva esta sesión y la sentada separadas por RX/LTF.

El [reproductor offline](../tools/comparar_fisicas_v3.py) reconstruye este resumen y la comparación desde los originales. Comandos, runtime de gráficos fijado y [verificaciones](COMPARACION_FISICA_V3.validacion.json) se detallan en el informe comparativo. La comprobación del informe no modifica la aceptación de la adquisición. Brutos/canónicos y `results/local` siguen fuera de Git; ninguna autorización de captura vigente.
