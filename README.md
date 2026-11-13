# Tesis: análisis espacial mediante WiFi CSI y Edge AI

Sistema híbrido con ESP32-S3, firmware propio y componentes verificados de
RuView, con procesamiento en PC local, para MIPYMES de Riobamba. Presencia es
el primer hito; el alcance también contempla zonas, mapas de calor y validación
en una MIPYME.

## Avance verificable al 13/11/2026

El [informe de seguimiento del Anexo G](docs/AVANCE_ANEXO_G_2026-11-13.md)
relaciona los ocho hitos, sus fechas referenciales, evidencia y pendientes.
Último seguimiento indicado: **12/11/2026**; último plazo: **13/11/2026**.
Los porcentajes del Anexo G están **no verificados**: la copia privada disponible
tiene esas celdas vacías. No se calcula un porcentaje global a partir de pruebas
de software ni se atribuye aprobación académica sin respaldo.

| Evidencia disponible | Resultado y límite |
| --- | --- |
| [Firmware y captura dual de 60 s](docs/INVENTARIO_BASE.md) | TX-01, RX-01 y RX-02 compilados con ESP-IDF v5.4; referencia física de 292/291 filas. Se conserva el rechazo estricto de RX-01. Compilar no acredita el binario instalado. |
| [Captura dual v2, 25/10](results/CAPTURA_FISICA_V2_20261025.md) | 147/147 filas en 30 s, integridad conforme, ambos puertos cerrados y cero cola; sesión **rechazada por residuos iniciales**. |
| [C03 frente a C01](results/RX02_C03_C01.md) | Ventanas E/S exploratorias y comparación descriptiva de RSSI/LLTF52; conexión estricta rechazada. No demuestra clasificación de presencia. C02 conserva su rechazo. |
| [Visor RX-02 y diagnóstico físico histórico](results/RX02_DIAG_VISOR_240S_R1.md) | 1.192 muestras en aproximadamente 240 s; integridad, replay y cierre confirmados. Calidad **rechazada por preámbulo**. Diagnóstico ejecutado el 10/11, sin etiquetas E/S. |
| [Piloto SQLite y CSV agregado](results/BASE_DATOS_CSI_OFFLINE.md) | 1.192 muestras históricas indexadas, importación repetida sin duplicados y métricas contrastadas. SQLite y datos por muestra permanecen locales. |
| [Vista SQLite en el tablero](results/VISTA_SQLITE_OFFLINE.md) | `/sessions` de solo lectura; 60 pruebas Python y 3 contratos Node registrados. Revisión visual y HTTP real en navegador pendientes. |
| [Integración offline R5-N01](results/DEVREP_R5_N01_INTEGRACION.md) | Evidencia local de 229 pruebas, incluidas 42 específicas, contrastada por hashes. Parte de sus fuentes sigue sin confirmar en la copia original; el ensayo guiado humano continúa pendiente. |

Las [instantáneas publicadas y sus commits locales de origen](docs/AVANCE_ANEXO_G_2026-11-13.md#correspondencia-entre-origen-local-y-publicación) tienen árboles Git idénticos.

Las pruebas con memoria/PTY y DOM simulado verifican software. Los diagnósticos
físicos verifican el registro de intentos históricos. Ninguno sustituye una
evaluación experimental independiente de Edge AI con verdad terreno.

## Evidencia para el tutor

- [Capítulo III: esquema SQLite y análisis reproducible](docs/CAPITULO_3_BASE_DATOS_CSI.md).
- [CSV agregado del piloto, una fila por sesión/receptor](results/BASE_DATOS_CSI_PILOTO/RX02-DIAG-VISOR-240S-R1__RX-02.csv).
- [Guía de la vista SQLite y sus límites](docs/VISTA_SQLITE_OFFLINE.md).
- [Preparación de R5-N01](docs/GUIA_DEVREP_R5_N01.md) y [registro de integración offline](results/DEVREP_R5_N01_INTEGRACION.validacion.json).
- [Auditoría CSI/RuView](docs/COMPATIBILIDAD_CSI_RUVIEW.md), [adaptador offline de presencia](results/VALIDACION_ADAPTADOR_PRESENCIA.md) y [revisión de PresenceSpecialist](docs/REVISION_ADAPTADOR_PRESENCE_20261109.md).
- [Comprobaciones de esta publicación](results/VERIFICACION_AVANCE_ANEXO_G_2026-11-13.json).

Los informes históricos conservan los estados de preparación de cada etapa.
El informe del Anexo G establece el estado comprobado a este corte y distingue
las fechas de seguimiento de las fechas reales de implementación y adquisición.

## Lo que falta validar

Faltan el ensayo guiado y la comprobación humana de R5-N01; sesiones reales
elegibles y repetidas, etiquetas de ocupación y evaluación separada por sesión;
calibración y evaluación de Edge AI sin usar la reserva; geometría y verdad
terreno para distinguir zonas y generar mapas de calor; y despliegue y prueba
en una MIPYME. El tablero histórico no mide ocupación actual.

**C04–C06 permanecen cerradas y reservadas.** Esta actualización utiliza
evidencia existente: sin UART, capturas, firmware nuevo, calibración o
entrenamiento. Los documentos académicos privados, datos personales,
credenciales, SQLite local y datos brutos reservados quedan fuera de la
publicación. Los cambios sin confirmar de la copia original se conservan.

## Estructura técnica

`firmware/`: TX-01 y receptores; `src/`: captura, auditoría y análisis;
`tests/`: pruebas; `config/`: perfiles y esquema; `data/`: manifiestos;
`results/`: informes revisados; `docs/`: contratos, procedencia y seguimiento.

Consultar el [estado histórico](docs/ESTADO_INICIAL.md), los
[resultados de la base](results/BASE_VERIFICADA.md) y el
[flujo Git](docs/FLUJO_GIT.md). Los artefactos bajo `results/local/` y `data/raw/`
son referencias locales deliberadas, no descargas públicas.
