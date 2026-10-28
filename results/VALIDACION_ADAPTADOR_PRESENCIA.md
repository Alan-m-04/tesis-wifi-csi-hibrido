# Adaptador offline de presencia: implementación y validación

Implementado en `feat/adaptador-presencia-offline`, basada exactamente en **`796d534a9d04bb040f9868f77030980529ec02e7`**. Se conserva RuView **`fefb0f918eefa7db6daef8cc83787fc7d6f74187`**, licencia MIT. El runtime del adaptador es Python/biblioteca estándar; reutiliza los auditores existentes para verificar las fuentes locales. No se modificó capturador, protocolo, firmware, captura o resultado histórico.

**Resultado sobre datos físicos: rasgos evaluables, “sin calibración”, sin decisión ni confianza de presencia en los cuatro pares sesión/RX.** Solo se probó calibración/inferencia con datos explícitamente sintéticos. No se entrenó, calibró, ajustó un umbral o clasificó presencia en las dos sesiones físicas.

## Implementación y límites del port

- [Extracción LLTF52](../src/presence_offline.py): filas incluidas en las ventanas v3 originales, por identidad USB y RX independiente. RX-01 es entrada primaria por contrato; RX-02 réplica separada, sin OR/AND/promedio/fusión.
- [Port Python explícito](../src/ruview_presence_port.py): únicamente `PresenceSpecialist::train/infer`. No es el crate Rust ni un modelo preentrenado. El margen de confianza no es probabilidad calibrada ni prueba de presencia.
- [CLI de extracción física](../tools/extraer_presencia_offline.py): no tiene opciones de modelos, anclas, calibración, inferencia o captura. Reconstruye y verifica las dos sesiones conocidas desde sus originales; no usa los números del chat como evidencia.
- [Extractos Rust y procedencia](../vendor/ruview/presence/PROVENANCE.json): constantes/struct/implementaciones de presencia y `AnchorLabel::expects_presence`, copiados sin modificar del commit fijado, con hashes y licencia [MIT raíz, copyright 2024 rUv](../vendor/ruview/presence/LICENSE). Se conserva separada e intacta la licencia del parser JS anterior (copyright 2026 ruvnet); no se reemplaza un aviso por otro. La selección anterior se mantiene en [DETECTOR_PRESENCIA_RUVIEW](../docs/DETECTOR_PRESENCIA_RUVIEW.md).

Se excluye HT-LTF del adaptador. Los datos HT, RSSI, MAC, IQ, fase y demás metadatos siguen en los originales; el artefacto escalar no permite reconstruirlos. La trazabilidad conserva identidad/sesión, índice CSV, callback, reloj local, primera/última lectura, offsets/hash de línea y referencias SHA-256 a archivos completos. No se presenta esa reducción como representación sin pérdida de CSI.

## Extracción, datos incompletos y resultados separados

Cada fila debe conservar el bloque LLTF de bytes [0,128), 64 pares int8, índices canónicos y roles. La selección fija es **52 tonos activos: datos y pilotos**, con máscara hardware y `cfr_usable` coherentes. No se incluyen DC/guardas ni se sustituye un tono inválido por otro. La amplitud se contrasta con `hypot(Re,Im)`; no se normaliza ganancia ni se convierte a una escala física calibrada. Un cero válido permanece cero; fase desconocida no se usa para completar datos.

Para cada fila incluida `i`, `x_i` es la media de amplitud de esos 52 tonos. Para el RX/sesión se calcula, en **binary64**, `mean = sum(x_i)/N` y `variance = sum((x_i-mean)^2)/N`, con igual peso por fila y varianza poblacional. No hay frecuencia supuesta, remuestreo, interpolación o relleno. No se generan valores de movimiento, bandas periódicas, respiración o corazón: los cinco campos del contenedor upstream que este head no lee solo se identifican como **no utilizados**, sin ceros publicados como mediciones.

Si falta un tono, máscara, IQ, amplitud o fila requerida, la entrada **completa de ese RX/sesión** queda **“no evaluable”**, `features=null`. La fila incompleta se conserva con `x=null` y motivo; las filas completas restantes no forman una ventana sustitutiva o una media parcial aprobada. Tampoco son evaluables identidad/layout incorrectos, referencias o timestamps contradictorios, cobertura incoherente, estados históricos ausentes, ventana no conforme o protocolo distinto de v3.

