# Ensayo sostenido del visor CSI con PTY

10 de noviembre de 2026 · `feat/demo-offline-operacion-20261109`.

El ensayo usa `CheckpointRx02Session` con el backend de prueba de
`rx02_service_lab`. El productor inventado escribe por un PTY propio a 5 Hz,
en cuatro fragmentos separados por 20 ms. El capturador conserva el bruto y
las operaciones mediante el journal y los checkpoints existentes. El servicio
corre 900 s en reloj monotónico real, con pausa de 5 ms entre llamadas a `step`.
La prueba prescinde de ventanas E/S, etiquetas y equipos físicos.

El observador independiente sondea cada 250 ms, procesa hasta 64 operaciones
por sondeo y retiene hasta ocho filas dentro de una ventana de 30 s. Publica
`latest.json` mediante reemplazo atómico con límite de 2 MiB. El consumidor lee
y serializa la instantánea cada 2,5 s, también durante el drenaje final. Los
contadores distinguen expulsiones del buffer, revisiones omitidas entre consultas
y filas únicas que recibió el consumidor.

```bash
.venv/bin/python -B tools/medir_observador_pty.py \
  --output-new results/local/visor-sostenido-900s-NUEVO \
  --duration 900 --repetitions 1 --scenario slow
```

El arnés conserva el hash de cada byte escrito al PTY y lo compara con el SHA-256
del bruto. La verificación exige duración de servicio suficiente, una apertura y
un cierre confirmados del PTY, integridad y replay nativos, drenaje completo del
observador y coincidencia de todas sus filas con el productor. Comprueba los
límites del buffer y la instantánea, la contabilidad de descartes, las omisiones
del consumidor lento y la ausencia de desborde de los medidores. Vuelve a calcular
los hashes de los archivos del bundle después de detener el observador.

La CPU se calcula como porcentaje de un núcleo entre muestras de cada proceso.
El servicio toma muestras de RSS cada segundo. Observador y consumidor toman
muestras cada diez segundos, con tope de 128. Los medidores retienen hasta
262 144 muestras por métrica. La latencia empieza en `returned_ns` de la lectura
host que completa la fila y termina al decodificarla, publicar la instantánea o
recibirla y serializarla en el consumidor. Los cuantiles del consumidor usan
solo las filas que efectivamente recibió. El alcance de esta medición termina
en el JSON local y deja pendientes RF, TCP, renderizado y equipos físicos.

El directorio `results/local/visor-sostenido-20261110/` conserva el piloto corto,
el ensayo largo y sus logs. `measurement-plan.json` fija los hashes de las fuentes
y `laboratory.json` guarda el perfil de servicio original. `comparison.json`
contiene la comparación de bytes, los recursos muestreados y los cuantiles.

## Resultado auditado al retomar la sesión

El ensayo `ensayo-900s/01-slow` ya había terminado. Pasó los criterios del
arnés `sustained-PTY-3` y se auditó offline sin repetirlo. El cronómetro del
laboratorio registró **900,037767509 s** desde antes de construir la sesión
hasta que terminó el servicio. El journal registró **899,982084422 s** entre
`opened` y `closing`, 18 ms menos que 900 s. El cierre del PTY fue confirmado
una vez, con el lector detenido y el descriptor liberado. Los cinco hashes de
fuentes fijados en el plan coinciden con el árbol de trabajo del commit
`37ce2e6`. El ID `RX02-C01` del bundle pertenece al fixture sintético.

Se repitió el auditor nativo de checkpoints. Verificó el manifiesto, reconstruyó
eventos y resumen a partir de **174.624 operaciones**, y confirmó el recibo de
cierre, **246 checkpoints** y cero bytes de operaciones pendientes. El bruto
contiene **3.789.172 bytes**, con SHA-256
`5b5c09b1519121f0e5f163a0677184956506928543b16f7e9414509907e1ccd7`,
idéntico al medido por el productor y al regenerado offline. El replay clasificó
4.500 filas CSI con IDs consecutivos de 0 a 4.499, dos líneas informativas y un
READY sintético, con cero bytes de cola. El observador procesó 4.500 filas,
consumió el journal completo y conservó las referencias de las ocho últimas.
Los hashes del bundle coinciden con el inventario posterior al drenaje original.

| Proceso | CPU media de un núcleo | RSS inicial, KiB | RSS máximo muestreado, KiB | Muestras |
| --- | ---: | ---: | ---: | ---: |
| Capturador PTY instrumentado | 6,27 % | 31.484 | 49.780 | 897 |
| Observador | 2,22 % | 32.188 | 33.028 | 89 |
| Consumidor lento | 0,81 % | 33.404 | 33.572 | 91 |

El capturador aumentó **18.296 KiB** de RSS durante el servicio. Su pico de
**212.848 KiB** incluye finalización y auditoría en el mismo proceso. El pico
del observador fue **33.404 KiB**, con una instantánea de hasta **15.832 bytes**
y **56.360.366 bytes** de escrituras lógicas entre su primera y última muestra.
El journal nativo tiene topes de historial y operaciones. La corrida comprueba
la cota del buffer visual y documenta el crecimiento del proceso instrumentado
para esta duración. Los descriptores se mantuvieron en 17, 13 y 12 en las
muestras respectivas. Entre llamadas de servicio se midieron 8,34 ms p95 y
25,18 ms de máximo.

| Latencia desde el retorno de lectura host | Filas | p50 | p95 | Máximo |
| --- | ---: | ---: | ---: | ---: |
| Decodificación | 4.500 | 135,03 ms | 237,53 ms | 240,90 ms |
| Publicación del JSON | 4.500 | 136,09 ms | 238,67 ms | 242,31 ms |
| Lectura y serialización por el consumidor | 2.877 | 939,24 ms | 1.668,00 ms | 2.649,05 ms |

El buffer expulsó **4.492 filas** al conservar las últimas ocho. En **360
consultas**, el consumidor recibió **2.877 filas únicas** y dejó **1.623** sin
mostrar (36,1 %). Omitió **3.238 revisiones entre consultas**. Las expulsiones
del buffer incluyen filas que el consumidor alcanzó a leer. El bruto conservó
todas las filas y ningún medidor se desbordó. Los cuantiles proceden de los
medidores guardados. La prueba cubre una sola ejecución larga con consumidor
lento, JSON local y carga PTY sintética. La revisión humana del navegador, la
medición hasta render y una comparación larga con un control equivalente siguen
pendientes.

La auditoría y sus logs nuevos quedaron en
`results/local/visor-sostenido-auditoria-20261110-r1/`. El archivo
`auditoria.json` registra los recálculos de CPU, los límites observados y la
comprobación de hashes. [Revisión de la integración mínima con RX-02](REVISION_VISOR_FISICO_RX02.md).
