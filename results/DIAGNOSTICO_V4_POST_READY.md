# Diagnóstico offline del intento V4-C01 — 28 de octubre de 2026 UTC

Este informe conserva el diagnóstico y la propuesta de aquella sesión.
La propuesta quedó integrada de forma optativa y versionada el 1 de noviembre;
ver [corrección, verificación y pendientes](CORRECCION_V4_POST_READY.md).
El diff de `proposals/` se conserva como artefacto histórico para la base
`15b75cd`; no debe aplicarse sobre el código ya corregido.

El intento conserva **suspensión `post_ready_info:RX-02`**, conexión rechazada,
ningún slot solicitado y ambos puertos cerrados con recibo. La línea causante
es un mensaje de retorno normal de `app_main()` en las fuentes inspeccionadas;
v4 lo clasifica como `info` y suspende cualquier `info` posterior a READY.
Esto identifica la incompatibilidad de gramática, sin atribuir una causa
eléctrica al arranque observado ni acreditar el binario instalado.

Solo se leyeron los registros existentes. No se abrió UART, relanzó el intento,
reconectó, reseteó, cambió firmware o calibró el detector. El marcador del único
intento consumido permanece intacto.

## Evidencia y reproducción original

Base limpia al iniciar: rama `feat/backend-uart-presencia-v4`, commit
`15b75cd6ec6ad125204cf92d93e27f531cbee49b`. Bundle local original:
`results/local/v4-c01-vacia-sentado-20261028T014057Z/`.

La auditoría original pasa integridad y reproducción: 112 operaciones, 193
eventos, `fatal=post_ready_info:RX-02`, `windows=[]`, disponibilidad inicial
nunca alcanzada. Pasar integridad **no aprueba adquisición o presencia**.
Los 11 hashes de fuentes del journal y los cuatro del transporte coinciden
con las fuentes actuales. Las fuentes firmware no están atestadas por esa
procedencia: su comparación con Git es inspección del código disponible.

Artefactos nuevos, separados de la adquisición, en
`results/local/diagnostico-v4-post-ready-20261028T035329Z/`:

- `preservacion-antes.json`: hashes y tamaños de 48 archivos del intento,
  preparación/autorización y ambas prácticas de sonidos.
- `auditoria-original.json`: reproducción con el código original intacto.
- `forense.json`: bytes, offsets, lecturas, eventos, hashes y contraste de fuentes.
- `pruebas-offline.log`: salida completa de las 176 pruebas.
- `preservacion-despues.json`: comprobación final de preservación.

## Línea exacta, bytes y orden

RX-02, línea **92**, evento **183** (índices `seq` desde cero):

```python
b'I (545) main_task: Returned from app_main()\r\n'
```

Son **45 bytes**, rango **[4624, 4669)** del bruto RX-02 (offsets desde cero).
Incluye CR y LF, sin ANSI ni prefijo binario en esa línea.

```text
49 20 28 35 34 35 29 20 6d 61 69 6e 5f 74 61 73 6b 3a 20 52 65 74 75 72 6e 65 64 20 66 72 6f 6d 20 61 70 70 5f 6d 61 69 6e 28 29 0d 0a
```

SHA-256 de la línea, incluyendo terminador:
`82ba255a7ab0a2cb2f27dccb58898e4b7798e1c4e877722ebc8b2e7ce329522d`.

| RX-02 | Línea | Bytes [inicio, fin) | Evento | Contenido |
|---|---:|---|---:|---|
| Cabecera CSV | 88 | [4179, 4405) | 173 | cabecera exacta, neutral |
| Inicialización Wi-Fi | 89 | [4405, 4437) | 179 | `I (526) wifi:ic_enable_sniffer` |
| Identidad informada | 90 | [4437, 4527) | 180 | `receiver_mac=10:20:ba:7a:c4:88 secondary=256 (unused in HT20)` |
| READY | 91 | [4527, 4624) | 182 | `I (536) csi_recv_02: RX-02 READY channel=11 HT20 UART0=115200 raw CSI; source=1a:00:00:00:00:00` |
| Retorno de app_main | 92 | [4624, 4669) | 183 | mensaje causante de la suspensión |
| Suspensión | — | — | 184 | `post_ready_info:RX-02` |

No hay filas CSI completas, ni siquiera el token `CSI_DATA,`, en ninguno de los
dos brutos. RX-01 termina con la cabecera CSV (línea 89, [4243, 4469)) y una cola
de **un byte `49` hexadecimal (`I`)** en offset 4469. No permite afirmar que
RX-01 haya emitido READY: no se reconstruye el resto de esa línea.

## Tiempos registrados

Son nanosegundos monotónicos del host; no son tiempos de llegada RF ni permiten
fechar un reset eléctrico. `A = 31402717400044` es la operación `begin`.

