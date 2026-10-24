# Tesis: sistema híbrido WiFi CSI con ESP32-S3 y RuView

Repositorio nuevo para desarrollar y documentar el sistema de sensado CSI y Edge AI aplicado a MIPYMES de Riobamba. El procesamiento se realizará en una PC local.

## Punto de partida

Esta base organiza el proyecto desde cero. Todavía no contiene firmware, capturador ni adaptador funcional. El firmware y las capturas existentes se incorporarán desde copias verificadas; no se eliminarán ni se sobrescribirán sus originales.

La integración mínima buscará recibir CSI de TX-01, RX-01 y RX-02 con el firmware propio, conservar los registros y reutilizar componentes verificables de RuView. La detección de presencia será el primer hito; no sustituye los objetivos del anteproyecto aprobado, que deben mantenerse.

## Estructura

| Carpeta | Contenido previsto |
|---|---|
| firmware/ | Fuentes propias de TX-01, RX-01 y RX-02 |
| src/ | Capturador, validación, adaptador y procesamiento en PC |
| tests/ | Pruebas automatizadas y fixtures identificados |
| config/ | Plantillas de configuración sin credenciales |
| docs/ | Arquitectura, decisiones, procedimientos y validación |
| data/ | Manifiestos y documentación de conjuntos de datos |
| results/ | Informes, métricas y evidencias revisadas |

## Orden de desarrollo

1. Crear y conectar este repositorio en GitHub.
2. Incorporar y revisar las fuentes existentes, su configuración y pruebas.
3. Reproducir offline una captura real y conservar el resultado estricto.
4. Fijar una revisión de RuView y aprobar la correspondencia CSI antes de convertir.
5. Probar el adaptador con ambos receptores y visualización local.
6. Solicitar autorización antes de abrir UART para una captura física integrada.
7. Realizar campañas etiquetadas y después comparar modelos de presencia.

## Reglas de evidencia

- Diferenciar lo declarado por el usuario, lo inspeccionado en código, lo medido en software y lo medido físicamente.
- Identificar explícitamente cualquier dato sintético.
- No presentar pruebas sintéticas como validación física.
- No cambiar criterios de calidad para aprobar capturas.
- No rellenar matrices incompletas ni aumentar artificialmente la frecuencia.
- Conservar ESP-IDF v5.4 y el firmware propio hasta que exista una decisión documentada.

Consultar [ESTADO_INICIAL.md](docs/ESTADO_INICIAL.md) y [FLUJO_GIT.md](docs/FLUJO_GIT.md).
