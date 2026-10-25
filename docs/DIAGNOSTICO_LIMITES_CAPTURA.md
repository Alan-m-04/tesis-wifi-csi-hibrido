# Diagnóstico offline de inicio y parada — intento rechazado conservado

25 de octubre de 2026. El commit `cf36c30` se subió primero a `origin/feat/preparacion-captura-dual`. El diagnóstico posterior usa exclusivamente archivos existentes y PTY privados. **No se abrió UART físico, no hubo otra captura, no se modificó firmware y el intento sigue rechazado.** Resumen verificable: [diagnóstico con offsets, ledgers, tiempos y hashes](../results/diagnostico_limites_post_reinicio.json). El [informe original](../results/CAPTURA_DUAL_POST_REINICIO.md) permanece intacto.

## Qué se demuestra y qué sigue sin determinarse

| Cuestión | Evidencia y conclusión |
|---|---|
| Fragmento pendiente al comenzar | En la primera lectura ya aparecen 3 bytes en RX-01 y 2 en RX-02, separados en el ledger de las lecturas posteriores de ROM. Esos bytes son reales en la entrada del host; no los fabrica el parser. No se demuestra que estuvieran pendientes **antes de abrir/configurar** el dispositivo. |
| Línea interrumpida al detener el capturador | Demostrado en el registro: ambos lectores terminan con una línea sin LF después de una lectura que cruza el deadline. El bucle decide parar por tiempo y deja de leer con esa línea pendiente. En PTY se reproduce con el resto de una línea válida disponible posteriormente. En el experimento físico no se observó ese resto y no se puede demostrar que llegara a emitirse. |
| Corrupción durante la ventana | No se demuestra corrupción de las 145/146 filas completas. Su bruto coincide con CSV; todas pasan formato y perfil y no hay huecos de callback, reinicio posterior ni texto ajeno entre esas filas. Esto no prueba integridad del cable ni permite excluir alteraciones que conservaran un formato válido. La ventana común también contiene parte del arranque y la cola, no solo filas completas. |
| Causa del arranque/residuos iniciales | Indeterminada. No hay traza anterior a la apertura/configuración ni medición eléctrica o USB. No se atribuye a WiFi, al firmware, a DTR/RTS ni a una avería de placa. POWERON en el texto no demuestra causalidad. |

## Inicio: bytes y tiempos realmente registrados

Se verificaron tamaños y SHA-256 de los 15 archivos del bundle antes de interpretar los datos. La ventana común es [663842227682, 693842227682) ns del reloj monotónico host. Todos los offsets de bytes son base cero, con extremo final excluido.

| Dato | RX-01 | RX-02 |
|---|---:|---:|
| Evento `opened`, posterior al retorno de `open()` (ns) | 663836561532 | 663841737359 |
| Prefijo inicial, offset | [0,3) | [0,2) |
| Firma residual hexadecimal | `4c 13 00` | `31 f2` |
| Inicio de primera lectura (ns) | 663837155074 | 663842182611 |
| Retorno de primera lectura (ns) | 663837288612 | 663842278178 |
| Retorno después de `opened` | 0.727080 ms | 0.540819 ms |
| Línea física inicial completa | [0,29) | [0,28) |
| Lecturas que forman esa línea | 3 + 1 + 25 bytes | 2 + 1 + 25 bytes |
| Primera línea CSI completa (número base uno) | 92 | 93 |

El primer byte `E` de `ESP-ROM:` se recibió en la lectura siguiente al prefijo, y los 25 bytes restantes de esa línea, incluido CRLF, en otra lectura. El parser une los bytes porque entre el prefijo y ROM **no existe LF**: no crea esa unión ni elimina un separador. El prefijo de RX-01 se recibió antes de comenzar la ventana común; la primera lectura de RX-02 la atravesó y retornó 50.496 µs después de iniciarla. No se desplazan esos tiempos para clasificar todo como preámbulo.

La subclase activa suprimió un flush de entrada por apertura; esa decisión conserva residuos observables. El código pySerial 3.5 inspeccionado localmente configura el dispositivo y solicita DTR/RTS antes del hook de flush suprimido. Solo se conoce el evento posterior a `open()`: esos bytes podrían haber estado pendientes o haber aparecido durante la apertura/configuración. Las pruebas PTY demuestran que un prefijo escrito antes de abrir puede sobrevivir, seguido de ROM; demuestran un mecanismo posible, no la causa de esta sesión física. No se demuestra que el prefijo sea parte de una CSI anterior.

