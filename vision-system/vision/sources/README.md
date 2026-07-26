# sources/

**Productor.** De acá salen las imágenes que procesa el resto del sistema. Es el
primer eslabón: nada entra al sistema sin pasar por esta carpeta.

## Lo que ya existe

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

> **Ojo, no confundir con el simulador de `contrato/`.** Aquel emite *posiciones
> en JSON* por la red, para que los equipos prueben su rover. Este dibuja
> *imágenes*, para que el sistema de visión tenga qué procesar. Uno se consume
> por TCP; el otro entra por el lado de la cámara.

## Lo que todavía NO existe

Planificado, sin código aún:

- **Captura de la webcam USB.** Leer cuadros de la cámara real con **exposición,
  enfoque y balance de blancos fijos** —nunca en automático, porque un ajuste que
  se mueve solo cambia los colores a mitad de ronda y rompe la detección— y
  sellar cada cuadro con su **instante de captura**, que después viaja con el
  mensaje para que los equipos puedan medir latencia.
