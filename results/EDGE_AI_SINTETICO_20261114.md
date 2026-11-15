# EVALUACIÓN SINTÉTICA · SIN VALIDEZ FÍSICA

Prueba de integración de software. No estima exactitud física ni desempeño en una MIPYME.

Contrato: `presence-offline-v1/LLTF52/row-mean/session-population`. RuView `fefb0f918eefa7db6daef8cc83787fc7d6f74187` (MIT).

Partición por conexiones completas; E y S de una conexión siempre juntas.

- train: SYNTHETIC-TRAIN-01, SYNTHETIC-TRAIN-02
- evaluation: SYNTHETIC-EVAL-01, SYNTHETIC-EVAL-02, SYNTHETIC-EVAL-03

| Verdad / predicción | Vacío | Ocupado | Abstención |
| --- | ---: | ---: | ---: |
| Vacío | 1 | 1 | 1 |
| Ocupado | 1 | 1 | 1 |

| Métrica | Valor |
| --- | ---: |
| evaluation_windows | 6 |
| decided_windows | 4 |
| abstentions | 2 |
| coverage | 0.6666666666666666 |
| accuracy_decided | 0.5 |
| correct_over_all_windows | 0.3333333333333333 |
| false_alarms | 1 |
| false_negatives | 1 |
| false_alarm_rate_decided_empty | 0.5 |
| false_alarm_rate_all_empty | 0.3333333333333333 |
| abstention_rate | 0.3333333333333333 |

La tasa de falsas alarmas decididas es FP/(FP+TN); el otro denominador incluye
las abstenciones en vacío. Los cocientes sin denominador se guardan como null.
La cobertura y los aciertos sobre todas las ventanas impiden ocultar abstenciones.

El port original usa la primera ancla Empty y promedia las ocupadas. Se fija el orden
lexicográfico por ID antes de leer evaluación. No se seleccionan umbrales con evaluación.
El margen de confianza no es una probabilidad. Una máscara incompleta invalida toda
la característica; un modelo no separable produce abstención.

Ver JSON para características, rechazos conservados, decisiones y métricas por sesión.
No se han leído C04–C06 ni abierto UART. No hay adquisición o detector en vivo.
