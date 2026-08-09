# tools/

**Herramientas visuales.** Utilidades que apoyan la puesta a punto. No forman
parte del flujo de publicación: nada de lo que hay acá se ejecuta durante una
ronda.

> **¿Vas a poner a punto una cámara?** El procedimiento en orden, paso a paso,
> está en [`PUESTA_A_PUNTO.md`](../../PUESTA_A_PUNTO.md). Este README es la
> **referencia** de cada herramienta —qué hace, todas sus opciones y por qué
> está hecha así—; aquel es el **instructivo**.

## Lo que ya existe

### `verificar_geometria.py`

Verifica el sistema de coordenadas contra la **verdad conocida** del generador
sintético de `sources/`: genera una imagen del tablero, detecta los cuatro
marcadores de esquina, construye la transformación de píxeles a celdas y mide
cuánto se desvía de lo real.

```bash
python -m vision.tools.verificar_geometria
python -m vision.tools.verificar_geometria --salida /tmp/tablero.png --anotar
```

Mide en puntos que **no participaron del ajuste** de la homografía —el centro,
los medios de los bordes y una rejilla interior—, porque una homografía de
cuatro puntos es exacta en esos cuatro por definición y verificar sobre los
marcadores no probaría nada. Corre en dos modos, con y sin inclinación de
cámara, y devuelve código de salida distinto de cero si algún grupo se pasa del
umbral.

### `verificar_rovers.py`

Verifica la **detección de rovers** contra la misma verdad conocida: genera
imágenes con rovers en celdas y ángulos que el generador sabe, los detecta y
compara. Reporta error de **posición** (celdas y mm) y de **orientación**
(grados), con máximo, promedio y umbral.

```bash
python -m vision.tools.verificar_rovers
python -m vision.tools.verificar_rovers --salida /tmp/rovers.png --anotar
python -m vision.tools.verificar_rovers --umbral-mm 5 --umbral-grados 2
```

Corre cuatro escenarios en los dos modos de cámara:

| Escenario | Qué pone a prueba |
|---|---|
| Los dos rovers de la configuración | el caso de todos los días |
| Cinco rovers repartidos | que cada rover se corresponde con **su** ID |
| Ángulos en el borde del círculo | el salto de 359° a 0° |
| Barrido cada 10° | que el ángulo está bien en todo el círculo |

La prueba de identidad no se conforma con que los errores sean chicos: exige que
**cada rover esté más cerca de su propia verdad que de la de cualquier otro**.
Dos rovers que se intercambiaran el ID podrían tener errores individuales
razonables y estar todo mal.

El escenario del salto angular imprime, al lado, la **resta ingenua** y la
diferencia bien calculada, para que se vea el problema en vez de tener que
creerlo.

### `diagnostico_camara.py`

Responde si la cámara sirve tal cual o hay algo que resolver. Abre la webcam,
muestra el video en vivo e informa **fps reales**, **edad del cuadro**, qué
ajustes aceptó de verdad y **si ve los cuatro marcadores de esquina**,
dibujándolos sobre la imagen.

```bash
python -m vision.tools.diagnostico_camara            # ventana en vivo
python -m vision.tools.diagnostico_camara --listar   # ¿qué cámaras responden?
python -m vision.tools.diagnostico_camara --indice 1 # elegir otra cámara
python -m vision.tools.diagnostico_camara --sintetico    # sin cámara
python -m vision.tools.diagnostico_camara --sin-ventana  # sin pantalla
python -m vision.tools.diagnostico_camara --segundos 10  # cerrar solo a los 10 s
python -m vision.tools.diagnostico_camara --sin-efecto   # saltear la prueba de ajustes
```

Si no se pasa `--indice`, respeta lo que diga `camara.indice` en la
configuración, que además del número acepta `"menu"` para elegir de una lista.
Ver [`../sources/README.md`](../sources/README.md).

