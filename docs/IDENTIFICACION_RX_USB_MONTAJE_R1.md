# Asociación de las fotos a los RX: metadatos y observación pendiente

Consulta autorizada exclusivamente de metadatos USB, sin abrir UART, desconectar
o mover equipos. Base Git: `4cd768aeea090966777e95bc7df6aded2d8afbdf`.
Registro local: `results/local/identificacion-rx-usb-metadatos-r1/metadatos-usb.json`.
No es un preflight completo ni una adquisición. `/dev/serial/by-id` no es visible
en este entorno; sí lo son sysfs y las propiedades udev consultadas por `--path`.
Los nombres tty siguientes proceden de metadatos y no se abrieron sus nodos.

## Identidades y rutas actuales comprobadas

| Identidad | Serie USB | Ruta sysfs USB | Ruta udev de la interfaz tty | tty en metadatos |
|---|---|---|---|---|
| RX-01 | `5C93199744` | `3-7.1` | `pci-0000:00:14.0-usb-0:7.1:1.0` | `ttyACM1` |
| RX-02 | `5C93200689` | `3-4` | `pci-0000:00:14.0-usb-0:4:1.0` | `ttyACM0` |

Ambos son VID/PID `1a86:55d3`, producto `USB Single Serial`, driver `cdc_acm`,
y dependen del controlador PCI `0000:00:14.0`, bus USB 3. La identidad se apoya
en la serie USB, no en el número tty, color, LEDs, forma de la placa o antena.

RX-01 cuelga del puerto descendente 1 de `3-7`, un hub `GenesysLogic USB2.1 Hub`,
VID/PID `05e3:0610`, conectado al puerto 7 del hub raíz. RX-02 cuelga del puerto 4
del mismo hub raíz, sin ese hub intermedio en la ruta. «Directo» describe la
topología USB enumerada; no acredita por sí solo el extremo físico de un cable
o la ausencia de adaptadores pasivos.

Estas rutas muestran que los caminos actuales difieren en el hub intermedio;
no implican controladores PCI distintos. Tampoco demuestran que el hub cause
los 171/296 registros históricos. El bundle anterior no registró estas rutas
ID_PATH; no se añaden retrospectivamente a sus metadatos originales.

## Por qué todavía falta la asociación física definitiva

El firmware del sistema expone para los puertos raíz 4 y 7 las mismas etiquetas:
panel `top`, horizontal `left`, vertical `upper`, dock/lid `no`. Las ubicaciones
numéricas `0x80000004` y `0x80000007` distinguen rutas internas, pero no indican
qué conector externo se ve a cada lado de la laptop. No se traducen a izquierda/
derecha o a un conector concreto por intuición.

En la foto `ChatGPT Image Nov 3, 2026, 02_23_17 PM.jpg` se aprecia el cable USB azul
curvándose hacia el adaptador visible. La foto `02_23_29 PM` no muestra de forma
suficientemente inequívoca todo el extremo del host para cerrar la asociación
por sí sola. La ruta visible es compatible con la distinción hub/directo, pero
la correspondencia fotográfica permanece **pendiente de confirmación del recorrido**.

## Observación requerida, sin manipulación

Seguir únicamente con la vista cada cable USB azul desde su placa hasta el
extremo del host, sin tirar, levantar el cable, mover objetos o desconectar:

1. Confirmar si el cable de `02_23_17 PM` entra en el adaptador/hub marrón visible
   y si ese es el hub conectado a la laptop por el que pasa ese RX.
2. Confirmar si el de `02_23_29 PM` entra directamente en un puerto de la laptop
   o también pasa por un adaptador/hub.
3. Si un tramo está oculto o hay más adaptadores, describirlo y mantener la
   asociación pendiente; no mover nada para despejarlo.

Solo tras confirmar esos extremos: el RX cuyo USB pase por el hub enumerado es
RX-01; el que siga la conexión directa es RX-02. Si la observación no encaja con
esa topología, revisar metadatos y recorrido antes de asignar fotos. No emitir
órdenes de reset, localizar por parpadeo, abrir monitor serie o desenchufar para
ver cuál desaparece.

Una vez cerrada la asociación se revisará la articulación de **esa antena RX-01**,
sin inferir que una rosca es articulación o que admite giro sin tensión. El
[plan r2](PLAN_ORIENTACION_ABA_CONTINUIDAD_R2.md) continúa pendiente: no se ha
definido ni autorizado una maniobra física o adquisición. Fotos, brutos, colas
y autorización consumida del intento anterior permanecen intactos.

## Actualización: asociación confirmada por el operador

Alan confirma el seguimiento visual: `02_23_17 PM` llega al hub marrón y
`02_23_29 PM` directamente a la laptop, sin movimientos o desconexiones. La
[asociación registrada](ASOCIACION_RX_FOTOS_CONFIRMADA_R1.md) es RX-01 para
`02_23_17 PM` y RX-02 para `02_23_29 PM`. Los apartados pendientes anteriores
describen la situación previa a esta confirmación; la identificación queda resuelta.
