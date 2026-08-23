# sources/

**Productor.** De acá salen las imágenes que procesa el resto del sistema. Es el
primer eslabón: nada entra al sistema sin pasar por esta carpeta.

## Lo que ya existe

### `fuente.py` — la interfaz común

`Cuadro` (una imagen con su **instante de captura**) y el protocolo
`FuenteImagen`, que es lo único que el resto del sistema necesita conocer.

Existe para que la **cámara real** y el **generador sintético** sean
intercambiables: quien consume imágenes recibe una `FuenteImagen` y no pregunta
cuál le tocó. Si supiera la diferencia habría dos caminos que mantener, y el
sintético dejaría de servir para verificar el real.

La marca de tiempo es la de **captura**, no la de uso: ese valor viaja después
hasta el `ts_ms` del contrato y es lo que les permite a los equipos medir cuán
viejo es el dato con el que navegan.

### `camara.py` — la webcam USB real

```python
from vision.configuracion import cargar_config
from vision.sources.camara import FuenteCamara

with FuenteCamara(cargar_config().camara) as camara:
    cuadro = camara.leer()          # no bloquea nunca
```

**Lectura que no bloquea.** Un hilo lee la cámara sin parar y deja el último
cuadro en una ranura de **un solo lugar**: si llega uno nuevo antes de que lo
consuman, pisa al anterior. Es la misma política del publicador —el último valor
gana— por la misma razón: un cuadro viejo no sirve, y así el procesamiento nunca
espera a la cámara.

**Ajustes fijos, y verificados de verdad.** Intenta pasar exposición, enfoque y
balance de blancos a manual, y reporta para cada uno qué pasó. La parte
importante es que **no le cree a la cámara**: `set()` y `get()` mienten en muchos
modelos, que aceptan el valor, lo reportan de vuelta y siguen haciendo lo que
quieren. Por eso `verificar_por_efecto()` fija dos valores muy distintos y mide
si **la imagen cambió** —brillo para exposición, nitidez para enfoque, relación
azul/rojo para balance—.

Eso es lo que responde la pregunta que importa: si se puede fijar la exposición.
Con exposición automática, la cámara sube la ganancia para "compensar" el robot
negro y quema los marcadores blancos.

> **En macOS es esperable que diga "no soportado".** OpenCV sobre AVFoundation
> casi no expone controles de cámara. No significa que la cámara no sirva: la
> prueba que vale se hace en Windows con DSHOW, que es el destino de despliegue.

### `generador_sintetico.py` — imágenes de prueba con verdad conocida

Dibuja imágenes cenitales sintéticas del tablero: los cuatro marcadores ArUco de
esquina y los rovers que se le pidan, cada uno con su marcador, su posición y su
orientación.

Lo que lo hace valioso no es dibujar, sino que **devuelve la verdad de cada
imagen que crea**: qué marcador puso, en qué celda, con qué ángulo y en qué
píxeles quedó. Sin esa verdad, una prueba solo podría decir "no explotó"; con
ella puede decir "está bien, y por este margen".

```python
from vision.configuracion import cargar_config
from vision.sources.generador_sintetico import generar

cfg = cargar_config()
imagen, verdad = generar(cfg)
print(verdad.celda_a_pixel(21.5, 21.5))   # el centro de la cancha -> (640.0, 640.0)
```

#### Tiene una cámara de verdad, no un trapecio

El modo "con perspectiva" **no** deforma la imagen: hay una **cámara
estenopeica** con posición, objetivo e intrínsecos, y todo se proyecta con
`projectPoints`. La inclinación es el ángulo **físico** entre el eje óptico y la
vertical, el que se mediría con un transportador sobre el soporte.

Importa porque sin rayos no se pueden simular las dos cosas que el sistema tiene
que resolver de verdad:

- el **paralaje**: un objeto con altura se ve corrido porque su rayo cruza el
  plano del tablero en otro lado. Los marcadores de rover se dibujan a sus
  **90 mm** reales y los cubos como **cajas 3D**;