| Evidencia | Monotonic ns |
|---|---:|
| READY: inicio de su primera lectura (índice 26) | 31403307149082 |
| Inicio de lectura que completa READY y contiene toda la línea 92 (índice 27) | 31403325310735 |
| Retorno de esa lectura | 31403325373907 |
| Procesamiento de READY, línea 92 y suspensión | 31403327961087 |
| Orden de detener lectura | 31403333120297 |
| Cierre confirmado RX-01 | 31403376246261 |
| Cierre confirmado RX-02 y evento de ambos cerrados | 31403381114996 |

La lectura RX-02 índice 27 corresponde a operación **105**, offset 4534,
135 bytes: final de READY seguido del mensaje entero. La suspensión se procesa
a **610,561043 ms desde A**. READY y retorno comparten retorno de lectura y reloj
de procesamiento: no se puede inferir un intervalo host entre sus emisiones.
Los números `536` y `545` impresos por el dispositivo difieren en 9 ms; no se
equiparan a timestamps CSI ni se sincronizan con el host.

El recibo declara `pyserial_close_returned_and_all_fds_released` y lector
detenido para ambos RX; `both_confirmed=true`, `timer_is_close_proof=false`.
La suspensión y el cierre confirmado son hechos distintos. Los resultados del
reproductor de sonidos no demuestran audibilidad humana durante este intento.

Brutos originales:

- RX-01: 4470 bytes, SHA-256
  `67eef193aa3d15638f4f212757ede7713f7de7abfd3250977b454d73ea3d39c4`.
- RX-02: 4669 bytes, SHA-256
  `2b4cade6d115b28033db17f592e3b28d8723b3523d183b65a52c75aebc7df719`.

## Contraste de firmware, SDK y gramática

En [RX-02 app_main.c](../firmware/csi_recv_02/main/app_main.c), líneas 272–292,
se crea la tarea `csi_writer`, se inicializa CSI, se consulta canal/banda,
se aborta ante incompatibilidad, se imprime identidad y finalmente READY;
`app_main()` termina a continuación. En
[RX-01 app_main.c](../firmware/csi_recv/main/app_main.c), líneas 271–275,
READY precede a `wifi_csi_init()` y después retorna `app_main()`. El orden no
es idéntico en ambos receptores; el mensaje observado aquí es de RX-02.

ESP-IDF local coincide con el commit fijado
`67c1de1eebe095d554d281952fde63c16ee2dca0` (v5.4). En
`components/freertos/app_startup.c`, líneas 206–210:

```c
ESP_LOGI(MAIN_TAG, "Calling app_main()");
extern void app_main(void);
app_main();
ESP_LOGI(MAIN_TAG, "Returned from app_main()");
vTaskDelete(NULL);
```

El retorno borra la tarea principal en esa fuente; no es una orden de reset ni
termina por sí mismo la tarea escritora CSI creada por la aplicación. El SDK y
ambas fuentes firmware coinciden byte a byte con sus blobs Git; hashes en
`forense.json`. `installed_firmware_attested=false` sigue siendo un límite:
la concordancia textual no prueba qué binario estaba instalado.

En [la gramática compartida](../src/availability_window.py), `classify_line`
acepta el texto como `LOG` informativo. No contiene marcadores de reset, READY
conflictivo o error. En [el reductor v4](../src/persistent_presence_v4.py),
`feed` suspende por cualquier `info` no neutral posterior al primer READY.
Es exactamente el comportamiento publicado en el
[protocolo v4](../docs/PROTOCOLO_PRESENCIA_PERSISTENTE_V4.md), apartado de precisión.
El rechazo era conforme a aquella regla; se conserva.

Hay evidencia separada de arranque **anterior** a READY:

- Ambos brutos empiezan con bytes no UTF-8 seguidos de `ESP-ROM:esp32s3-20210327`.
- RX-01 línea 3 [122,172), evento 4, y RX-02 línea 3 [134,184), evento 17:
  `rst:0x1 (POWERON),boot:0x8 (SPI_FAST_FLASH_BOOT)\r\n`.
- Esos marcadores no aparecen después del READY observado. No prueban cuándo
  ocurrió el evento respecto de la apertura ni su causa; no se atribuyen a
  DTR/RTS, alimentación o acción humana. El registro de apertura solicita
  DTR/RTS `false` y registra retorno de ioctl, sin medir niveles/transitorios.

La línea 92 es compatible con **fin normal de inicialización** según las fuentes.
No aporta por sí misma evidencia de reset, error o cambio de configuración.
No hay líneas clasificadas `error` en estos registros. Tampoco se infiere
ausencia de fallos físicos a partir del silencio posterior: la lectura cesó.

