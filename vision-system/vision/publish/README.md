# publish/

**Consumidor.** Emite el estado del mundo por la red, en el formato del
contrato. Es la única pieza del sistema que los equipos ven.

## Estado: vacío

**Todavía no hay código acá.** Pero el comportamiento **ya está implementado y
probado** en el simulador del contrato
([`../../contrato/mock_publisher.py`](../../contrato/mock_publisher.py)), que
publica exactamente el mismo formato con la misma política. Cuando se escriba
esta pieza, el simulador es la referencia a seguir.

## Lo que va a existir

### Publicación TCP/NDJSON en el puerto 2026

Un JSON por línea, terminado en `\n`. Mismo puerto que el simulador, para que un
equipo pase del simulador a la cancha sin tocar su código.

### El último valor gana

Buffer de **un solo mensaje por cliente**. Si llega telemetría nueva y el cliente
no drenó la anterior, **la anterior se pisa**. Nunca se encola.

En telemetría de posición un dato viejo no vale nada: al rover le sirve saber
dónde está *ahora*. Con una cola, un cliente lento se atrasaría cada vez más sin
recuperarse jamás. Por eso los equipos ven saltos en el número de secuencia, y
eso es normal.

### Reloj propio

Corre **por temporizador**, desacoplado del procesamiento. Si un cuadro tarda de
más, la publicación no se frena: vuelve a mandar el último estado bueno, con su
marca de tiempo de captura original para que el consumidor note que está añejo.

Y al revés: un cliente con la red lenta no puede frenar el procesamiento.

### Falla abierto

Ante una excepción se conserva el último estado bueno y se sigue publicando. El
sistema no se cae a mitad de ronda.

> El formato exacto que hay que respetar está en
> [`../../contrato/CONTRATO.md`](../../contrato/CONTRATO.md). **Es un contrato:**
> no se cambia sin subir la versión de protocolo y avisarle a los equipos.