## Parada: por qué hay 129 bytes en ambos RX

| Dato | RX-01 | RX-02 |
|---|---:|---:|
| Cola sin LF | [129476,129605) | [130463,130592) |
| Callback declarado en el encabezado incompleto | 145 | 146 |
| Bytes preservados | 129 | 129 |
| Lecturas que forman la cola | 1 + 127 + 1 | 1 + 127 + 1 |
| Inicio de última lectura, relativo al deadline | −2.866620 ms | −3.000515 ms |
| Retorno de última lectura, relativo al deadline | +7.557702 ms | +7.688908 ms |
| Desde último retorno hasta lectores unidos | 3.147011 ms | 3.015805 ms |
| Desde último retorno hasta evento puertos cerrados | 42.401413 ms | 42.270207 ms |
| Última línea completa, bytes | 969 | 882 |

Ambas colas contienen un encabezado CSI y solo el comienzo de la lista; `[` está en el byte relativo 92. Sus últimos bytes son `0x32` y `0x31`. No hay `]`, cierre de comillas ni LF final. No se infieren valores faltantes ni matrices a partir de esos prefijos. El JSON local contiene el hex completo para inspección; Git conserva offsets, tamaños y hashes, sin matrices ni fragmentos CSI completos.

El lector en `src/capture_csi_multi.py` solicita `min(in_waiting or 1, 16384)` y vuelve a evaluar el deadline antes de la siguiente lectura. Cuando retorna la última lectura, ya se superó el límite; se guarda ese byte, se registra el ledger y se abandona el bucle aunque quede una línea pendiente. **El cese de lectura precede al cierre del puerto unos 42 ms**: los bytes no desaparecen del bruto durante `close()`. No se conoce qué había en el dispositivo/driver durante ese intervalo, porque ya no se leía.

La longitud 129 se explica aritméticamente por el patrón observado 1+127+1 y el instante de parada. No existe un límite de trama de 129 bytes en el capturador inspeccionado. Son frecuentes lecturas de 1/127 bytes en toda la sesión (1053/895 en RX-01 y 1067/907 en RX-02), pero el ledger no registra tamaños solicitados ni eventos USB. No demuestra una FIFO o paquete USB de 128 bytes, su causa física ni un tamaño fijo universal. Las pruebas reproducen también colas de 17, 128 y 257 bytes.

Es una **limitación demostrada de delimitación de parada**: el protocolo v1 respeta su corte temporal, pero no garantiza terminar en LF. No se demuestra que trunque un chunk ya devuelto por `read()` ni que corrompa el parser. El remanente físico no fue observado; por eso no se afirma que el host sea la única causa posible de una matriz incompleta.

## Tres resultados que se conservan separados

1. **Integridad del transporte registrado:** hashes, offsets contiguos del ledger, tiempos y correspondencia de filas bruto/CSV pasan para ambos RX. No equivale a demostrar la ausencia de pérdidas o corrupción antes de que `read()` devolviera los bytes. El registro solo contiene lecturas no vacías, no todas las peticiones/timeout.
2. **Calidad de filas completas:** 145/146 filas, 256 escalares int8, metadatos/perfil documentado y flags originales válidos. Desde la primera fila CSI hasta la última completa no hay otras líneas completas ni bytes UTF-8 inválidos. No se presenta cada callback como secuencia TX ni se deduce pérdida RF de estos conteos.
3. **Calidad global:** rechazada por la primera línea con residuos pegados a ROM y por las colas sin LF. Esta conclusión, sus archivos y su visualización no se cambian. Los límites de fase/modelo LTF, sincronización y firmware instalado sin hash atestado siguen vigentes.

## Propuesta ensayada antes de otra adquisición

Se implementó un **prototipo offline sin integrar al protocolo v1**, `src/bounded_frame_reader.py`, con 250 ms de espera máxima contados desde el deadline nominal y un máximo adicional de 65536 bytes. No hay CLI física que lo active y no abre ni cierra puertos. Su política es:

