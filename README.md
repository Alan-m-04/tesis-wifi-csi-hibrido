# Tesis: sistema híbrido WiFi CSI con ESP32-S3 y RuView

Base verificable del sistema de sensado CSI y Edge AI para MIPYMES de Riobamba, con procesamiento en PC local. Se conservan los objetivos del anteproyecto aprobado: presencia será el primer hito, no el alcance total.

## Estado actualizado el 25 de octubre de 2026

- Fuentes TX-01, RX-01 y RX-02 compiladas aquí con ESP-IDF v5.4 para ESP32-S3.
- Parser restaurado y capturador derivado con correcciones verificadas de entrada, encuadre y cierre; originales preservados.
- Primer hito: 40 pruebas aprobadas. Segundo hito: 60 aprobadas. Tercer hito: 103 aprobadas (72 Python y 31 Node), sin omisiones. No se ejecutaron las 304 pruebas del proyecto anterior.
- Referencia física histórica: 292/291 filas. Su rechazo estricto se conserva; aprobar la regresión no convierte la captura en una campaña válida.
- Un intento físico posterior al reinicio: 145/146 filas completas y sesión estrictamente rechazada; brutos y colas conservados. Sin flasheo, instalación de RuView ni entrenamiento.

## Reproducir

Crear `.venv` con Python compatible, instalar `requirements-dev.txt` exclusivamente allí y ejecutar `./tools/test_base.sh`. Requiere Bubblewrap (`bwrap`): el procedimiento bloquea red y dispositivos físicos, mantiene el repositorio de solo lectura y permite PTY sintéticos. Sin la copia física local se omiten explícitamente tres pruebas; los datos no se descargan automáticamente.

Con el entorno oficial ESP-IDF v5.4 ya activado, ejecutar `./tools/build_firmware.sh TX-01` y repetir para RX-01 y RX-02. El procedimiento solo compila; no flashea. Builds y entornos son locales e ignorados.

## Estructura y siguiente hito

`firmware/`: tres proyectos y atribuciones; `src/`: captura y validación; `tests/`: pruebas; `config/`: perfil; `data/`: manifiesto; `results/`: resultados; `docs/`: procedencia, formato y pendientes.

Antes de integrar RuView hay que verificar orden I/Q, empaquetado LTF y subportadoras, relojes y compatibilidad de modelos. Existe un puente diagnóstico offline al consumidor oficial de este tercer hito; no hay streaming integrado ni modelo entrenado validado. Las capturas brutas permanecen locales e intactas. Una nueva adquisición física requiere autorización explícita.

Consultar [inventario](docs/INVENTARIO_BASE.md), [estado](docs/ESTADO_INICIAL.md), [resultados](results/BASE_VERIFICADA.md) y [flujo Git](docs/FLUJO_GIT.md).

La [auditoría CSI/RuView](docs/COMPATIBILIDAD_CSI_RUVIEW.md) demuestra Im/Re y documenta incompatibilidades de fase, banda e índices. [Resultados del segundo hito](results/AUDITORIA_CSI_RUVIEW.md): queda respaldado el análisis offline; ADR-018 directo sigue bloqueado.

## Tercer hito: visualización offline

Se ejecutan `parsePacket` y `SpectrumCollector` oficiales de `harness/ruview/src/devices/esp32.js` (RuView fefb0f9) con Node v22.20.0 local fijado y sin UDP. La representación canónica conserva fuentes, hashes, máscaras, metadatos y relojes; la página muestra RX-01/RX-02 y LLTF/HT-LTF con **captura histórica con validación estricta rechazada**.

103 pruebas aprobadas: 72 Python y 31 Node, cero omisiones; cuatro vistas verificadas en Firefox. Ver [contrato/procedimiento](docs/CONTRATO_CONSUMIDOR_RUVIEW.md) y [validación](results/VALIDACION_VISUALIZACION_OFFLINE.md). El artefacto local generado es `results/local/visualizacion-csi-entrega/index.html`; no se publican sus datos brutos en Git.

## Cuarto hito: preparación de captura dual (estado previo)

Protocolo de 30 s preparado; **no se han abierto UART ni ejecutado la captura física**. Se corrigieron el flush implícito al abrir, el conteo de cola sin LF y el cierre durante startup interrumpido. Se registrarán ambiente, identidades, procedencia y ledgers sin borrar el arranque ni aprobar un recorte.

124 pruebas aprobadas (93 Python, 31 Node), sin omisiones. Ver [protocolo y comandos pendientes de autorización](docs/PROTOCOLO_CAPTURA_DUAL.md) e [informe de preparación](results/PREPARACION_CAPTURA_DUAL.md). El plan local exige completar la condición ambiental antes de abrir ambos receptores.

## Captura posterior al reinicio

Con autorización nueva y ambiente confirmado se ejecutó un único intento de 30 s comunes. Ambos puertos quedaron cerrados. Se conservaron 145/146 filas completas y todos los bytes leídos; la sesión fue **rechazada** por residuos iniciales pegados a ROM y colas incompletas de 129 bytes en ambos RX. No hubo recortes ni reintentos. La integridad permitió generar una visualización offline con rechazo visible, verificada en sus cuatro vistas. Ver [resultado real y límites](results/CAPTURA_DUAL_POST_REINICIO.md). Los datos permanecen locales; otra adquisición requiere nueva autorización.

El [diagnóstico offline posterior](docs/DIAGNOSTICO_LIMITES_CAPTURA.md) reproduce la parada a mitad de línea y propone una finalización hasta LF con espera acotada, ensayada en memoria/PTY y todavía sin integrar a v1. Pasaron 142 pruebas (111 Python, 31 Node), sin omisiones. La causa de los residuos iniciales sigue indeterminada; el intento físico conserva su rechazo. No se realizó otra captura ni se modificó firmware.

## controlled_dual_v2 preparado y probado sin hardware físico

v2 integra el lector acotado: mantiene los 30 s nominales y completa una línea pendiente hasta LF con máximo 250 ms desde el deadline y 65536 bytes adicionales. Conserva todos los fragmentos y registra motivos/tiempos por RX; las filas posteriores quedan fuera del conteo nominal. v1 y sus resultados siguen disponibles. Pasaron 155 pruebas (124 Python, 31 Node), un ensayo PTY de 30 s y ocho vistas de navegador. No se abrió UART físico ni se creó otra autorización. Ver [protocolo, límites y comando pendiente de revisión](docs/PROTOCOLO_CAPTURA_DUAL_V2.md) y [evidencia](results/CONTROLLED_DUAL_V2.validacion.json).
