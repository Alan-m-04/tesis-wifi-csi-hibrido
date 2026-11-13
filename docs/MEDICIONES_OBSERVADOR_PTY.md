# Observador CSI: integración y mediciones con PTY sintético

Implementación `cf5ee3c`, rama `feat/demo-offline-operacion-20261109`.
Evidencia local: `results/local/mediciones-live-pty-r1/`. Es trabajo sintético,
sin UART físicos, datos reservados, nuevas autorizaciones o ventanas E/S.

## Comprobación parcial del operador

El operador declaró: «El visor sintético abre y muestra LLTF52, RSSI y huecos sin
rellenar». Se conserva como comprobación **parcial**. No confirma todos los
controles, estados, recuperación, rendimiento de navegador, READY o CSI físicos.
El JSON `comprobacion-parcial-operador.json` conserva la declaración y la hora
de registro; no se infiere cuándo se hizo la prueba visual.

## Recorrido revisado

El arnés reutiliza `rx02_service_lab.run_case`, `OwnedPty`, su productor inventado
de 5 Hz y `CheckpointRx02Session`. Ejecuta el servicio real compartido:
`step → StorageGuard/read_ready → journal/checkpoint → operaciones+bruto`.
El backend de prueba sustituye la ruta lógica por su **PTY propio** antes de abrir
el descriptor; el audit hook impide UART físicos y C04–C06. No consulta USB real.

Otro proceso abre los archivos en lectura y reutiliza `Observer`, el framer,
parser/validador y extracción LLTF52. Publica una sola instantánea reemplazable;
el consumidor lee/serializa esa instantánea. No hay llamada, cola o acuse del
consumidor al servicio nativo. Comparten recursos del sistema operativo.

Se corrigió un defecto reproducido primero con una prueba fallida: el observador
rechazaba la operación nativa `storage_check`. Ahora la reconoce como control;
una operación desconocida sigue deteniendo el observador. No cambia la adquisición.

La procedencia del capturador genérico no incluye dominio de reloj/boot. El arnés
atestigua únicamente el reloj monotónico que él mismo inyecta al backend sintético,
en un archivo **externo** ligado a ruta, hashes de plan/procedencia y boot. Se
comprueban además evidencia y transporte sintéticos. La API Python acepta esa
constancia; no hay opción física en el CLI ni edición de procedencia original.

La inspección de C03 y R4 confirma que reutilizan el bucle de `UartSession` y el
decorador de checkpoints, pero tienen contratos/journals y puertas de permiso
propios. **No se ejecutaron esos puntos de entrada** ni se declara compatible el
visor con sus planes físicos. El capturador y sus criterios permanecen intactos.

## Método y resultados

Comparación vigente: `comparacion-periodica-r2/`, seis procesos nativos nuevos,
dos repeticiones de 8 s: baseline/normal/slow y slow/normal/baseline. Servicio a
5 ms, generador de 5 Hz, fragmentos separados 20 ms, observador a 250 ms. Normal:
300 filas y consumidor a 250 ms. Lento: **ocho filas** y consumidor a 2,5 s,
también durante el drenaje final. La reducción explícita del buffer provoca
expulsiones visuales y no cambia el registro del servicio.

| Ejecución | CPU servicio (% de un núcleo) | Intervalo servicio p99 / máximo (ms) | Filas recibidas por consumidor / 40 | Expulsiones del visor |
|---|---:|---:|---:|---:|
| 01 sin observador | 7,109 | 19,074 / 19,657 | — | — |
| 02 normal | 6,884 | 18,845 / 19,430 | 40 | 0 |
| 03 lento | 6,763 | 18,905 / 19,636 | 27 | 32 |
| 04 lento | 6,947 | 18,783 / 20,543 | 27 | 32 |
| 05 normal | 6,623 | 18,625 / 21,710 | 40 | 0 |
| 06 sin observador | 6,414 | 18,914 / 19,258 | — | — |

Las seis conservaron 40 filas generadas y 33 852 bytes brutos por caso, con igual
conteo de bytes enviados/registrados, una apertura/cierre **sintéticos**, integridad
y replay nativos conformes, sin fatal ni ventanas experimentales. El observador
decodificó 40/40 en cada caso y terminó con backlog cero. Los hashes del bundle
tras cerrar la fuente y después del drenaje del observador fueron idénticos.

En normal, la CPU del observador fue 2,80–2,86 % de un núcleo; máximo RSS de proceso
33 392 KiB, instantánea máxima 74 463 bytes y backlog máximo possondeo 66 bytes.
La latencia desde `returned_ns` del último fragmento hasta publicación tuvo p95
234,3–242,3 ms y máximo 245,5 ms. Hasta la primera lectura/serialización por el
consumidor: p95 436,5–445,4 ms y máximo 501,8 ms; cobertura 80/80 entre ambos casos.