La información en pantalla la dibuja [`panel.py`](#panelpy), que es lo que
permite que diga "exposición" y no "exposici??n".

Al cerrar imprime un resumen en lenguaje claro con lo que encontró y qué hacer
si falta algo. Reusa la detección de marcadores de
[`../geometry/`](../geometry/README.md): escribir otra acá daría dos
implementaciones que pueden divergir, y el diagnóstico dejaría de decir nada
sobre el sistema real.

El indicador que más importa apuntando al tablero físico es
**"MARCADORES DE ESQUINA: 4 de 4"**: significa que el mundo real se comporta como
lo sintético y las coordenadas se pueden anclar.

### `patron_calibracion.py`

Genera en PDF, **a tamaño real**, el ajedrezado que necesita la calibración.

```bash
python -m vision.tools.patron_calibracion --salida patron.pdf
python -m vision.tools.patron_calibracion --columnas 9 --filas 6    # version de una hoja
python -m vision.tools.patron_calibracion --marcador-prueba 20      # el marcador de precisión
```

**Qué patrón elegir.** Con cuadros de 25 mm sobre papel Carta horizontal:

| Esquinas internas | Tamaño | Hojas | Empalmes |
|---|---|---|---|
| 9 × 6 | 250 × 175 mm | 1 | 0 |
| **13 × 6** ← por defecto | **350 × 175 mm** | **2** | **1** |
| 13 × 9 | 350 × 250 mm | 4 | 3 |

Un patrón más ancho cubre mejor los bordes del cuadro, que es donde más
distorsiona el lente. Pero **cada empalme es una oportunidad de que deje de ser
plano**, y un patrón chico perfectamente plano calibra mejor que uno grande
ondulado: la calibración supone que el patrón es un plano perfecto y cada
ondulación la interpreta como distorsión del lente.

Por eso el valor por defecto es el que consigue 350 mm de ancho con un solo
empalme, y el de una hoja queda como alternativa segura.

El PDF se escribe con biblioteca estándar —no hay ninguna librería de PDF
instalada y agregarla iría contra la regla de dependencias— y lleva impresa una
**regla de verificación de 100 mm**, más una página entera de instrucciones de
impresión y armado.

Esa regla no es un adorno: si la hoja se imprime al 97 % —que es lo que hace
"ajustar a la página" sin avisar—, la calibración queda escalada **en silencio**,
porque el patrón sigue siendo coherente consigo mismo y el error de reproyección
sale bajo igual.

### `calibrar_camara.py`

Mide la distorsión del lente y la deja guardada como perfil de cámara.

```bash
python -m vision.tools.calibrar_camara --camara "Logitech C270"   # capturar y calibrar
python -m vision.tools.calibrar_camara --verificar                # ver el antes y después
```

**`--camara NOMBRE` es lo que decide a qué archivo va el perfil.** La distorsión
es del aparato, no del sistema: cada cámara tiene el suyo en
`vision/calibraciones/`, y el nombre que se pase acá es el que lo bautiza
(`"Logitech C270"` → `logitech_c270.json`). Si se omite, la herramienta lo
pregunta. Sin esto, calibrar una segunda cámara pisaría el perfil de la primera.
El detalle de cómo se elige después está en
[`../geometry/README.md`](../geometry/README.md).

**Captura guiada, no "sacá 15 fotos".** Lleva la cuenta de **zonas del cuadro,
distancias e inclinaciones**, y captura sola cuando el patrón está quieto y
aporta algo que falta. La razón está medida: 8 vistas todas de frente dan un
error de 0,14 px —que parece excelente— pero recuperan la distancia focal con un
**20 % de desvío**. El número no delata la falta de variedad; el contador sí.

**Semáforo del error de reproyección**, con qué hacer en cada caso:

| Error | Veredicto |
|---|---|
| < 0,3 px | excelente, usar tal cual |
| < 0,5 px | cumple el objetivo |
| < 1,0 px | usable, conviene repetir |
| ≥ 1,0 px | no confiable, **no se guarda** salvo `--guardar-igual` |

**Verificación con los ojos** (`--verificar`): video en vivo lado a lado, crudo
contra corregido, con una rejilla de líneas perfectamente rectas superpuesta en
ambos. Apuntando al tablero, lo que se ve curvado a la izquierda tiene que verse
recto a la derecha. Cuando el patrón está a la vista agrega el número: *"curvatura
de las filas: 4,89 px → 0,001 px"*.

Esa comprobación visual existe porque el error de reproyección **puede mentir**:
con el patrón mal impreso el ajuste es coherente consigo mismo y el número sale
bajo igual. Mirar algo que uno sabe que es recto comprueba lo que el número no.

Cuando el perfil cargado **no le corresponde** a la cámara conectada, avisa en
pantalla. Ver [`../geometry/README.md`](../geometry/README.md).

### `precision_ubicacion.py`

Responde con un número la pregunta que decide la compra: **¿esta cámara ubica
los objetos con error aceptable?**

```bash
python -m vision.tools.precision_ubicacion --camara "Logitech C270"
python -m vision.tools.precision_ubicacion --comparar       # tabla de cámaras medidas
```

**Criterio: error máximo por debajo de 1 cm** en toda la cancha. No es
arbitrario: un cubo mide 6 cm, así que 1 cm de error mantiene el objetivo dentro
del cubo.

**Mide una DISTANCIA, no una posición.** Se apoya el marcador de prueba en un
punto A, se lo corre un número exacto de cuadros y se lo captura en B. Dos
motivos, y el segundo es el decisivo:

1. Medir una posición absoluta exigiría ubicar el origen —el centro del marcador
   ID 0— con precisión, y eso reintroduce el error manual que se quiere evitar.
   Un desplazamiento no necesita saber dónde está el origen: se cancela al restar.
2. **Neutraliza el paralaje por construcción.** Un objeto de altura `h` a
   distancia `d` del punto bajo la cámara se ve corrido a `d · H/(H−h)`: una
   multiplicación alrededor de ese punto. Las dos posiciones se escalan por el
   **mismo** factor, así que al restarlas el paralaje queda como un **error de
   escala puro**, calculable y descontable, en vez de un corrimiento que varía
   con la posición y sería inseparable del error de la cámara.

> Por eso esta prueba se salva de necesitar la corrección de paralaje. El
> sistema real **sí la necesita**, porque publica posiciones absolutas.

**La cuadrícula del tablero es la regla.** Cada cuadro mide exactamente 20 mm, así
que contar cuadros da una distancia exacta, sin lectura que interpretar. El único
error humano que queda es alinear el marcador a las líneas.

**Se mide sobre puntos internos**, nunca sobre los marcadores de esquina: esos
son los que el sistema usa para definir sus coordenadas, así que medir ahí sería
corregir con las propias respuestas —darían cero por construcción y no probarían
nada—. Recorre **cinco zonas** (centro y las cuatro esquinas de la cancha útil),
en horizontal y vertical.

Todo lo demás sale de `config_vision.json`, sección `precision`: el umbral, el ID
y tamaño del marcador de prueba, cuántos cuadros mover, cuántas muestras
promediar por punto, la altura de la cámara y el margen mínimo a los marcadores.

**El marcador de prueba** se imprime con
`patron_calibracion --marcador-prueba 20`, y va apoyado **plano** sobre el
tablero. Su altura entra en la configuración (`altura_marcador_mm`) porque de
ella sale el factor de paralaje que se descuenta.

#### `--comparar`: una fila por cámara

```
  cámara                 resolución    err. máx   err. med     ruido  veredicto
  ArgomTech CAM40        1920x1080      1.58 mm    0.75 mm   0.16 mm  SIRVE
  Logitech C270          1280x720       1.01 mm    0.47 mm   0.17 mm  SIRVE
```

Muestra la **última medición válida** de cada cámara, **no la mejor**: quedarse
con la mejor escondería una cámara que falla seguido. Las anteriores no se
borran; se ven con `--historial`.

Cada sesión guarda en `vision/mediciones/` **con qué cancha se midió**. Eso
permite marcar una sesión como obsoleta **por causa y no por antigüedad**: si
mañana se remonta la cancha con otras medidas, las mediciones viejas quedan
marcadas solas, sin depender de que alguien recuerde cuándo fue el cambio. Una
sesión sin ese dato dice *"cancha no registrada"* y **sigue contando**: no saber
con qué cancha se midió no es lo mismo que saber que está mal.

**Resultado sobre hardware real:** las dos cámaras medidas quedan muy por debajo
del criterio de 10 mm, así que la elección se puede hacer por disponibilidad y
precio y no por precisión.

### `panel.py`

El panel de información que las herramientas dibujan sobre el video. No es una
herramienta en sí: lo usan `diagnostico_camara`, `calibrar_camara` y
`precision_ubicacion`.

**Existe por los acentos.** `cv2.putText` usa las fuentes Hershey, que son ASCII
puro: escriben "exposición" como "exposici??n" **sin avisar**. El camino nativo
sería `cv2.freetype`, que no viene compilado en la rueda de
`opencv-contrib-python`. Por eso el panel dibuja con **Pillow**, que sí tiene
fuentes TrueType del sistema.

**Pillow es opcional.** Si no está instalado, el panel cae a `cv2.putText`
transliterando los acentos: se lee peor, pero la herramienta no se rompe.

Otras dos cosas que resuelve:

- **La tipografía se carga una vez** (`Tipografia`). El panel se dibuja en cada
  cuadro; abrir la fuente cada vez costaría más que dibujar y el visor perdería
  cuadros.
- **Se escala con la resolución** (`escala_para`). Un panel pensado para 1080p es
  ilegible a 480p y ridículo a 4K.

El estado se comunica **por color antes que por texto** —verde bien, rojo
problema, ámbar no se pudo determinar—: en una herramienta que se mira de reojo
mientras uno mueve la cámara, el color se lee de un vistazo y la palabra
después.

> La paleta de `panel.py` va en **RGB** (es lo que espera Pillow); lo que se
> dibuja con OpenCV directamente sobre el video va en **BGR**. Son espacios
> distintos y mezclarlos pinta los avisos de un color equivocado.

## Lo que todavía NO existe

Planificado, sin código aún:

- **Guía de alineamiento.** Ayudar a colocar la cámara en la posición correcta
  sobre la cancha, indicando en vivo qué corregir.
- **Monitor en vivo.** Ver el estado del mundo sobre la imagen de la cámara en
  tiempo real, para la puesta a punto antes de una ronda.
