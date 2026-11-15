# Reproducción offline C01 / C03

Desde la raíz del repositorio:

```bash
.venv/bin/python -B tools/demo_offline.py
xdg-open results/local/demo-offline-c01-c03-shared-live-r1/index.html
```

El primer comando genera el HTML autónomo o verifica los hashes del artefacto
existente, sus fuentes y los originales. El segundo lo abre en el navegador.
También puede abrirse `index.html` desde el explorador de archivos. No necesita
instalaciones, Internet ni servidor. Los datos permanecen en `results/local/`,
fuera de Git. Si cambian las fuentes, el generador exige una salida nueva mediante
`--output-new results/local/NOMBRE-NUEVO`; nunca sobrescribe evidencia.

La vista comienza pausada al final de los 30 s para mostrar la ventana completa.
**Reproducir** vuelve al inicio; **Pausar**, **Reiniciar**, el deslizador y la
velocidad permiten recorrerla. Se elige C01 o C03 y E o S. La comparación muestra
la misma condición en dos paneles separados, con escalas comunes y fijas.

Si se prefiere HTTP, `tools/demo_offline.py --serve` usa exclusivamente
`127.0.0.1:8765` y sirve solo el directorio generado. Ctrl-C lo detiene. No hace
falta para abrir el HTML. Esta sesión no inició ningún servidor.

## Datos y definiciones

| Serie | Definición |
|---|---|
| Amplitud LLTF52 | `hypot(Re, Im)` de I/Q int8 originales, sin calibración de amplitud; tonos −26…−1 y +1…+26. |
| RSSI | Campo original por fila, en dBm. |
| Media por fila | Media de los 52 tonos activos, todos utilizables según las máscaras originales. |
| Variabilidad temporal | Desviación estándar **poblacional acumulada** de las medias por fila observadas desde T0 hasta el cursor. Con menos de dos filas no se dibuja; no es un detector de movimiento. |
| Características de ventana | Media y varianza poblacional de las medias por fila de toda la ventana original; visibles en los detalles. |

Cada marca ocupa un instante observado. El espacio entre marcas se conserva;
no hay interpolación, unión de puntos, remuestreo ni relleno. El mapa de calor
representa CSI, no ubicación humana. La posición vertical es una subportadora.
El gris identifica una máscara no utilizable, nunca un valor cero inventado.

Los tiempos relativos se calculan con enteros `BigInt` desde los nanosegundos host
originales; no se interpretan como un reloj RF. Se conservan inicio de lectura,
retorno, timestamp local, callback, línea, offsets y hash de referencia, máscaras
completas y procedencia. Cada conexión mantiene su propio T0 y partición.

## Calidad y alcance

| Conexión | E | S | Conexión completa |
|---|---:|---:|---|
| C01 | 148 filas | 150 filas | Rechazada |
| C03 | 143 filas | 146 filas | Rechazada |

Las cuatro ventanas son elegibles **exploratorias**, según los auditores
existentes; esto no elimina el rechazo de sus conexiones ni concede calibración,
entrenamiento o evaluación. La interfaz muestra ambos estados por separado,
etiqueta humana, cobertura, bins de 5 s y hueco máximo con bordes incluidos.
`manifest.json` registra hashes de datos y fuentes; `data.json` conserva las
referencias y definiciones. C02 no se incorpora y C04–C06 no se abren.

La vista lleva permanentemente **REPRODUCCIÓN OFFLINE** y **SIN DETECTOR
CALIBRADO**. No calcula presencia, confianza, personas ni coordenadas.

## Verificación de esta sesión

Se comprobaron automáticamente los recuentos, límites temporales, máscaras,
características, controles de reproducción y escalas comunes. El arnés Node usa
un DOM/canvas simulado; no sustituye una revisión visual del navegador.
Firefox no pudo arrancar por `EPERM` al crear su espacio de nombres, y el control
por socket local también fue rechazado por el entorno. No se deshabilitó su
sandbox.

El operador confirmó después que la demostración abre y muestra los mapas,
RSSI y variabilidad. Reportó superposición del encabezado al desplazar la página.
Se corrigió dejando el encabezado en el flujo normal, sin fijación al desplazar;
se conservaron los rótulos offline. La versión corregida está en
`demo-offline-c01-c03-scroll-r1/`; la anterior `demo-offline-c01-c03-final/`
permanece intacta. Los datos son idénticos byte a byte y el JavaScript de
reproducción no cambió; el HTML solo difiere en el CSS del encabezado. El arnés
Node de controles volvió a pasar en la salida nueva, con DOM/canvas simulado.
El operador confirmó visualmente después que, al desplazar, el encabezado ya no
cubre las gráficas y que se muestran los datos y los detalles de muestras.
La comprobación humana de **todos los controles** sigue pendiente; la confirmación
no se extiende a esos controles ni a tamaños de pantalla no declarados.

