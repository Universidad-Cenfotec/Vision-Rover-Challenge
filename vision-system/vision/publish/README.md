# publish/

**Consumidor.** Emite el estado del mundo por la red, en el formato del
contrato. Es la única pieza del sistema que los equipos ven.

## Estado: publicando

**Todavía no hay código acá.** Pero el comportamiento **ya está implementado y
probado** en el simulador del contrato
([`../../contrato/mock_publisher.py`](../../contrato/mock_publisher.py)), que
publica exactamente el mismo formato con la misma política. Cuando se escriba
esta pieza, el simulador es la referencia a seguir.

## Lo que ya existe

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


---

## Cómo está armado

### El transporte NO está acá

Abrir el puerto, aceptar clientes y la política de **el último valor gana** viven
en [`contrato/publicador.py`](../../contrato/publicador.py), **compartidos con el
simulador**.

El contrato les promete a los equipos que pasan del simulador a la cancha **sin
tocar su código**, y esa promesa no es solo sobre el formato del mensaje: también
es sobre cómo se comporta la conexión. Con dos implementaciones podrían divergir
sin que nadie lo note, y un equipo se toparía con la diferencia el día de la
competencia.

Lo que sí está acá es lo propio de este lado: el **reloj de publicación**, el
**contador de secuencia** y la **casilla del último estado bueno**.

### Los dos relojes

El procesamiento corre a la velocidad de la cámara; la publicación, por
**temporizador propio** a 20 Hz. Entre los dos hay **una sola casilla** con el
último estado producido.

`actualizar()` nunca bloquea: deja el estado y vuelve. Eso es lo que garantiza
que la red no pueda frenar al procesamiento. Y al revés: si un cliente tiene la
red lenta, la lentitud queda encerrada en el hilo de ese cliente.

### Falla abierto

La casilla conserva el **último estado bueno**. Si el procesamiento tira una
excepción y deja de actualizarla, la publicación **sigue emitiendo**: un dato de
hace 300 ms, marcado como viejo, le sirve más a un equipo que un silencio
repentino.

Antes del primer cuadro se publica igual, con las listas vacías y fase `IDLE`.
Que todavía no haya nada detectado es información, no un motivo para callarse.

`edad_del_estado_ms()` es el termómetro: si sube mientras la publicación sigue,
se está emitiendo el último estado bueno porque algo anda mal del otro lado.

## Verificado

Contra [`contrato/test_client.py`](../../contrato/test_client.py) —el cliente de
referencia que usan los equipos, sin modificarle una línea— con el sistema de
visión real procesando imágenes sintéticas:

```
  recibidos=121 invalidos=0 saltos=0 (perdidos=0)
  latencia min/prom/max = 24/52/84 ms
```

Los **52 ms de latencia media** son reales y significan lo que dicen: `ts_ms` es
el instante de **captura**, así que ese número incluye detectar (unos 20 ms) y
esperar el siguiente tic de publicación (hasta 50 ms). El umbral que
[`CONTRATO.md`](../../contrato/CONTRATO.md) le sugiere a los equipos para frenar
es de 500 ms.
