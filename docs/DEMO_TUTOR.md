# Demostración local para el tutor — unos cuatro minutos

Desde `/home/alan-monar/tesis-wifi-csi-hibrido`:

```bash
.venv/bin/python -B tools/panel_dispositivos.py
```

Esperar a que imprima las direcciones y abrir **http://127.0.0.1:8766/**. Dejar la
terminal abierta; Ctrl-C la cierra. El mismo servidor localhost ofrece el panel y
**http://127.0.0.1:8766/replay**, con enlaces de ida y vuelta. `--port 8767` cambia
ambas direcciones conjuntamente. No hay botones de captura, calibración o reset.
El inicio genera o verifica el artefacto histórico antes de servirlo; no abre UART.

La reproducción también puede abrirse sin servidor:

```bash
.venv/bin/python -B tools/demo_offline.py
xdg-open results/local/demo-offline-c01-c03-shared-live-r1/index.html
```

En ese caso, el enlace al panel requiere que el servidor esté iniciado en el
puerto 8766. Las versiones anteriores se conservan. No se necesitan instalaciones,
Internet ni publicación en la red.

## Guion

| Tiempo | Acción y explicación |
|---|---|
| 0:00–0:40 | En **Dispositivos · metadatos actuales**, mostrar serie USB, by-id, nodo, permisos y hora UTC. «Esto es una consulta del sistema operativo, no una captura. Detectar USB no demuestra READY ni CSI». Pulsar Consultar para mostrar una instantánea nueva. Si el entorno dice no verificable, explicar esa limitación; no sustituirla por una detección anterior. |
| 0:40–1:30 | Ir a **C01/C03 · datos históricos**. Señalar **REPRODUCCIÓN OFFLINE** y **SIN DETECTOR CALIBRADO**. Elegir C01, E y comparación. «Estas son mediciones guardadas de RX-02 y condiciones declaradas por el operador. Las conexiones completas siguen rechazadas; sus ventanas son elegibles solo para exploración». |
| 1:30–2:30 | Reproducir, pausar, reiniciar, cambiar velocidad y mover el cursor. Mostrar E/S y C01/C03. «El mapa de calor es amplitud CSI por tiempo y subportadora: no es un plano ni ubicación humana. RSSI es el campo original; σ es la desviación poblacional acumulada de medias LLTF52 por fila». Cambiar velocidad no añade mediciones. |
| 2:30–3:10 | Abrir los detalles y consultar una muestra con el puntero. Mostrar timestamps, callback, línea bruta, cobertura/huecos y procedencia. «Conservamos máscaras y tiempos, sin rellenar huecos; las sesiones no se concatenan. Diferencias entre gráficas no demuestran por sí solas presencia ni su causa». |
| 3:10–4:00 | Volver al panel para hacer explícita la separación. «Funciona la identificación por metadatos, la reproducción real y el recorrido de software hasta PresenceSpecialist con pruebas sintéticas. Todavía no hay detector físico calibrado ni localizador». Explicar los pendientes siguientes. |

## Evidencia que sí mostramos

- Mediciones físicas históricas C01/C03: E/S de 148/150 y 143/146 filas,
  respectivamente, con referencias y manifiestos verificables. No se alteraron
  los rechazos de conexión ni las etiquetas.
- El operador informó que el panel abre en Ubuntu y muestra RX-02 detectado,
  RX-01 ausente y TX no verificable por USB. Es una comprobación declarada del
  panel en ese momento, sin verificación de READY o recepción CSI. La nueva
  consulta puede diferir y siempre conserva su propia hora.
- Pruebas automáticas de controles, navegación HTTP en memoria y recorrido
  sintético I/Q → LLTF52 → PresenceSpecialist. No son medidas de exactitud física.

## Qué falta

**Presencia:** conexiones completas aceptadas y autorizadas, E/S prospectivas y
suficiente desarrollo independiente; política de anclas y ámbito de receptor/
geometría fijados (la cabeza original usa el primer `Empty`); calibración solo
en desarrollo y evaluación por conexiones/grupos correlacionados separados,
con método, métricas, cobertura y abstenciones definidos previamente. C04–C06
permanecen reservadas, sin consultarlas para elegir métodos. No hay modelo
físico calibrado, precisión estimada o inferencia física en esta demostración.

**Localización:** después de validar presencia, falta elegir y justificar un
método compatible con estos enlaces, documentar geometría/receptores y obtener
verdad de referencia de posiciones o zonas, datos independientes y evaluación
espacial. Si el método requiere fase, sincronización, antenas o pesos, debe
verificarse esa compatibilidad; no se da por disponible. El mapa CSI actual no
permite afirmar coordenadas, número de personas o trayectorias.

**CSI en vivo:** existe una [demo sintética ejecutable](OBSERVADOR_CSI_SINTETICO.md)
con productor PTY y observador separado en solo lectura. Como complemento de
45 s al guion, ejecutar `tools/demo_csi_vivo.py --seconds 45` con `.venv/bin/python -B`
y abrir `http://127.0.0.1:8767/`. Mostrar esperando, recibiendo, datos antiguos
durante la pausa y recuperación; pausar/reanudar solo la vista. Explicar que son
datos inventados sin ESP y que la fuente física sigue deshabilitada. No es
streaming físico verificado ni incorpora un detector.

La integración nueva se verificó con DOM/canvas simulado y HTTP en memoria.
El navegador completo, controles nativos y legibilidad en distintas pantallas
quedan para revisión humana. La confirmación previa del panel no se extiende
automáticamente a esta navegación ni a todos los controles de reproducción.
