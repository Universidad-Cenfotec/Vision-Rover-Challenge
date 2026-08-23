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
print(sistema.celda_de(640, 640))         # píxel -> celda:  (21.5, 21.5)
print(sistema.a_pixeles([[21.5, 21.5]]))  # celda -> píxel:  [[640.0, 640.0]]
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

**Verificado**, contra la verdad conocida del generador sintético: **exacto** con
la cámara cenital y **0,44 mm** de error máximo —dos centésimas de celda— con la
cámara inclinada, uniforme entre el centro, los bordes y el interior. Ver
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

Una vez rectificada la imagen, **todo lo de abajo trabaja sobre ella**: los
marcadores se detectan ahí y la homografía se calcula ahí, así que no hay que
reconvertir coordenadas en ningún lado. Lo único que no se puede hacer es
**mezclar** imágenes crudas y rectificadas en el mismo camino.

### Un perfil por cámara, no un perfil para todas

La distorsión **no es del sistema: es del aparato**. Dos webcams del mismo
modelo se parecen, pero una C270 y una CAM40 no tienen nada que ver. Por eso
cada cámara calibrada guarda su **propio archivo** en `vision/calibraciones/`:

```
vision/calibraciones/
├── argomtech_cam40.json     ← 1920x1080 · 0,314 px · 13 vistas
└── logitech_c270.json       ← 1280x720  · 0,206 px · 15 vistas
```

El nombre del archivo sale del nombre humano de la cámara con `nombre_archivo()`:
`"Logitech C270"` → `logitech_c270`. El nombre lindo se guarda **dentro** del
perfil; el del archivo tiene que ser seguro en cualquier sistema de archivos y
fácil de escribir en una línea de comandos.

**Cómo se elige cuál usar** (`elegir_perfil`), de más explícito a más automático:

| Situación | Qué hace |
|---|---|
| Se pasó `--camara "NOMBRE"` | Usa ese y nada más. Sin ambigüedad. Si no existe, falla diciendo cuáles hay y cómo calibrar esa |
| Hay **un solo** perfil guardado | Usa ese |
| Hay **varios** y hay terminal | Menú, **preseleccionando el que coincide con la resolución** de la cámara conectada |
| Hay **varios** y no hay terminal | El `perfil_por_defecto` de la configuración |

El último caso es el que mantiene andando al sistema corriendo solo: sin nadie
para contestar, nunca pregunta.

### El aviso de "EL PERFIL NO CORRESPONDE"

Aplicar el perfil de otra cámara **no da error**: da una imagen corregida al
revés, más deformada que la original, sin que nada avise. Nos pasó: la C270 se
veía peor rectificada que cruda, porque estaba tomando el perfil de la CAM40.

Por eso cada perfil expone una **huella** —resolución, campo de visión diagonal
y cuánto mueve un píxel del borde— y `comparar_con_camara()` la contrasta contra
lo que la cámara realmente entrega. Acumula **todas** las señales en vez de
quedarse con la primera, porque suelen aparecer juntas y cada una explica una
parte:

| Nivel | Cuándo | Qué significa |
|---|---|---|
| **incompatible** | La relación de aspecto no coincide | El perfil describe un sensor de otra forma. Aplicarlo **deforma** en vez de corregir |
| **sospechoso** | Misma forma, distinta resolución | Los parámetros se escalan; suele andar, pero pierde precisión |
| **compatible** | Todo calza | Se usa sin más |

**Una corrección fuerte NO levanta la alarma por sí sola.** Fue el primer diseño
y estaba mal: en un gran angular mover mucho el borde es lo normal y correcto, así
que la alarma saltaba también con la CAM40 usando su propio perfil. Un aviso que
salta siempre entrena a ignorar los avisos. Ahora solo **amplifica una sospecha
que ya existe** por otro motivo; si no, queda como dato informativo.

> El caso real que motivó todo esto —la C270 con el perfil de la CAM40— tiene la
> **misma relación de aspecto** (los dos son 16:9), así que el chequeo de forma
> solo no alcanzaba. Lo que lo delata es que la corrección es desproporcionada
> para el sensor que la recibe.

Para generar un perfil, ver [`../tools/README.md`](../tools/README.md).

### `coordenadas.py` — la pose de cámara y el paralaje

Los objetos **altos** no se ven donde están: se ven corridos **hacia afuera**,
alejándose del punto que está justo debajo de la cámara. El marcador del rover
está a 90 mm del tablero, y eso son hasta **41 mm** de error con la cámara
inclinada, contra un criterio de aceptación de 10.

Los cuatro marcadores de esquina **no pueden corregirlo por sí solos**: están al
ras del tablero, así que no contienen ninguna información sobre cuánto se
desplaza algo que tiene altura. Hace falta la **pose de la cámara**.

**Y no hay que declararla.** Los cuatro centros son puntos coplanares de posición
métrica conocida y la cámara está calibrada, así que `solvePnP` da la pose
completa. Nadie mide 2,1 m con una cinta: sale de los mismos marcadores que el
sistema ya tiene que ver, y si alguien mueve la cámara, el cuadro siguiente trae
una pose nueva.

> Los intrínsecos que se usan son los de la imagen **ya rectificada**
> (`Rectificador.matriz_nueva`) y no los del perfil: quitar la distorsión cambia
> los intrínsecos efectivos, y usar los de antes metería un error que después
> nadie sabría de dónde salió.

La corrección es una **homotecia centrada en el nadir** con factor `(H−h)/H`, y
es exacta para cualquier inclinación de cámara porque el rayo solo depende del
centro óptico y no de hacia dónde mire.

| Inclinación | Sin corregir | Corregido |
|---|---|---|
| 0° | 19,44 mm | **0,43 mm** |
| 8° | 30,07 mm | **1,03 mm** |
| 15° | 41,29 mm | **0,89 mm** |

Medido sobre 36 rovers repartidos por toda la cancha. Entre 30 y 45 veces mejor.

Dos propiedades que conviene saber:

- **El ángulo no se toca.** Una homotecia conserva las direcciones, así que la
  orientación del rover ya era correcta antes de corregir nada.
- **Es muy insensible al error de la pose.** Como solo escala por `(1−1/k)`, un
  4,3 %, trece milímetros de error en el nadir se traducen en 0,6 mm de posición.

Los **cubos no la necesitan**: se ubican por su borde inferior, que está en el
piso, y ahí el factor vale exactamente 1.

## Lo que todavía NO existe

Planificado, sin código aún:
