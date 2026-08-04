# geometry/

**Productor.** Traduce lo que ve la cámara —**píxeles**— a lo que publica el
sistema —**celdas de la cancha**—. Es el cimiento: si esta pieza está mal, todo
lo que venga después está mal en la misma medida.

## Lo que ya existe

### `coordenadas.py` — el sistema de coordenadas de la cancha

Detecta los cuatro marcadores ArUco de esquina, verifica que estén los cuatro
IDs esperados y construye la transformación que convierte cualquier píxel de la
imagen en una coordenada en celdas.

```python
from vision.configuracion import cargar_config
from vision.geometry.coordenadas import construir_sistema

sistema = construir_sistema(imagen, cargar_config())
print(sistema.celda_de(640, 640))     # píxel -> celda
print(sistema.a_pixeles([[25, 25]]))  # celda -> píxel
```

**Por qué una homografía y no una simple escala.** Porque la cámara real nunca va
a estar perfectamente cenital. Con cualquier inclinación, el tablero se ve como
un trapecio y no como un rectángulo: una escala daría bien en el centro y mal en
los bordes. La homografía es la transformación exacta entre dos planos vistos en
perspectiva, y el tablero es un plano. Cuatro puntos la determinan por completo.

**Por qué los centros de los marcadores y no sus esquinas.** El centro es el
promedio de las cuatro esquinas detectadas, así que reparte el ruido en vez de
arrastrar el de una sola. Y es lo único medible sin ambigüedad en la cancha
física: "el centro del marcador" no admite discusión, "su esquina superior
izquierda" sí.

**Verificado**, contra la verdad conocida del generador sintético: error máximo
de **0,2 mm** —una centésima de celda— y uniforme entre el centro, los bordes y
el interior, también con la cámara inclinada. Ver
[`../tools/README.md`](../tools/README.md).

Ante datos insuficientes levanta `ErrorGeometria` con un mensaje que dice qué
revisar, en vez de devolver coordenadas en las que no se puede confiar.

> La disposición exacta de los marcadores en la cancha física está en
> [`MONTAJE.md`](../../MONTAJE.md). Pegarlos en otro orden rota todas las
> coordenadas.

### `distorsion.py` — corrección del lente gran angular

Un lente ancho **curva las líneas rectas**, y cada vez más cerca de los bordes.
La homografía de `coordenadas.py` **no puede arreglar eso**: es exacta para
describir un plano visto en perspectiva, pero supone que las rectas siguen
siendo rectas. La distorsión rompe justamente esa suposición, así que hay que
quitarla **antes**:

```
cámara --> [rectificar] --> detectar marcadores --> geometría de esquinas
```

```python
from vision.geometry.distorsion import cargar_perfil, Rectificador, FuenteRectificada

rect = Rectificador(cargar_perfil("vision/calibraciones/argomtech_cam40.json"))
fuente = FuenteRectificada(FuenteCamara(cfg.camara), rect)
cuadro = fuente.leer()      # ya viene sin distorsión
```

`FuenteRectificada` cumple la interfaz `FuenteImagen`, así que se enchufa delante
sin que nada de lo que viene después se entere. Se hace por composición y no
metiéndole la corrección a la cámara porque son dos responsabilidades distintas
—capturar y corregir— y así la misma capa sirve también para la fuente sintética.

Los mapas de corrección se calculan **una sola vez** (`initUndistortRectifyMap`)
y después cada cuadro es solo un `remap`: a 30 cuadros por segundo sobre 1080p,
recalcularlos cada vez se notaría.

El resultado de calibrar se guarda como **perfil de cámara** en JSON
(`vision/calibraciones/*.json`), que es configuración de un aparato concreto y
no del sistema. Para generarlo, ver
[`../tools/README.md`](../tools/README.md).

Una vez rectificada la imagen, **todo lo de abajo trabaja sobre ella**: los
marcadores se detectan ahí y la homografía se calcula ahí, así que no hay que
reconvertir coordenadas en ningún lado. Lo único que no se puede hacer es
**mezclar** imágenes crudas y rectificadas en el mismo camino.

## Lo que todavía NO existe

Planificado, sin código aún:

- **Corrección de paralaje.** Los objetos **altos** —un cubo de 6 cm, el marcador
  de un rover a unos 10 cm— no se ven donde están: se ven corridos **hacia
  afuera**, alejándose del centro de la cámara, porque la cámara los mira de
  costado. Se corrige con la **pose de cámara** deducida de los cuatro marcadores
  más la **altura conocida** de cada objeto.