La conexión ya tenía motivos `format` previos a READY: 20 líneas inválidas en
RX-01 y 21 en RX-02. Además de los prefijos binarios, la gramática exige tag
alfanumérico/guion bajo y espacio tras `:`; por ello rechaza textos como
`boot.esp32s3: ...` y `wifi:ic_enable_sniffer`. Algunos describen inicialización
o configuración inicial, pero su mera presencia no demuestra un cambio
posterior de configuración. La cola de RX-01 añade `incomplete_tail:RX-01` al
cierre. **No se corrigen ni se eliminan esos motivos en esta propuesta.**

## Corrección mínima propuesta, sin activar

[Diff para revisión](../proposals/v4-app-main-return.patch). Se aplica en una
copia temporal durante las pruebas; el backend, CLI y auditor actuales siguen
usando el código original. No es un nuevo permiso ni un comando de adquisición.

Contrato de la excepción propuesta:

1. Solo v4. Bytes completos coincidentes con
   `I ([0-9]+) main_task: Returned from app_main()` y LF o CRLF. Sin ANSI,
   sufijos, otros tags, niveles W/E ni otras frases `main_task`.
2. Únicamente la línea inmediatamente posterior al primer READY estricto de
   ese RX, antes de cualquier CSI de ese RX y de disponibilidad inicial,
   dentro de los 10 s iniciales, sin fallo previo. La posición hace que solo
   pueda admitirse una vez. Un duplicado o mensaje posterior a CSI suspende.
3. Mantener su clasificación informativa y todos los bytes, offsets, lecturas,
   hashes y tiempos; anotar el patrón reconocido, sin declararlo disponibilidad.
4. Seguir exigiendo READY y tres filas frescas de ambos RX. Sin modificar
   timeouts, ventanas, cobertura, etiquetas, detección de discontinuidades,
   errores/resets, almacenamiento, cierres o política de reintentos.
5. No modificar la gramática compartida ni v1/v2/v3. Ninguna aceptación genérica
   de logs. Ninguna eliminación de residuos o selección de intervalos.

La excepción resuelve el caso sintético del mensaje normal, pero **no habría
convertido este intento en una conexión conforme**: conserva sus residuos,
falta de disponibilidad/CSI y cola. No se reinterpretan retrospectivamente los
eventos ni las decisiones de cierre del intento con la regla candidata.

Antes de integrar la propuesta para uso físico debe revisarse este contrato,
fijar una revisión explícita de gramática en la procedencia y conservar la
selección del auditor histórico para los bundles anteriores. El diff es una
propuesta probada en copia, no una migración de auditoría lista para activar.
No se cambia el ejecutable de adquisición con una regla silenciosa.

## Verificación y siguiente revisión

Las 13 pruebas originales de la propuesta, ahora ampliadas en
[pruebas de la política integrada](../tests/test_v4_line_policy.py):
rechazo original exacto, todos los cortes de byte en READY+retorno para ambos
RX, offsets/hash conservados, tres filas frescas obligatorias, READY ausente,
timeout sin filas, frontera de 10 s, duplicados/interposición/CSI anterior,
variantes negativas, reset/error/perfil/ANSI, línea sobredimensionada, watchdog
y auditoría inmutable del intento local. Fixtures candidatos exclusivamente
sintéticos; no se calibra con los registros físicos.

Las 163 pruebas anteriores de memoria, dobles de serial y PTY propios más esas
13 pasan: **176 pruebas, cero omisiones, 14,750 s**. El test del bundle local
solo verifica archivos; se omite expresamente si esa evidencia no está presente
en otro checkout. Comando ejecutado:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python -B -m unittest \
  test_uart_v4 test_persistent_presence_v4 test_availability_window \
  test_controlled_v2 test_controlled_v3 test_capture_preparation \
  test_capture_boundaries test_boundary_diagnostic test_v4_app_main_return_proposal -v
```

`git apply --check proposals/v4-app-main-return.patch` pasa sin aplicar el diff.
`./tools/offline_sandbox.sh /usr/bin/true` falla con returncode 1:
`bwrap: No permissions to create a new namespace`. Se conserva ese fallo; las
pruebas directas en el entorno restringido **no acreditan aislamiento Bubblewrap**.

Revisión concreta pendiente: decidir la excepción estrecha y su versionado;
evaluar por separado los motivos de formato inicial sin ampliar permisos de
logs; preservar el auditor/rechazo histórico; solo entonces preparar otro
intento y solicitar autorización nueva. Faltan disponibilidad real de ambos RX,
primera ventana vacía/sentada y cobertura/etiquetas de una campaña. Ninguna se
considera realizada. La declaración humana de audibilidad de PRUEBA02 y la
incertidumbre de PRUEBA01 se conservan; no se convierten en verificaciones
automáticas ni pruebas nuevas de audibilidad durante esta sesión.
