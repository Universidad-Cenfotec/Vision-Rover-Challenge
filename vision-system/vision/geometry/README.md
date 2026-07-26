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

## Lo que todavía NO existe

Planificado, sin código aún:

- **Calibración de distorsión.** El lente gran angular curva las líneas rectas;
  hay que medir esa curvatura una vez y corregirla en cada cuadro. Sin esto, un
  objeto cerca del borde aparece corrido aunque la homografía sea perfecta.
- **Corrección de paralaje.** Los objetos **altos** —un cubo de 6 cm, el marcador
  de un rover a unos 10 cm— no se ven donde están: se ven corridos **hacia
  afuera**, alejándose del centro de la cámara, porque la cámara los mira de
  costado. Se corrige con la **pose de cámara** deducida de los cuatro marcadores
  más la **altura conocida** de cada objeto.
