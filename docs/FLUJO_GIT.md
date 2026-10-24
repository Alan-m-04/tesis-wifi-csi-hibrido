# Flujo de trabajo en GitHub

Cada avance debe quedar registrado con una descripción concreta y evidencia de las comprobaciones realizadas. La rama principal será `main`.

## Primera incorporación

1. Conectar la cuenta de GitHub y elegir la visibilidad del repositorio.
2. Crear el repositorio remoto y asociar su URL como `origin`.
3. Configurar la identidad de autor real; no inventar nombre ni correo.
4. Revisar los archivos preparados, crear el primer commit y enviarlo.
5. Incorporar firmware, capturador y validación en cambios separados y revisables.

## Cambios posteriores

Trabajar en ramas breves, por ejemplo `feat/captura-dual` o `feat/adaptador-ruview`. Registrar en cada cambio qué funciona, qué se comprobó y qué permanece pendiente. No confundir un commit o un build con una validación física.

Mantener documentadas las revisiones de firmware, capturador, RuView y configuración utilizadas en cada experimento. Las copias brutas de capturas permanecen intactas; GitHub contendrá los manifiestos y los informes necesarios para localizar y comprobar cada conjunto. La publicación de conjuntos completos se decidirá según tamaño y contenido.