- la **oclusión**: un objeto tapa a otro cuando se le pone en el rayo. Sale del
  algoritmo del pintor —se dibuja de lejos a cerca— sin programarla.

Eso es lo que permite verificar el caso más frecuente del juego: un rover
empujando un cubo hacia una esquina le esconde el **22 %** del área, y justo la
arista de la base.

> El mundo se define con `Y = −row`. Sin ese menos, una cámara real mirando hacia
> abajo produce la imagen **espejada**, y un ArUco espejado no lo detecta nadie
> porque no coincide con ninguna entrada del diccionario.

La imagen sale en **BGR**, como la que entrega la cámara real.

Incluye además, configurable desde `config_vision.json`: **altura e inclinación**
de la cámara simulada, y **desenfoque y ruido** para ver cuánto aguanta la
detección antes de fallar.

#### `FuenteSintetica` entrega a una tasa, como la cámara

Cumple la misma interfaz que la cámara, así que el sistema entero corre sin
cámara y sigue teniendo la verdad para verificar lo que deduce.

Y entrega **a la misma tasa** que se le pide a la cámara real: si el próximo
cuadro todavía no toca, devuelve `None`. Antes entregaba tan rápido como se lo
pidieran, y eso la volvía distinta de la cámara justo en lo que más importa —el
ritmo al que late el sistema—. Apareció midiendo el falla-abierto: con el
procesamiento roto, el bucle daba **1,3 millones de vueltas por segundo**.

Cuando se atrasa **no entrega una ráfaga** para ponerse al día. Un cuadro viejo
no le sirve a nadie: es la misma lógica del último-valor-gana, aplicada del lado
de la entrada.

> **Ojo, no confundir con el simulador de `contrato/`.** Aquel emite *posiciones
> en JSON* por la red, para que los equipos prueben su rover. Este dibuja
> *imágenes*, para que el sistema de visión tenga qué procesar. Uno se consume
> por TCP; el otro entra por el lado de la cámara.

### Elegir qué cámara abrir

El índice de una webcam USB **no es estable**: depende de qué se enchufó
primero, de si hay una cámara integrada y de si la máquina se reinició. Un
número escrito en la configuración funciona hoy y falla mañana, con un error que
parece de permisos o de cámara rota y no lo es.

Por eso `camara.indice` en `config_vision.json` acepta tres cosas:

| Valor | Qué hace |
|---|---|
| un número | Lo usa, **si responde**. Es el camino rápido: no sondea nada ni molesta a nadie. |
| `"menu"` | Muestra las cámaras del sistema numeradas y pregunta cuál abrir. |
| `"auto"` | Toma la primera que entregue imágenes. |

Si el índice pedido no responde, se prueban los demás y se usa el primero que
entregue imágenes, **avisando cuál se eligió**: es preferible funcionar con un
aviso a fallar por un número desactualizado.

> **El menú lista los nombres y los índices por separado, a propósito.** Sería
> más cómodo mostrar "índice 0 → Logitech C270", pero **ese apareo sería
> falso**: en macOS el orden en que el sistema operativo lista las cámaras y el
> orden de los índices de OpenCV **no coinciden** —lo comprobamos en esta
> máquina, donde el índice 0 era la webcam USB y el sistema listaba primero la
> integrada—. Aparearlos daría una respuesta con aspecto de certeza y
> equivocada, que es peor que pedirle a la persona que mire cuál se abre.

El menú se arma con la lista del **sistema operativo**, no con el resultado de
sondear. Sondear es lento y poco confiable, y usarlo para decidir qué mostrar
fue justo lo que hizo que se eligiera sola la cámara equivocada: si la del
tablero no contestaba en ese intento, desaparecía del menú.

## Lo que todavía NO existe

Planificado, sin código aún:

- **Reconexión automática.** Si la webcam se desconecta a mitad de ronda, hoy la
  fuente cuenta fallos y sigue devolviendo el último cuadro; falta que intente
  reabrirla sola.
