# tools/

**Herramientas visuales.** Utilidades que apoyan la puesta a punto. No forman
parte del flujo de publicación: nada de lo que hay acá se ejecuta durante una
ronda.

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
```

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
python -m vision.tools.calibrar_camara              # capturar y calibrar
python -m vision.tools.calibrar_camara --verificar  # ver el antes y después
```

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

## Lo que todavía NO existe

Planificado, sin código aún:

- **Guía de alineamiento.** Ayudar a colocar la cámara en la posición correcta
  sobre la cancha, indicando en vivo qué corregir.
- **Monitor en vivo.** Ver el estado del mundo sobre la imagen de la cámara en
  tiempo real, para la puesta a punto antes de una ronda.
