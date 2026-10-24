# Tesis: sistema híbrido WiFi CSI con ESP32-S3 y RuView

Base verificable del sistema de sensado CSI y Edge AI para MIPYMES de Riobamba, con procesamiento en PC local. Se conservan los objetivos del anteproyecto aprobado: presencia será el primer hito, no el alcance total.

## Estado comprobado el 24 de octubre de 2026

- Fuentes TX-01, RX-01 y RX-02 compiladas aquí con ESP-IDF v5.4 para ESP32-S3.
- Parser y capturador dual restaurados sin cambios; validación offline nueva y perfil explícito.
- Primer hito: 40 pruebas aprobadas. Segundo hito: 60 aprobadas (57 sintéticas y 3 regresiones offline históricas). No se ejecutaron las 304 pruebas del proyecto anterior.
- Referencia física histórica: 292/291 filas. Su rechazo estricto se conserva; aprobar la regresión no convierte la captura en una campaña válida.
- Sin nueva adquisición UART, flasheo, instalación de RuView ni entrenamiento.

## Reproducir

Crear `.venv` con Python compatible, instalar `requirements-dev.txt` exclusivamente allí y ejecutar `./tools/test_base.sh`. Requiere Bubblewrap (`bwrap`): el procedimiento bloquea red y dispositivos físicos, mantiene el repositorio de solo lectura y permite PTY sintéticos. Sin la copia física local se omiten explícitamente tres pruebas; los datos no se descargan automáticamente.

Con el entorno oficial ESP-IDF v5.4 ya activado, ejecutar `./tools/build_firmware.sh TX-01` y repetir para RX-01 y RX-02. El procedimiento solo compila; no flashea. Builds y entornos son locales e ignorados.

## Estructura y siguiente hito

`firmware/`: tres proyectos y atribuciones; `src/`: captura y validación; `tests/`: pruebas; `config/`: perfil; `data/`: manifiesto; `results/`: resultados; `docs/`: procedencia, formato y pendientes.

Antes de integrar RuView hay que verificar orden I/Q, empaquetado LTF y subportadoras, relojes y compatibilidad de modelos. No existe adaptador aprobado ni modelo entrenado en esta base. Las capturas brutas permanecen locales e intactas. Una nueva adquisición física requiere autorización explícita.

Consultar [inventario](docs/INVENTARIO_BASE.md), [estado](docs/ESTADO_INICIAL.md), [resultados](results/BASE_VERIFICADA.md) y [flujo Git](docs/FLUJO_GIT.md).

La [auditoría CSI/RuView](docs/COMPATIBILIDAD_CSI_RUVIEW.md) demuestra Im/Re y documenta incompatibilidades de fase, banda e índices. [Resultados del segundo hito](results/AUDITORIA_CSI_RUVIEW.md): queda respaldado el análisis offline; ADR-018 directo sigue bloqueado.
