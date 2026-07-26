# vision/

Sistema de visión completo del Vision-Rover-Challenge. Una **cámara cenital**
observa la cancha (~1 m × 1 m) y publica varias veces por segundo, por
**TCP/NDJSON**, la posición de cada robot, cada cubo y cada obstáculo, como
telemetría que los equipos consumen.

Este paquete puede depender de `contrato/`, pero **`contrato/` nunca depende de
`vision/`** (ver `CLAUDE.md`, sección 4).

## Piso de versión de Python: 3.10+ acá, 3.9+ en el contrato

| Paquete | Piso | Quién lo corre |
|---|---|---|
| `vision/` | **Python 3.10+** | Nosotros, en la máquina de competencia y las estaciones de calibración |
| `contrato/` | **Python 3.9+** | Los veinte equipos, en sus propias máquinas |

La diferencia es deliberada. Acá se puede usar sintaxis moderna sin reparos
(`slots=True` en dataclasses, `match`, etc.) porque el entorno lo controlamos
nosotros. En `contrato/` no: el Python de fábrica de macOS es 3.9, y subir ese
piso dejaría afuera a equipos por una mejora cosmética.

Entorno de desarrollo: `vision-system/.venv` (Python 3.12), creado con
`python3.12 -m venv .venv` e instalado con `pip install -r vision/requirements.txt`.

## Flujo: productores → interfaz → consumidores

El sistema tiene un flujo **en una sola dirección** (ver `CLAUDE.md`, sección 3):

```
PRODUCTORES                        INTERFAZ              CONSUMIDORES
sources → geometry → detectors     estado del mundo      publish
                   → tracking      (inmutable)           record
```

- **Productores** generan un **"estado del mundo"** a partir de la cámara.
- La **interfaz** es ese estado del mundo, **inmutable**: lo único que cruza
  entre productores y consumidores. No se muta en el lugar; se produce uno nuevo.
- **Consumidores** solo **leen** el estado del mundo.

**Relojes desacoplados:** el procesamiento corre a la velocidad de la cámara; la
publicación corre por temporizador. Uno nunca bloquea al otro.

**Falla abierto:** ante cualquier excepción se conserva el último estado bueno y
se sigue publicando; el sistema no se cae a mitad de ronda.

## Estructura interna

| Paquete       | Lado        | Rol |
|---------------|-------------|-----|
| `sources/`    | Productor   | Captura de la cámara (webcam USB, ajustes fijos). |
| `geometry/`   | Productor   | Coordenadas ArUco, calibración de distorsión y corrección de paralaje. |
| `detectors/`  | Productor   | Detección de rovers, cubos y obstáculos. |
| `tracking/`   | Productor   | Seguimiento e identidad; oclusión y edad. |
| `publish/`    | Consumidor  | Publicación TCP/NDJSON (último valor gana). |
| `record/`     | Consumidor  | Grabación del estado del mundo. |
| `tools/`      | Herramientas | Utilidades visuales nativas (calibración, monitor), fuera de Docker. |

## Dependencias

Ver `requirements.txt`. Se usan `opencv-contrib-python`, `numpy` y `pyyaml` con
versiones fijadas y alineadas a la generación NumPy 1.x por estabilidad.