Se exige la inclusión original `primera_lectura>=T0` y `retorno_LF<T1`, una ventana de 30 s original y conteos/cobertura concordantes. Se conservan timestamps repetidos y sus huecos cero. No se retrocede T0, ordenan artificialmente tiempos o buscan subventanas. La comprobación de cobertura es de coherencia, **sin añadir umbral de silencio, tasa mínima o criterios del piloto**.

`connection_full`, `experimental_window` y global se copian de la evidencia auditada, separados de `feature_status` y `presence_status`. Extraer rasgos de una ventana conforme no revoca el rechazo de conexión/global.

## Calibración e inferencia: solo pruebas sintéticas

El port reproduce la política original: primera ancla `Empty`, media de estadísticas de todas las ocupadas; varianza activa solo si `var_O > var_E*(1+0.05)`; desplazamiento de media activo solo si la distancia supera `1e-4`; decisión por OR y comparaciones estrictas. Son las constantes originales, no números elegidos con datos físicos.

`calibrate_synthetic` exige evidencia sintética explícita, un RX y un alcance común. `infer_synthetic` rechaza usar esos modelos sobre evidencia física; RX/alcance/contrato distintos no producen decisión. No hay formato/CLI de banco físico aprobado en esta entrega. Las rutinas matemáticas de bajo nivel del port no acreditan por sí mismas calidad de anclas o validez de calibración.

| Situación | Estado de la envoltura | Presencia / confianza |
|---|---|---|
| Rasgos válidos, sin calibración o faltan Empty/ocupada | `sin calibración` | `null / null` |
| Ambos canales del head desactivados | `sin separabilidad` | `null / null` |
| Datos requeridos incompletos/no finitos | `no evaluable` | `null / null` |
| Calibración y consulta sintéticas compatibles | `resultado sintético` | Resultado de prueba, explícitamente sintético |

El Rust crudo puede devolver `absent` con confianza cero cuando ambos canales quedan inertes; la envoltura **se abstiene**. No se transforma falta de separabilidad o de calibración en ausencia. Las pruebas sintéticas no sustituyen anclas físicas elegibles, una sesión vacía o evaluación independiente. No se reutilizan las dos sesiones presentes como anclas ni se modifica la propuesta B01-E/B01-S.

## Equivalencia realmente ejecutada con Rust original

[Prueba reproducible y hashes](ADAPTADOR_PRESENCIA.equivalencia.json): **2022/2022 casos coincidentes**. En **513** se compararon bit a bit parámetros, valor/margen de confianza y etiqueta; en **1509** se verificó `None` por ausencia de las anclas requeridas, sin inferencia. Hay 22 casos nombrados y 2000 deterministas (semilla 1729), todos **sintéticos**, con anclas ausentes, primera Empty, varias ocupadas, etiquetas, varianza invertida, canales inertes, guardas/equivalencias exactas y vecinos binary32 de los límites, signos del desplazamiento y clamp de confianza.

**Sí se compiló y ejecutó Rust**, concretamente los cuerpos originales `train/infer` y `expects_presence` insertados en un arnés mínimo. Solo se retiraron derive/atributos de serialización y se proporcionaron tipos con los campos usados; el cálculo de esos cuerpos no se tradujo o reescribió para la referencia. **No** se compiló el workspace/Cargo completo, `Features::from_series`, enrolamiento, otros especialistas o firmware. El arnés no recibió ninguna característica física.

Rust 1.85.1/LLVM 19.1.7 se preparó localmente en `.tools` desde dos componentes binarios oficiales con SHA-256 [fijados](../config/presence_rust_reference.lock.json). Se usó el target musl y `rust-lld` incluido, sin compilador C, instalación global o ejecución de `install.sh`. Fuentes, binario, compilador, linker, entradas y salidas de la prueba tienen hashes; los binarios permanecen locales. Esto no actualiza RuView ni ESP-IDF v5.4.

El port redondea cada operación del head a **binary32**. La extracción de amplitudes/estadísticas es binary64 según el contrato local; convertir rasgos a binary32 ocurre solamente en las rutas sintéticas del head. No se afirma igualdad bit a bit con la extracción completa `Features::from_series`: esa función descarta no finitos, tiene fallback ZERO y calcula periodicidades con `fs`; tales comportamientos **no** se incorporan a este adaptador. La equivalencia ejecutada cubre los casos finitos no negativos probados, no todos los posibles valores IEEE, builds Rust o condiciones RF.

