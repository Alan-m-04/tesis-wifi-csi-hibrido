# Verificación offline y preparación Edge AI — 14 de noviembre de 2026

Se trabajó sobre `feat/demo-offline-operacion-20261109`, desde `c518d07`,
conservando sus cambios previos. Sin UART, preflight físico, ESP conectadas por
este trabajo, adquisición, flasheo, dependencias nuevas o acceso a la reserva.
El estado de desconexión fue una condición de trabajo indicada por el usuario;
no se consultaron dispositivos para acreditarlo físicamente.

## Tablero SQLite

Se intentó el comando real `.venv/bin/python -B tools/panel_dispositivos.py
--sin-replay`. El entorno rechazó el socket localhost con `[Errno 1] Operation
not permitted`; el servidor no llegó a escuchar. No se intentó eludir esa
restricción. El servidor y las rutas existentes se conservaron.

`tools/verificar_tablero_sqlite.py` invoca el handler HTTP real sobre streams
en memoria, sin sockets, usando el SQLite y CSV existentes. `/sessions`,
`/sessions.mjs`, `/panel.css` y `/api/sessions` devolvieron 200; las tres consultas
API contrastaron los indicadores y la calidad con el CSV. No se consultó USB.
`tools/base_datos_csi.py verify` revalidó las fuentes y registros en solo lectura,
con resultado `verified`, SQLite íntegro y cero errores de claves foráneas.

| Indicador | SQLite / CSV |
| --- | ---: |
| Sesión / receptor | RX02-DIAG-VISOR-240S-R1 / RX-02 |
| Muestras | 1.192 |
| Apertura → cierre | 240,005564743 s |
| Primera → última fila | 239,191988869 s |
| Cadencia `(1192−1)/239,191988869` | 4,9792637522332885 Hz |
| Hueco máximo host | 614,782902 ms |
| Calidad estricta | **Rechazada por preámbulo** |

Los motivos siguen siendo `format:RX-02` ×20 y `preamble_anomaly:RX-02` ×1.
Integridad, replay, cierre y diagnóstico conformes permanecen separados del
rechazo. Las 1.192 filas son las guardadas originalmente; no se rellenó el hueco.

SQLite mantuvo tamaño **5.115.904 bytes**, mtime y SHA-256 antes/después:

```text
86d37e68ea63f2a3f97dc00626533ca646488416d2d1dd63960efd1769f8199c
```

El CSV mantuvo sus 999 bytes, mtime y SHA-256:

```text
9a72a84ef5c7171aadbc9a8a9a31f81b4ffc7d870fbd46ce89d91153f427ff3c
```

Tampoco apareció o desapareció un archivo vecino de SQLite. No se importó,
creó o actualizó la base. [Evidencia JSON](VERIFICACION_TABLERO_20261114.json).

## Presentación: qué pudo comprobarse

Los tres contratos Node comprueban el comportamiento del DOM simulado y sus
errores/estados. Una QA adicional ejecutó `sqlite_sessions.mjs` con la respuesta
**real** de SQLite obtenida por HTTP en memoria: se comprobaron los valores
completos, la coma decimal, el aviso `RECHAZADA · PREÁMBULO`, los motivos ×20/×1,
las otras validaciones separadas y el contraste CSV. El entero se presenta como
`1192`; no se añadió separador de miles. No se alteró la interfaz existente.

Se intentó abrir Firefox headless con perfil aparte y el HTML local, pero
terminó con código −11 tras `CanCreateUserNamespace() ... EPERM`, sin captura.
Ni ese intento ni los contratos DOM acreditan renderizado, tipografía,
contraste visual, diseño adaptable, navegación o interacción humana reales.
La consulta conectada en navegador queda pendiente en la terminal del operador:

```bash
.venv/bin/python -B tools/panel_dispositivos.py --sin-replay
# http://127.0.0.1:8766/sessions
```

## Evaluación sintética Edge AI

El [flujo documentado](../docs/EVALUACION_EDGE_AI_OFFLINE.md) reutiliza parser,
referencias, decodificador, extracción LLTF52 y el port existente de RuView
`fefb0f918eefa7db6daef8cc83787fc7d6f74187` (MIT). El nuevo CLI no adquiere datos.
Se verificó el recorrido completo con cinco conexiones inventadas: dos de
entrenamiento, tres de evaluación, cada una con E y S originales juntas.

Se generó una salida nueva y se reevaluó su manifiesto, conservando las revisiones
anteriores. La ejecución final es `results/local/edge-ai-synthetic-20261114-r3/`;
se versionan [reporte](EDGE_AI_SINTETICO_20261114.md) y
[JSON](EDGE_AI_SINTETICO_20261114.json). Incluye hashes, características,
particiones, parámetros, decisiones y métricas por sesión.

| Verdad / predicción sintética | Vacío | Ocupado | Abstención |
| --- | ---: | ---: | ---: |
| Vacío | 1 | 1 | 1 |
| Ocupado | 1 | 1 | 1 |

Una falsa alarma, un falso negativo y dos abstenciones fueron construidos
deliberadamente. Cobertura: 4/6; exactitud entre decisiones: 2/4; aciertos sobre
todas las ventanas: 2/6. Falsas alarmas: 1/2 de vacíos decididos y 1/3 de todos
los vacíos. **Son pruebas sintéticas de software, no mediciones de precisión.**

Los contratos físicos vigentes no permiten entrenamiento. La ruta física del
CLI bloquea planes sin permisos prospectivos, ámbito o partición admisible;
su aceptación real requiere revisar y probar un contrato/adaptador futuro.
El comando para capturas válidas queda documentado con ese límite, sin cambiar
planes históricos, aprobar rechazos o entrenar con C01/C03/piloto.

## Pruebas y conservación

Resultado final: **102 pruebas Python** relacionadas (60 de tablero/SQLite/replay
y 42 de presencia/evaluación, incluidas once nuevas) y **tres contratos Node**
aprobados, cero fallos, errores u omisiones. QA adicional del DOM con el JSON real
aprobada. No se ejecutó la suite completa o la equivalencia Rust completa.
Comandos reproducibles en el [checklist](../docs/CHECKLIST_TECNICO.md).

Los primeros ensayos detectaron y corrigieron la serialización del modelo sin
separabilidad y dos problemas del arnés nuevo de pruebas. Una corrida conjunta
posterior falló por falta de `PYTHONPATH` heredable y por un nombre temporal
aleatorio que coincidió con la barrera conservadora `C06`. Los logs de esos
intentos se conservan; la corrida final con `PYTHONPATH` exportado terminó sin
intentos de acceso bloqueados ni fallos. No se cambió el guard o el capturador.

Bubblewrap rechazó crear namespaces. Se ejecutó directamente bajo las
restricciones del entorno con una barrera Python para aperturas UART/reserva;
no se afirma aislamiento Bubblewrap. Logs, inventario y ensayo de navegador:
`results/local/avance-offline-20261114-r1/`.

La [comparación SHA-256](PRESERVACION_OFFLINE_20261114.json) conserva **69 archivos
con cambios previos y 4.126 archivos locales originales accesibles**, de
927.079.174 bytes, sin cambios. C04–C06 se excluyeron de inventarios de contenido
y no se abrieron. Se conservaron los rechazos y las autorizaciones anteriores.
No se comprobó su contenido reservado para afirmar su conservación.

Pendientes: revisión visual conectada de `/sessions`, ensayo humano R5-N01 sin
ESP, contrato prospectivo de uso real, capturas válidas etiquetadas independientes,
calibración/evaluación física y validación en una MIPYME. Ninguno se marcó como
completado por las pruebas sintéticas.