En lento, el observador siguió decodificando 40/40 por caso; el consumidor recibió
27/40 y omitió 13 filas, además de saltar 27 revisiones entre consultas. Las 32
expulsiones del buffer incluyen filas que el consumidor ya pudo haber visto:
no equivalen a 32 filas perdidas del original. El p95 hasta consumidor fue
2,30–2,31 s sobre las **27 filas recibidas**, con máximo 2,51 s. Se conserva ese
denominador; las omitidas no se presentan como latencias medidas.

### Ejecución de 30 s

`ventana-30s/` amplía el caso normal para medir una instantánea mayor y el borde
temporal de 30 s. Generó/decodificó/entregó 150/150 filas y conservó 126 412 bytes
brutos, con auditorías conformes y cero backlog final. Hubo una expulsión por
edad al terminar; las 150 filas ya habían llegado al consumidor.

CPU del servicio 6,41 % y del observador 3,84 % de un núcleo; máximo RSS del
observador 33 780 KiB, máximo 150 filas retenidas e instantánea de 276 313 bytes.
Los descriptores del observador permanecieron en 13 en las muestras inicial/final.
Host→publicación: p95 250,5 ms/máximo 254,2 ms. Host→consumidor: p95 462,6 ms/máximo
513,8 ms. Publicar costó p95 9,0 ms; leer/serializar, p95 15,8 ms.

En el intervalo muestreado del observador (30,04 s), `/proc/self/io` registró
17 136 854 bytes en `wchar` y 17 387 520 en `write_bytes`; `read_bytes` fue cero.
La instantánea completa reemplazada en cada sondeo tiene un coste de escritura
visible, aunque el espacio retenido esté acotado. Estos contadores incluyen caché
y atribución del kernel: no prueban rendimiento ni durabilidad del disco físico.

### Definiciones y límites

- CPU del servicio: delta de `process_time_ns` entre muestras durante servicio,
  dividido por su intervalo de pared. `laboratory.json` también incluye CPU/RSS
  de toda la vida del proceso, incluyendo cierre/auditoría; no se confunden.
- Latencia: reloj monotónico host sin escalar; comienza en lectura host, incluye
  persistencia/framing/espera del observador. `first_read_to_decode_ns` incluye
  además el ensamblado de fragmentos. Publicación termina tras reemplazo atómico,
  sin promesa de fsync/durabilidad de la vista.
- Consumidor: archivo y serialización JSON equivalentes al API local. Puede leer
  filas retenidas en una instantánea detenida; **no significa que se dibujaran**.
  No mide RF, firmware, TCP, navegador, render o respuesta humana.
- Cuantiles p95/p99 por rango más próximo, muestras finitas y overflow informado
  (cero en estas ejecuciones). Las métricas de filas registran una sola vez cada
  referencia creciente; no cuentan cada redibujo como otra muestra CSI.
- RSS y descriptores son muestras de ejecuciones cortas; no demuestran estabilidad
  durante horas ni coste al máximo de 300 filas. La variación de CPU entre las dos
  baselines supera su diferencia de medianas con normal: no se infiere coste cero
  ni una mejora causada por el observador. Es un único entorno con caché caliente.

Se conservaron `piloto/` y `comparacion/`, incluyendo la prueba inicialmente
fallida de `storage_check`. El primer arnés aceleraba consultas después del fin
de la fuente; esos resultados quedan como preliminares. La revisión
`consumer-periodic-2` corrigió el muestreo y sustenta la tabla anterior.

## Reproducir y continuar

```bash
.venv/bin/python -B tools/medir_observador_pty.py --output-new results/local/medicion-pty-NUEVA --duration 8 --repetitions 2
.venv/bin/python -B tools/medir_observador_pty.py --output-new results/local/medicion-pty-30s-NUEVA --duration 30 --repetitions 1 --scenario normal
PYTHONPATH=src:tools:tests .venv/bin/python -B -m unittest -v test_csi_live test_csi_observer_lab
.tools/node-v22.20.0/bin/node tests/js/csi_live.test.mjs
```

Pasaron 21 pruebas Python seleccionadas y el arnés JS (DOM/canvas simulado), con
interrupciones, consumidor lento, desconexión/recuperación, controles de reloj y
conservación. No se repitió la suite completa. Los 321 archivos protegidos y los
52 archivos con cambios ajenos conservan sus hashes (`preservacion.json`).

Pendientes: revisión humana de todos los controles/estados en Ubuntu, latencia
real hasta render, carga prolongada y competencia con disco/CPU representativos.
La integración física requiere revisión nueva de contrato, identidad, relojes y
procedencia; la vista seguirá provisional hasta cierre/auditoría. No se habilitó
ni preparó una adquisición. R4 sigue rechazado/cerrado, autorización consumida;
los otros rechazos y declaraciones posteriores permanecen intactos.

Presencia requiere conexiones completas independientes de desarrollo/calibración
y evaluación, separación antes de seleccionar ventanas/métodos y exclusión de
conexiones rechazadas según el contrato vigente. C04–C06 continúan reservadas;
no se usan para desarrollar. Localizar personas requiere datos y validación
espacial propios: ninguna de estas gráficas constituye detección o coordenadas.
