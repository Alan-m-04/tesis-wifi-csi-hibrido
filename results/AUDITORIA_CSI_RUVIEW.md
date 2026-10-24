# Auditoría offline CSI / RuView

Segundo hito, 24 de octubre de 2026. Base `74d612a87fa02021a30a7a034595e4aa5575dbb7`, rama `feat/compatibilidad-csi-ruview`. Fuentes externas fijadas en [FUENTES_CSI_RUVIEW.json](../docs/FUENTES_CSI_RUVIEW.json), decisiones y tabla de los 31 campos en [COMPATIBILIDAD_CSI_RUVIEW.md](../docs/COMPATIBILIDAD_CSI_RUVIEW.md).

## Resultado técnico

Se demuestra la lectura matemática **Im/Re → Re+jIm** preservada por ambos firmware y el CSV. Se documenta el modelo HT20 LLTF+HT-LTF condicionado a metadatos y configuración explícitos. Se rechaza interpretar los 128 pares como 128 subportadoras únicas o como dos antenas. La geometría no se cambia y no se implementa ningún paquete real para RuView.

RuView `fefb0f918eefa7db6daef8cc83787fc7d6f74187`, checkout separado limpio, licencia raíz MIT. El serializador copia Im/Re, mientras Rust hardware, Rust servidor y Python binario archivado interpretan Re/Im. Hay reflexión/rotación de fase invisible a amplitud. El conversor Python JSONL/RVCSI sí interpreta Im/Re; no admite la misma permuta. JavaScript graph no calcula fase; spectrogram y UI tienen offsets/tipos incompatibles con el contrato real. La heurística de banda/índices del Rust hardware no conserva los dos LTF HT20. El filtro propio está activo y el upstream S3 desactivado; no se puede recuperar a posteriori la independencia entre tonos.

## Referencia física dual preservada

Los siete archivos locales coinciden con el manifiesto anterior. El auditor compara CSV y bruto, identidades, hashes y resultados originales. No se elimina el arranque ni la línea residual. El informe JSON separado contiene histogramas completos y controles estrictos.

| Métrica | RX-01 | RX-02 |
|---|---:|---:|
| Filas válidas / ventana solicitada | 292 / 60 s | 291 / 60 s |
| Media por ventana | 4,867 Hz | 4,850 Hz |
| Longitud / tipo escalar | 256 / int8 | 256 / int8 |
| sig_mode / bandwidth / secondary / STBC | 1 / 0 / 0 / 0 | 1 / 0 / 0 / 0 |
| MCS / ant / first_word_invalid / rx_state | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| Filas consistentes con modelo documentado HT20 | 292 | 291 |
| Rango de escalares observado | -75..73 | -66..66 |
| Escalares en -128 o +127 | 0 | 0 |
| Pares completos interpretables | 37.376 | 37.248 |
| Pares exactamente cero (fase no medible) | 5.856 | 5.820 |
| Pares cuya fase cambiaría al permutar ejes | 31.049 | 31.051 |
| RSSI dBm | -68..-52 | -52..-48 |
| IDs callback | 0..291 | 0..290 |
| Intervalos del reloj local, µs | 195.905..399.992 | 195.906..400.417 |
| Timestamps host únicos / grupos compartidos | 292 / 0 | 291 / 0 |
| Líneas CSI malformadas | 1 inicial | 0 |
| Calidad estricta del capturador | Rechazada | Aceptada |

Todos los registros aceptados tienen MAC `1a:00:00:00:00:00`, canal 11, smoothing=1, not_sounding=1, aggregation=0, SGI=0, FEC=0, sig_len=47 y queue_drops=0. Rate=11 es metadato no válido como tasa PHY HT según IDF; no se traduce a Mbps. No hubo reinicios posteriores a la primera fila válida, saltos de callback ni IDs no crecientes en esta referencia. **Calidad global sigue false, capturador histórico y CLI de validación retornan 1.** Que las regresiones aprueben significa que detectan y conservan ese rechazo.

No se interpreta un cero como prueba de guarda/DC; no se etiqueta una banda por longitud. Las cuentas de fase son comprobaciones algebraicas offline sobre los pares, sin demostrar fase RF estable, ocupación, rendimiento de modelos o calibración absoluta. Los clocks RX no se alinean y los IDs no identifican paquetes TX. El capturador admite timestamps host compartidos por bloque; aunque no se observen repeticiones aquí, no se inventan instantes individuales. La prueba sintética de tres filas en un mismo read confirma esa semántica.

## Otros históricos: nunca concatenados

Se revisaron también en solo lectura los dos brutos de `/home/alan-monar/prueba_uart_20261024_155353/` y el RX-02 experimental incompleto preservado por la consolidación. Se comprobaron los SHA-256 previamente fijados. Sus rutas, hashes e histogramas quedan en el JSON; no se copiaron ni publicaron nuevos brutos.

