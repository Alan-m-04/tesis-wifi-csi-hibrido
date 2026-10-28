# Práctica de sonidos sin ESP

Mantén las ESP desconectadas y los equipos en sus posiciones actuales. Este programa solo usa audio de laptop: no descubre USB, abre UART/PTY ni ejecuta el detector. Los sonidos son EJEMPLOS; tres tonos largos aquí no confirman cierre de ningún dispositivo.

1. Desde la raíz del repositorio, elige un directorio nuevo y ejecuta:

   ```sh
   .venv/bin/python -B tools/practicar_sonidos_v4.py \
     --output-new results/local/SONIDOS-FUERA-NUEVA \
     --play-after-delay 30
   ```

2. Tienes 30 s para salir. Deja la puerta en la posición prevista y escucha sin mover laptop/RX ni usar equipo adicional. El orden, con 5 s de separación, es: **dos cortos** (establecer condición), **uno corto** (ventana terminada/conexión abierta), **tres largos** (ejemplo de cierre confirmado), **ocho rápidos** (ejemplo de fallo).
3. Después de los ocho tonos vuelve a la laptop. Responde **sí**, **no** o **incierto** a si distinguiste los cuatro desde fuera. Esa respuesta queda en `practice.json` como declaración humana; la verificación automática de audibilidad permanece `false`.

Si no se oye o confundes patrones, responde no/incierto y deja pendiente la operación audible. Si `aplay` falla o no existe, el programa conserva el error y no deduce que oíste nada; no instala software. No interpretes silencio o tiempo transcurrido como cierre. Para revisar únicamente los WAV sin reproducirlos, omite `--play-after-delay` y usa otro directorio nuevo.

Esta entrega solo exportó y probó el reproductor con dobles; no se reprodujo audio real ni se confirmó tu audibilidad. La práctica no autoriza la futura adquisición UART.
