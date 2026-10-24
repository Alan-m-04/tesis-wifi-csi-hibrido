# Panel local de preparación de sesiones

## Qué resuelve esta primera versión

Una interfaz local reúne TX-01, RX-01 y RX-02 y permite preparar, validar, guardar y exportar borradores de perfiles de sesión. El servicio utiliza solo la biblioteca estándar de Python. No requiere Node, paquetes web, conexión a Internet ni cambios al entorno ESP-IDF.

Los equipos y valores iniciales se leen de `config/csi_esp32s3.json`. Los borradores se guardan en archivos nuevos con UUID, fecha y hash SHA-256 del perfil de origen bajo `results/local/control-panel/`, que ya está excluido de Git. Guardar otro borrador no reemplaza el anterior ni modifica el perfil fuente. Cada exportación lleva `DRAFT_NOT_APPLIED` y `hardware_modified=false`.

La consulta USB lee atributos de identidad en sysfs de Linux. No importa pyserial, no abre dispositivos tty y no cambia DTR/RTS. Una identidad visible no demuestra flujo CSI, firmware instalado ni estado de recepción. Las coincidencias duplicadas se muestran como ambiguas. El transmisor alimentado externamente permanece sin verificar.

## Ejecutarlo en Ubuntu sin interrumpir el otro Codex

Usar otra terminal y un worktree separado. Los comandos siguientes no cambian la rama ni los archivos donde está trabajando la otra sesión:

```bash
cd ~/tesis-wifi-csi-hibrido
git fetch origin
git worktree add --detach ../tesis-panel-local origin/feat/panel-control-local
cd ~/tesis-panel-local
python3 apps/control_panel/server.py
```

Abrir `http://127.0.0.1:8090` en el navegador de esa misma PC. Ctrl+C detiene el servicio. El puerto se puede elegir con `--port`, por ejemplo `--port 8091` si ya se está utilizando. No existe opción para escuchar en interfaces públicas o de red local.

Si `../tesis-panel-local` ya existe, conservarlo y usar otra ruta nueva; no borrarlo ni sobrescribirlo para repetir los comandos. El worktree detached sirve para revisar esta versión, no para mezclarla automáticamente con el trabajo paralelo.

## Funciones disponibles

- Inventario USB por lectura, con nombre de rol, serie esperada y rutas observadas.
- Edición de nombre de sesión, canal propuesto, HT20, MAC TX, series RX, duración propuesta y notas.
- Validación de valores, identidades RX distintas y MAC unicast.
- Guardado de borradores nuevos y exportación JSON.
- API propia `GET /api/state`, `POST /api/drafts`, `GET /api/drafts/{uuid}/export`.

La duración es una propuesta: no arranca una captura. La vista de equipos usa el perfil fuente documentado; guardar un borrador no cambia la identidad esperada que muestra esa vista. No se introduce una medición, un puerto físico ni una sesión sintética como si estuvieran activos.

## Qué significa configurar las ESP32

Esta versión configura **borradores del experimento**, no las placas. El firmware actual no tiene demostrado un protocolo remoto de configuración que permita aplicar estos campos desde un navegador. Cambiar canal o MAC en la interfaz no altera el firmware ni la radio. Para aplicar esos cambios deberá elegirse y probarse un flujo explícito: configuración de compilación y flasheo autorizado, o un protocolo futuro compatible. No se debe inventar un comando UART que el firmware no implemente.

Las operaciones de captura, aplicación de ajustes, flasheo y presencia permanecen deshabilitadas y no tienen endpoints de ejecución. Tampoco hay endpoints para ejecutar comandos shell, abrir archivos arbitrarios o instalar software. La visualización CSI en desarrollo paralelo todavía no está conectada.

## Integraciones siguientes

1. Incorporar el visualizador offline como módulo independiente y mantener etiquetas de calidad/rechazo de sesión.
2. Añadir selección de conjuntos e informes ya verificados, sin cambiar el bruto.
3. Integrar el capturador existente mediante un gestor de trabajos con exclusión mutua por identidad USB, estados, parada ordenada y logs. Solicitar autorización antes de abrir UART.
4. Separar preparación, compilación, revisión y flasheo; una confirmación para guardar un perfil no autoriza flashear ni abrir un puerto.
5. Añadir inferencia solo después de validar los datos, los pesos, el contrato de entrada y las campañas etiquetadas.

No es necesario fusionar esta rama mientras Codex construye el visualizador. Revisar su PR por separado y comprobar ambas ramas antes de integrarlas.

## Pruebas

Desde la raíz del repositorio:

```bash
python3 -m unittest discover -s tests/control_panel -v
```

Son pruebas independientes del panel. Utilizan directorios temporales, servidor HTTP en loopback con puerto efímero e inventarios USB sintéticos. Ninguna prueba abre UART. El archivo de configuración fuente se compara byte por byte al terminar cada caso. Estas pruebas no reemplazan ni se suman automáticamente a las 60 del segundo hito sin ejecutar el conjunto integrado.

Resultado y límites: [PANEL_CONTROL_LOCAL.md](../results/PANEL_CONTROL_LOCAL.md).