## Dos sesiones físicas: exclusivamente rasgos y trazabilidad

[Resumen físico reconstruible](ADAPTADOR_PRESENCIA_FISICAS.resumen.json), derivado de originales verificados de las sesiones [sentada](CAPTURA_FISICA_V3.md) y [movimiento libre](CAPTURA_MOVIMIENTO_LIBRE_V3.md). La procedencia, calidad y límites de montaje/adquisición permanecen en la [comparación anterior](COMPARACION_FISICA_V3.md), sin cambios de criterios.

| Sesión | RX / USB | Filas incluidas | Media de `x_i` | Varianza poblacional de `x_i` | Estado / decisión |
|---|---|---:|---:|---:|---|
| Sentada | RX-01 / 5C93199744 | 150 | 13.0180447757 | 0.3274368155 | sin calibración / null |
| Sentada | RX-02 / 5C93200689 | 150 | 12.7248720455 | 0.2489936701 | sin calibración / null |
| Libre | RX-01 / 5C93199744 | 149 | 12.9583039589 | 0.3159908979 | sin calibración / null |
| Libre | RX-02 / 5C93200689 | 149 | 13.1000619178 | 0.4364633982 | sin calibración / null |

Amplitud en unidades derivadas del int8 sin calibrar; varianza en sus unidades al cuadrado. Las **598 medias por fila con referencias** están en cuatro JSONL separados en [la salida local](local/adaptador-presencia-offline-20261026/extraccion-fisica-03/features.resumen.json); el resumen público fija nombre, tamaño, número de filas y SHA-256 de cada JSONL. No se incluyen matrices, brutos o canónicos en Git.

En ambas sesiones siguen `connection_full=rechazada`, `experimental_window=conforme` y global rechazado. No hubo consulta de modelo, puntuación de confianza, clasificación, ajuste de anclas/umbrales o nuevo intervalo. El inicio físico y la continuidad del movimiento libre siguen inciertos; no se infieren desde estas medias/varianzas. Dos sesiones de una persona presente no permiten atribuir causalidad o calcular precisión.

## Pruebas, preservación y reproducción

**22 pruebas aprobadas, cero fallos/omisiones**: fórmulas poblacionales, ceros válidos, máscaras/guardas/layout, filas/campos ausentes, no finitos, cobertura, fronteras, timestamps repetidos, RX/USB independientes, HT excluido, ausencia de anclas, separación de alcances, falta de separabilidad y políticas del head. El test físico bloquea `train`, `infer`, `serial.Serial` y descubrimiento de puertos: ninguna se invoca durante extracción. Los resultados coinciden con las estadísticas descriptivas LLTF previas; no se recalculó su aceptación.

Se preservaron **598 archivos anteriores** por SHA-256, incluidos informes, figuras, código, capturas y estados. [Registro de verificación y hashes](ADAPTADOR_PRESENCIA.validacion.json). No se ejecutó la suite de adquisición porque no se modificó ese código. Los fallos de integridad detienen la CLI; no se descargan o simulan datos faltantes para completar la evidencia.

Extracción en una salida local nueva y comprobación del resumen publicado (requieren los originales locales; no instalan Rust):

```sh
.venv/bin/python -B tools/extraer_presencia_offline.py \
  --output-new results/local/EXTRACCION-PRESENCIA-NUEVA
.venv/bin/python -B tools/extraer_presencia_offline.py \
  --check results/ADAPTADOR_PRESENCIA_FISICAS.resumen.json
./tools/offline_sandbox.sh .venv/bin/python -B -m unittest discover \
  -s tests -p test_presence_offline.py -v
```

Opcional para reproducir la referencia Rust, en Linux x86_64; el preparador conserva destinos existentes y nunca ejecuta instaladores remotos:

```sh
.venv/bin/python -B tools/preparar_rust_presencia.py
.venv/bin/python -B tools/verificar_port_presencia.py \
  --output-new results/local/EQUIVALENCIA-SINTETICA-NUEVA
```

