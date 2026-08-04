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
print(verdad.celda_a_pixel(25, 25))   # dónde quedó el centro del tablero
```

Incluye, configurable desde `config_vision.json`:

- **inclinación de cámara** opcional (apagada por defecto), porque la cámara real
  nunca va a estar perfectamente cenital;
- **desenfoque y ruido**, para ver cuánto aguanta la detección antes de fallar.

Expone también `FuenteSintetica`, que cumple la misma interfaz que la cámara: se
puede correr el sistema entero sin cámara y seguir teniendo la verdad para
verificar lo que deduce.

> **Ojo, no confundir con el simulador de `contrato/`.** Aquel emite *posiciones
> en JSON* por la red, para que los equipos prueben su rover. Este dibuja
> *imágenes*, para que el sistema de visión tenga qué procesar. Uno se consume
> por TCP; el otro entra por el lado de la cámara.

## Lo que todavía NO existe

Planificado, sin código aún:

- **Elegir la cámara por nombre y no por índice.** Hoy se abre por número de
  índice, que cambia según qué se enchufó primero. Identificarla por su nombre
  evitaría abrir la cámara integrada de la laptop por error.
- **Reconexión automática.** Si la webcam se desconecta a mitad de ronda, hoy la
  fuente cuenta fallos y sigue devolviendo el último cuadro; falta que intente
  reabrirla sola.