## Revisión offline de controles posterior

Se reprodujo en el arnés un defecto durante la reproducción: cada actualización
reconstruía los paneles y cerraba los detalles abiertos, además de borrar la
consulta de muestras. Ahora se conservan los paneles mientras no cambie la
sesión/condición/comparación; solo se actualizan las gráficas, el contador y la
muestra. Al retroceder antes de la primera fila, la consulta indica que no hay
filas observadas, sin conservar una muestra posterior al cursor.

La salida vigente es **demo-offline-c01-c03-controles-r1/**. Conserva exactamente
el CSS del encabezado que confirmó el operador y un `data.json` idéntico byte a
byte al de `scroll-r1`: mismos datos, escalas, máscaras, etiquetas y timestamps.
Las versiones anteriores permanecen intactas.

El arnés Node ampliado pasó reproducción/pausa/reinicio, las cuatro velocidades
(0,5/1/2/4×), cambio de velocidad en marcha, desplazamiento temporal y fin automático, pausa al ocultar la página,
las cuatro combinaciones C01/C03 × E/S, comparación, persistencia de detalles y
procedencia de la muestra limitada al cursor. Se ejecutó también la verificación
Python del artefacto original de cuatro ventanas. Esto sigue siendo una prueba
con DOM/canvas simulado, no confirmación humana de todos los controles ni una
prueba de distribución visual en un navegador real.

Evidencia: `results/local/revision-controles-presence-r1/controles-antes.log`
(fallo reproducido), `controles-final.log`, `artefacto-python.log` y
`preservacion.json`. No se repitió la suite completa del proyecto.

## Navegación y revisión de controles para el tutor

Inicio recomendado para ambas vistas:

```bash
.venv/bin/python -B tools/panel_dispositivos.py
```

Abrir `http://127.0.0.1:8766/` para **metadatos actuales** y seguir el enlace a
`/replay` para **datos históricos**. El generador y renderizador son los mismos;
el servidor verifica el HTML al iniciar y lo sirve sin consultas USB desde esa
vista. La reproducción tiene su propia política que impide conexiones de datos.
Los enlaces son relativos en la vista integrada, también con otro puerto local.
El HTML autónomo sigue funcionando; su enlace al panel usa el puerto 8766.

Se reprodujeron errores al pausar o cambiar velocidad entre fotogramas: se perdía
el intervalo desde el último frame o se aplicaba la velocidad nueva a todo él.
Ahora los eventos liquidan el tiempo transcurrido con la velocidad anterior.
Ir al final pausa inmediatamente y pausar al alcanzar el final no reinicia.
Esto solo corrige el reloj de reproducción; los timestamps experimentales y
plazos de adquisición no cambian.

La salida vigente es **demo-offline-c01-c03-tutor-r2/**. `tutor-r1/` es un
prototipo conservado; `controles-r1/` y anteriores permanecen intactos. Sus datos,
máscaras, etiquetas y escalas son idénticos byte a byte. Las pruebas ampliadas
cubren archivo autónomo, servidor integrado y servidor HTTP separado, incluidos
detalles, muestras, velocidades, pausa/fin y navegación. Son DOM/canvas simulado
y HTTP en memoria; la comprobación humana completa permanece pendiente.

El [guion para el tutor](DEMO_TUTOR.md) explica evidencia, límites y pendientes.
Logs actuales en `results/local/demo-tutor-navegacion-r1/`.

El observador sintético posterior comparte las funciones originales de heatmap
y RSSI mediante `csi_charts.mjs`. El artefacto histórico vigente pasa a
**demo-offline-c01-c03-shared-live-r1/**, sin cambiar datos, máscaras, timestamps,
etiquetas o escalas. Los contadores de dibujo de la regresión son idénticos a
`tutor-r2`. La [vista sintética](OBSERVADOR_CSI_SINTETICO.md) es otra aplicación,
rotulada sin ESP y sin fuente física habilitada; no transforma la reproducción
histórica en datos actuales.
