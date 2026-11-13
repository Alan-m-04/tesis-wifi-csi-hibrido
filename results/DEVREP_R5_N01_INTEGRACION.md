# Integración RX02-DEVREP-R5-N01 — validación offline

La entrada R5-N01 queda integrada con `devrep_operator_interface.operate` y
`devrep_operation_view`, sobre el coordinador DEVREP, el ciclo de servicio y
cierre C03 y `CheckpointJournal` existentes. No se inició una adquisición ni
se ejecutó un preflight físico. Plan, ejecutor y autorización permanecen en
estado de revisión, con condiciones actuales pendientes.

Se revisó la rama `feat/demo-offline-operacion-20261109`, HEAD `6f5ae46`.
El árbol ya contenía cambios README/estado y archivos R1/R2/R5 sin registrar;
se conservaron. La propuesta R5 y los intentos anteriores mantienen sus
identidades, salidas, autorizaciones consumidas y rechazos originales.

El plan integrado coincide con `config/devrep_r5_N01.propuesta.review.json`.
La revisión de la entrada comprueba esa igualdad antes de proyectar los avisos.
La salida exclusiva continúa siendo `results/local/devrep-rx02-r5-N01`, sin
crear; partición `development_future`, calibración/entrenamiento/producción
en `false`, un solo intento y cero reintentos.

| Momento relativo a disponibilidad inicial A | Acción / límite conservado |
| --- | --- |
| A+30 s | Solicitud E: **SAL DEL CUARTO AHORA Y CIERRA LA PUERTA**. |
| Antes del tono final E confirmado | **PERMANECE FUERA**; no se invita a regresar. |
| Después del tono final E confirmado | **REGRESA Y ESCRIBE LA DECLARACIÓN**, con `declare RX02-DEVREP-R5-N01-E yes` o `uncertain MOTIVO`. Plazo A+210 s. |
| Tras E y solicitud S en A+240 s | **SIÉNTATE Y PERMANECE QUIETO**. |
| Cierre comprobado y resultado sonoro final satisfactorio | **ESCRIBE LA DECLARACIÓN Y PULSA ENTER**, con `declare RX02-DEVREP-R5-N01-S yes` o `uncertain MOTIVO`. Plazo A+420 s. |

Ventanas de 30 s, bandas T0 E A+90–120 s y S A+300–330 s, tolerancia de
solicitud 2 s, límite de solicitud de cierre A+390 s y cierre temprano ante
fallo permanecen iguales. El contador del prompt usa el plazo absoluto; no
lo reinicia al mostrarlo. READY, cobertura, watchdog y calidad no cambian.

Pasaron **229 pruebas, sin fallos, errores ni omisiones**, de los 20 módulos
enumerados en el [resultado estructurado](DEVREP_R5_N01_INTEGRACION.validacion.json).
Incluyen 42 pruebas R5 y regresión R1–R4, teclado, práctica, sonidos,
checkpoints y cierre. Son pruebas de memoria/PTY y lectura de evidencia
histórica; sus resultados no son mediciones nuevas ni validación física.

Los nuevos casos PTY demoran los resultados sonoros de E y del cierre final:
se conserva el aviso de permanecer fuera hasta confirmar el tono final E;
el prompt S exige lectura detenida, recibo persistido, descriptor liberado y
resultado sonoro final satisfactorio. Si ese audio falla, S queda pendiente
y el intento se detiene. Una declaración E incierta conserva su motivo y
detiene antes de S. READY ausente o Enter omitido tampoco producen reapertura.

En la primera regresión ampliada aparecieron tres errores R2 por usar recibos
físicos de un boot anterior y un fallo R3 por suponer inexistente una salida
histórica. Se corrigieron solo los fixtures: R2 usa declaración, recibo y boot
sintéticos temporales; R2/R3 verifican que la existencia previa de la salida
no cambie. Se mantienen los validadores y recibos originales.

`./tools/test_base.sh` falló antes de ejecutar pruebas porque Bubblewrap no
pudo crear namespaces. La regresión se ejecutó directamente en el entorno
restringido con `csi_live_observer.guard` instalado como barrera de auditoría
Python para UART y reserva. No se atribuye aislamiento Bubblewrap a ese ensayo.
Las CLI de revisión no reprodujeron audio ni consultaron dispositivos. La
audibilidad y las condiciones humanas no fueron confirmadas.

Se comprobaron por SHA-256 **4.261 archivos anteriores sin cambios**, excluyendo
las rutas reservadas C04–C06 antes de leer contenidos. La evidencia nueva está
en `results/local/integracion-devrep-r5-N01/`, separada de la preparación previa.
Se conservan ambos resultados de regresión, las proyecciones y los hashes.

Para reproducir la revisión y las 42 pruebas específicas:

```bash
cd /home/alan-monar/tesis-wifi-csi-hibrido
.venv/bin/python -B tools/revisar_devrep_r5_n01.py --check-guidance
.venv/bin/python -B tools/ejecutar_devrep_r5_n01.py --check-guidance
PYTHONPATH=src:tools:tests .venv/bin/python -B -m unittest test_execute_devrep_r5_n01 test_preflight_devrep_r5 test_r5_integration test_revisar_devrep_r5_n01 -v
```

El siguiente paso es la práctica interactiva, con las ESP desconectadas:

```bash
cd /home/alan-monar/tesis-wifi-csi-hibrido
.venv/bin/python -B tools/practica_devrep_r5_n01.py --rapida
```

La práctica usa IDs `PRACTICA-GUIADA-*`, sonidos reales y reloj simulado ×10.
Su confirmación humana se registra aparte y no autoriza captura. Después
seguirán la revisión de condiciones actuales, preflight por metadatos y
autorización nueva antes de un eventual intento único R5-N01.
