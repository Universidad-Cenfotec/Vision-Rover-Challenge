# tools/

**Herramientas visuales.** Utilidades nativas que corren **fuera de Docker** y
apoyan la puesta a punto. No forman parte del flujo de publicación: nada de lo
que hay acá se ejecuta durante una ronda.

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

## Lo que todavía NO existe

Planificado, sin código aún:

- **Calibración de cámara.** Capturar el patrón de calibración y calcular los
  coeficientes de distorsión del lente gran angular, que después usa `geometry/`.
- **Monitor en vivo.** Ver el estado del mundo sobre la imagen de la cámara en
  tiempo real, para la puesta a punto antes de una ronda.