| Material | Conteo revisado | Clasificación y límite |
|---|---:|---|
| Log 15 s RX-01 | 74 filas completas; cola 128 bytes | Referencia UART histórica fragmentaria, sin timestamps host por fila; no son 75 matrices completas |
| Log 15 s RX-02 | 74 filas completas; cola 128 bytes | Igual límite; no se rellenan los fragmentos inicial/final |
| RX-02 recuperado experimental | 596 filas completas | Integridad confirmada; cadena UART/host incompleta, no se promueve a campaña física completa |
| Reproducción en memoria histórica | 296 filas declaradas en auditoría previa | Excluida de los resultados físicos y de esta comparación matricial; no se ejecutó |
| Fragmentos 589 / manifiestos incompletos | Auditoría previa consultada | Procedencia insuficiente; no se unen ni cuentan como campañas nuevas |

Las filas completas de los tres brutos nuevamente analizados muestran len=256, HT20, sin secundario ni STBC, first_word_invalid=0, MCS=0, ant=0 y canal/MAC esperados. Eso corrobora la consistencia del perfil; no mejora automáticamente su procedencia experimental. Las 596 filas no se suman a las 583 duales para presentar una sesión mayor.

## Pruebas ejecutadas y limitaciones de ejecución

`./tools/test_base.sh`: **60 pruebas, 0 fallos, 0 errores, 0 omitidas, 3,535 s**. Son las 40 de la base más 19 contratos nuevos y una regresión adicional sobre las matrices históricas. Desglose final: 57 pruebas sintéticas y 3 regresiones offline sobre referencia física. No se ejecutaron las 304 históricas ni pruebas completas de RuView.

Los contratos comprueban orden complejo, signo int8 y extremos, fase en cuatro cuadrantes, permuta/conjugación invisibles a amplitud, máscara de primeros cuatro bytes sin desplazamiento, fase desconocida en ceros, separación condicionada LTF, DC/guardas/pilotos, rejilla FFT, geometría distinta de antenas, timestamps compartidos y precisión entera. Se ejecutan las dos funciones puras reales revisadas de `record-csi-udp.py` para verificar payload hex, amplitudes con signo, cabecera, identidad, frecuencia y rechazo de paquetes sintéticos truncados. Se adjunta licencia MIT a ese extracto; no se importó ni ejecutó su CLI con sockets.

**No hubo ejecución nativa JavaScript/Rust:** Node/nodejs/rustc no están disponibles en PATH y no se instalaron. Sus fórmulas y rutas se inspeccionaron estáticamente; las pruebas de fase son contratos matemáticos independientes, no certificación de aquellos runtimes. No se ejecutó el parser archivado dependiente de NumPy ni el conversor RVCSI. No se instalaron dependencias RuView. Los tres builds de firmware del hito anterior siguen siendo evidencia anterior; no se recompiló firmware que no cambió.

La ejecución de pruebas y el análisis matricial usaron Bubblewrap con red separada, repositorio/orígenes de solo lectura y /dev privado. Solo PTY sintéticos; ninguna UART física ni socket UDP. Logs íntegros ignorados en `results/local/`; hash de pruebas y del informe JSON en [pruebas_compatibilidad_csi_ruview.json](pruebas_compatibilidad_csi_ruview.json).

## Reproducción

En el entorno aislado del primer hito (pyserial 3.5, ninguna dependencia nueva): `./tools/test_base.sh`. Sin la copia física local se omiten explícitamente las tres regresiones, no se descargan ni fabrican datos. Las 19 pruebas nuevas no requieren el checkout externo porque el extracto puro auditado va acompañado de su licencia; el resto del checkout solo sirve de referencia de lectura.

El analizador se ejecuta como `.venv/bin/python -B tools/audit_csi_ruview.py`, emite JSON sin escribir dentro de las capturas ni abrir puertos. Para repetir el alcance ampliado, añadir `--historical-uart /home/alan-monar/prueba_uart_20261024_155353 --incomplete-log /home/alan-monar/tesis-restaurada-20261024T043056Z/consolidacion-tecnica-20261024/evidencia/experimental_incompleta/presencia-val-inicial-ocupado-20261018T002323-10944/rx-02.serial.log`. El resultado tiene `operation=offline` y `strict_historical_result.quality_ok=false`; la CLI de análisis retorna 0 al completar el análisis, a diferencia de la CLI de validación estricta que mantiene 1 para esta sesión. Los JSON fijados no se sobrescriben al repetir: guardar nuevas salidas en `results/local/`.

En esta ejecución ese comando se envolvió con bwrap: `--unshare-all --die-with-parent`, binds ro de /usr, /lib, /lib64, ld.so.cache y localtime, del repositorio y de las dos carpetas históricas, `--proc /proc --dev /dev --tmpfs /tmp`, HOME=/tmp y PYTHONDONTWRITEBYTECODE=1. No se montaron dispositivos de host.

## Decisión y siguiente paso

Queda respaldada la ruta **captura propia intacta → validación offline estricta → complejos canónicos con máscara y metadatos → selección explícita de contrato consumidor**. La entrega directa a ADR-018/RuView se bloquea hasta resolver fase por consumidor, bloques/índices/banda, preservación lateral de tiempos/identidades/calidad y configuración PHY. Falta evidencia del binario histórico y calibración por tono; no se promete reconstruir datos que nunca se exportaron. El siguiente hito razonable es acordar y probar ese contrato offline con un consumidor concreto antes de implementar transporte, instalar dependencias o solicitar una nueva prueba física.