Los dos ejecutores de extracción/equivalencia usan Bubblewrap con fuentes de solo lectura, salida nueva escribible, red aislada y `/dev` privado. Core/CLI de extracción y referencia no tienen opciones de UART. No se abrió UART físico, adquirieron datos, resetearon placas o modificaron firmware/protocolo. **Ninguna autorización física vigente; ningún detector de presencia validado sobre datos reales.**

## Reanudación y cierre documental — 27 de octubre de 2026

Se comprobó primero Git: rama `feat/adaptador-presencia-offline`, HEAD `796d534a9d04bb040f9868f77030980529ec02e7`, dos documentos modificados y los archivos del adaptador sin seguimiento; sin cambios preparados ni stashes. Se retomó esa implementación existente, sin reescribirla, reinstalar herramientas o duplicar extracciones. El conector de GitHub confirmó la misma base remota y que todavía no existía la rama del adaptador.

Volvieron a aprobarse **22 pruebas, cero fallos, errores u omisiones**, mediante `.venv/bin/python -B -m unittest discover -s tests -p test_presence_offline.py -v`. Se revisaron previamente sus rutas: usan memoria y archivos existentes; el caso físico bloquea calibración, inferencia, apertura serial y descubrimiento de puertos. La reconstrucción del informe físico volvió a coincidir íntegramente con el JSON publicado bajo esos mismos bloqueos, sin generar otra extracción en disco. Se contrastaron las 598 filas contra CSV, bytes y hashes de líneas originales, y los 598 archivos anteriores permanecieron idénticos.

Se verificaron las 35 referencias guardadas a fuentes, artefactos y registros, los extractos y la licencia contra los blobs del checkout RuView fijado, y los dos archivos oficiales del compilador contra sus hashes. Se volvió a ejecutar el **binario Rust ya guardado**, únicamente con las entradas sintéticas existentes: **2022 salidas idénticas** a Python (513 modelos/inferencias y 1509 resultados sin anclas). No se recompiló el arnés ni se ejecutó Cargo. El registro [de validación](ADAPTADOR_PRESENCIA.validacion.json) distingue la comprobación original de esta reanudación y actualiza los hashes de los documentos finales. La comprobación del diff preparado incluye los archivos nuevos; [.gitattributes](../.gitattributes) exceptúa únicamente la línea final en blanco del extracto Rust literal para conservar su hash upstream, sin desactivar los demás controles de espacios.

**Límite del entorno actual:** `tools/offline_sandbox.sh` falla porque Bubblewrap no puede crear namespaces. La repetición directa de unittest se ejecutó dentro del entorno restringido disponible; no se acredita un nuevo aislamiento Bubblewrap ni una ejecución satisfactoria de las CLI aisladas. Los wrappers conservan su fallo explícito si no pueden aislar. No se ejecutaron pruebas de adquisición ni se accedió a dispositivos físicos. Los registros de la reanudación permanecen en `results/local/reanudacion-presencia-offline-20261027/`.

Para repetir la referencia Rust en el entorno compatible, reutilizar `.tools/rust-presence-1.85.1` si ya existe; ejecutar el preparador solo si falta. Los originales físicos y los binarios locales no se descargan ni se incluyen en Git. Desde un clon sin esos originales se omite explícitamente la prueba física; eso no reproduce las 22 pruebas sin omisiones de esta máquina.

Pendientes para el hito físico posterior:

- Revisar montaje, etiquetado exterior, repetibilidad de READY y criterios prospectivos del [plan piloto](../docs/PLAN_CAMPAÑA_PRESENCIA_PILOTO.md).
- Disponer de sesiones vacías y ocupadas elegibles, con autorización nueva; definir y validar un banco físico por RX antes de habilitar calibración o inferencia físicas.
- Evaluar con sesiones completas independientes. La equivalencia matemática y estos rasgos no demuestran precisión de presencia.
- Repetir las CLI con Bubblewrap en un entorno que permita namespaces si se necesita acreditar nuevamente ese aislamiento.

La entrega se prepara como un único commit sobre la base comprobada. Git HTTPS no resuelve `github.com` en este entorno; la publicación usa el conector GitHub, con igualdad del árbol Git local y remoto y comprobación posterior del SHA de la rama. La publicación no modifica `main` ni incorpora brutos, binarios o artefactos locales.
