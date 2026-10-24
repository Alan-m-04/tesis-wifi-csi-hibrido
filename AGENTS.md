# Instrucciones para Codex

## Proyecto

Tesis de sensado WiFi CSI con ESP32-S3 y Edge AI para MIPYMES de Riobamba. Construir un sistema híbrido con componentes verificables de RuView y firmware propio. Procesamiento en PC local; conservar ESP-IDF v5.4.

## Forma de trabajar

- Revisar README y docs/ESTADO_INICIAL.md antes de cambiar código.
- Mantener los objetivos del anteproyecto aprobado. Presencia es el primer hito, no el alcance total de la tesis.
- Conservar las fuentes y capturas originales. Importar copias verificadas sin sobrescribir los originales.
- Registrar cambios pequeños y claros en Git; ejecutar las pruebas relevantes y documentar sus resultados reales.
- No afirmar acceso a archivos de Ubuntu o dispositivos que no estén disponibles en el entorno actual.
- No instalar herramientas mediante scripts remotos sin inspeccionarlos.

## Hardware y datos

- Solicitar autorización explícita antes de abrir UART físicos, flashear o modificar dispositivos y originales.
- No instalar firmware RuView en TX-01, RX-01 ni RX-02 sin una instrucción nueva y explícita del usuario.
- Mantener la validación estricta del capturador. Conservar arranques, residuos y errores en los registros brutos.
- Separar receptores por identidad USB verificada. No suponer que ttyACM0 y ttyACM1 mantienen su identidad.
- Verificar orden complejo, dimensiones, configuración LTF, subportadoras, indicadores de invalidez y relojes antes de transformar CSI.
- Conservar RSSI, MAC, secuencias, timestamps y metadatos originales. Registrar pérdidas de representación.
- No rellenar datos faltantes, simular mediciones completas ni aumentar artificialmente la frecuencia.

## Evidencia y modelos

- Distinguir antecedentes declarados, código inspeccionado, pruebas sintéticas y validación física.
- Fijar commit y licencia de cada componente externo reutilizado; conservar atribuciones.
- Comprobar existencia y carga de pesos, frecuencia y geometría antes de aplicar modelos.
- No entrenar con registros insuficientes ni mezclar sesiones entre entrenamiento y evaluación.
- Priorizar presencia básica. No implementar pose, signos vitales ni actividades antes de validar ese hito.
- Actualizar docs/ESTADO_INICIAL.md o un informe posterior con lo conseguido, pruebas, límites y pendientes.