1. Mantener exactamente los 30 s nominales. Si al detectar el deadline no queda línea pendiente, terminar sin esperar una nueva trama.
2. Si queda una línea pendiente, continuar hasta el primer LF con lecturas de un byte, un deadline absoluto fijo y un presupuesto de bytes. El timeout de cada lectura se limita al tiempo restante; el límite nunca se desplaza por recibir datos. No hay drenaje hasta silencio ni reintentos.
3. Persistir íntegro cada chunk ya leído, incluidos sufijos recibidos por una lectura iniciada antes del deadline. Si ese chunk acaba en mitad de otra línea, la finalización acotada completa esa línea pendiente; no se borra su prefijo para aparentar un límite limpio.
4. Registrar offsets, tamaños solicitados/devueltos, inicio/retorno monotónico, UTC real, fase nominal/finalización y motivo/tiempo real de parada. Una fila completada después del deadline conserva ese tiempo y no se cuenta dentro de los 30 s. Abortos y errores no inician una espera de finalización.
5. Al agotar tiempo/bytes sin LF, conservar la cola y rechazar. Llegar a LF solo establece un límite de línea: una fila malformada o un arranque residual siguen rechazados.

El backend debe respetar un timeout finito; la planificación del sistema operativo puede demorar el retorno. No es una garantía de tiempo real duro. El prototipo devuelve el tiempo real de parada además del deadline. El límite de 250 ms es una política propuesta y ensayada, no una medición de latencia física ni una promesa de terminar cualquier trama.

**Recomendación concreta: no repetir todavía el protocolo v1 esperando que las colas desaparezcan.** Antes de una adquisición futura, integrar esta política como un protocolo nuevo y explícito, con metadatos y auditoría que distingan ventana común, finalización y envolvente total; conservar los criterios estrictos y probar su coordinador dual/cierre también ante error. Añadir eventos antes/después de abrir y parada por lector para mejorar atribución temporal. No limpiar el prefijo inicial: documentarlo como fragmento independiente por offsets y seguir rechazando la sesión si aparece. Esta propuesta no demuestra ni corrige su causa.

La futura integración y sus resultados deben revisarse antes de solicitar una autorización nueva. No hay autorización vigente para otra adquisición. No se recomienda cambiar WiFi, firmware ni líneas eléctricas a partir de esta evidencia.

## Pruebas realizadas y reproducción

**142 pruebas aprobadas, cero fallos y cero omisiones: 111 Python y 31 Node.** Incluyen las 124 existentes, 16 nuevas sintéticas (cuatro con PTY privados) y dos nuevas regresiones sobre la captura física conservada. Tras añadir al diagnóstico el conteo de líneas/UTF-8 se repitieron las dos regresiones afectadas y pasaron.

Se ensayaron: bytes pendientes antes de abrir PTY, fragmentación de lectura separada de ROM, parada a mitad de línea, patrón 1+127+1, tamaños de cola diferentes, lectura completa que retorna después del límite, finalización hasta LF dejando la línea siguiente sin consumir, timeout sin LF, flujo continuo sin LF limitado por bytes, sufijo de otra línea en chunk en vuelo, aborto y error sin reintento. Un caso con CSI malformada y ROM pegada sigue fallando aunque se alcance LF.

```bash
./tools/test_offline.sh results/local/visualizacion-csi-entrega/canonical.json
.venv/bin/python -B tools/diagnosticar_limites_captura.py \
  --run results/local/captura-dual-30s-post-reinicio-20261025-intento01 \
  --output-new results/local/diagnostico-limites-otra-carpeta-nueva
```

El conjunto usa Bubblewrap: fuentes/datos de solo lectura, red aislada y `/dev` privado con PTY sintéticos. El sandbox externo bloqueó inicialmente namespaces; se ejecutaron las pruebas fuera de él manteniendo el aislamiento propio de Bubblewrap. Los logs, el hex inspeccionado y sus hashes permanecen en `results/local/diagnostico-limites-post-reinicio-20261025/`. Los 40 archivos fijados anteriormente, las fuentes de adquisición/validación y firmware, el plan consumido y el bundle original siguen idénticos. No se entrenó ni se validó presencia.
