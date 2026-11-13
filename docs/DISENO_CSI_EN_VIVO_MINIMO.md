# Diseño mínimo para observar CSI durante una futura adquisición

**Diseño inicial, implementado después solo como demostración sintética.**
Véanse [comandos, pruebas y límites actuales](OBSERVADOR_CSI_SINTETICO.md).
La entrada física continúa deshabilitada y no se ejecutó físicamente. No crea intento,
preflight, permiso, endpoint de adquisición o botón de captura. Primero debe
completarse la práctica humana pendiente y revisarse cualquier futura ejecución.
El primer alcance sería describir CSI/RSSI y calidad, sin decisiones de presencia.

## Reutilización y límite entre procesos

```mermaid
flowchart LR
  C[Capturador existente y journal] --> F[Bruto y operations.jsonl]
  F --> O[Observador separado: solo lectura]
  O --> S[Última instantánea acotada]
  S --> B[Backend localhost]
  B --> U[Vista CSI provisional]
```

El capturador conserva en exclusiva UART, relojes de decisión, validación,
notificador, almacenamiento y cierre. No espera al observador ni al navegador.
La interfaz no puede solicitar, detener o reabrir la adquisición. Se reutilizaría
la sesión/capturador ya revisada que corresponda al futuro plan, sin un ejecutor
nuevo por intento. Ninguna ruta actual del panel activa este diseño.

El observador sería otro proceso, con acceso **solo de lectura** a un bundle de
desarrollo explícitamente seleccionado y nuevo. No busca campañas ni abre
C04–C06. Mantiene su memoria/archivos derivados fuera del directorio adquirido.
No modifica journal, manifiestos, etiquetas, permisos o fuentes de adquisición.

## Qué permiten realmente las fuentes actuales

En [V4Journal.command](../src/presence_v4_journal.py), un chunk bruto se escribe,
vacía y sincroniza antes de registrar la operación. El registro JSONL contiene
`seq`, `op`, `now_ns` y `data`; para `chunk` conserva receptor, offset, tamaño,
hash y tiempos host `started_ns`/`returned_ns`. El replay existente verifica
secuencia/referencias y reconstruye `machine.apply` desde esos bytes.

[CheckpointJournal](../src/rx02_checkpoint_journal.py) mantiene fsync de cada
chunk bruto y flush de cada operación, pero fsync del journal solo en barreras
y presupuesto de bytes. **No publica durante la adquisición un marcador durable
por operación**: `checkpoint-status.json`, `events.json` y el manifiesto completo
se escriben al finalizar. No se puede usar su ausencia como fallo ni asumir
durabilidad de una línea JSONL visible. Los auditores de bundle completo
requieren el cierre y no son una API de streaming.

Por tanto, la primera vista sería **CSI PROVISIONAL · SIN DETECTOR CALIBRADO**:
solo observación de registros visibles completos y bruto verificado, sin
elegibilidad final ni promesa de recuperación ante pérdida de energía. La calidad
final se publicaría después del cierre y la auditoría existente.

## Recorrido mínimo del observador

1. Validar plan/procedencia/versión del bundle seleccionado; comenzar con un solo
   protocolo RX-02 explícito, sin adaptación silenciosa de R1–R4 o protocolos duales.
2. Leer incrementalmente `operations.jsonl` por offset. Conservar una última línea
   incompleta para el siguiente sondeo; no completarla artificialmente. Acotar
   registro/buffer con los límites de esa revisión. Ante truncado, secuencia o
   referencia contradictoria, suspender solo la vista y mostrar error.
3. Para cada operación `chunk`, comprobar que el segmento bruto referenciado
   existe completo y coincide en tamaño/hash. Reutilizar el framer/reductor
   correspondiente en memoria y su parser, leyendo las operaciones registradas;
   no inicializar una sesión UART ni ejecutar sus efectos de audio/control.
   Conservar residuos, máscaras, primera lectura, retorno y reloj de decisión.
4. Reutilizar `documented_ht20_layout`, `canonical_block`, `row_mean` y los
   renderizadores existentes. Exponer LLTF52/RSSI, identidad, tiempos y estado
   provisional. Los tonos inválidos siguen ausentes; no normalizar, interpolar
   ni interpretar frecuencia de filas host como frecuencia RF.
5. Publicar una instantánea derivada acotada con conexión, RX/serie, versión,
   secuencia/offset leído, referencias, máscaras, timestamps originales como
   cadenas decimales y estado de observación. Distinguir tiempos de adquisición
   y de publicación. No calcular edad entre relojes/boots incompatibles.

## Actualización sin esperas en adquisición

Un buzón de **una instantánea reemplazable** entre observador y servidor evita
una cola creciente. Como propuesta de interfaz, sondeo de hasta 4 Hz y ventana
visual acotada a 30 s/máximo 300 filas, sujetos a prueba sintética: son límites
del visor, no criterios ni frecuencia de adquisición. Si el navegador va lento,
se omiten actualizaciones visuales y se informa cuántas/secuencias se omitieron;
el bruto original no pierde filas. Los huecos y la selección visual quedan
explícitos. Cerrar/pausar la vista no detiene el capturador.

El backend serviría solo la última instantánea; ningún GET espera un nuevo dato
del capturador. Sin novedades muestra última secuencia/hora y «sin actualización»,
sin convertirlo en ausencia de personas o cierre físico. Un fallo del visor no
produce comandos en el journal experimental. Los metadatos USB actuales, esta
vista provisional y la reproducción histórica siguen siendo dominios distintos.

Procesos separados eliminan esperas/locks introducidos por la interfaz en el
lector. No demuestran ausencia de competencia por CPU/disco: debe medirse con
carga sintética y, antes de cualquier sesión física, revisar el impacto. No se
añaden callbacks de renderizado, decodificación pesada, sockets ni fsync nuevos
al bucle de adquisición.

## Trabajo pendiente antes de habilitarlo

Pruebas sintéticas de JSONL partido, bruto aún incompleto, hashes erróneos,
secuencias, máscara inválida, rotación/truncado, cierres y reinicio del visor;
navegador lento/desconectado, memoria acotada y comparación del mismo journal
con/sin visor. Después, pruebas PTY propias de carga/latencia y auditoría final,
manteniendo los criterios experimentales. Las pruebas sintéticas/PTY realizadas
después de este diseño y los pendientes físicos están en el informe enlazado
arriba. No se afirma rendimiento de una adquisición física.

Una futura ejecución necesita revisión de integración y autorización física
nuevas. La presencia exige además calibración/evaluación independientes; la
localización exige un método y evidencia espacial propios. Nada de esto se
deduce de USB, READY, un mapa de amplitud o una prueba sintética de la cabeza.
