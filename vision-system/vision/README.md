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

En la raíz del paquete:

| Archivo | Qué es |
|---|---|
| `configuracion.py` | Carga `config_vision.json` a estructuras inmutables y lo valida antes de usarlo. |
| `config_vision.json` | **Toda** la configuración, como datos: tablero, disposición de marcadores, parámetros del generador. Nada incrustado en el código. |
| `requirements.txt` | Las dos dependencias, con versión fijada. |

Y los siete subpaquetes. La columna de estado dice qué hay **hoy**, no qué va a
haber; cada carpeta tiene su propio README con el detalle:

| Paquete | Lado | Rol | Estado |
|---|---|---|---|
| `sources/` | Productor | De dónde salen las imágenes | 🟢 **generador sintético** con verdad conocida · ⚪ captura de webcam |
| `geometry/` | Productor | Píxeles → celdas | 🟢 **coordenadas ArUco** verificadas · ⚪ distorsión y paralaje |
| `detectors/` | Productor | Qué hay y dónde | ⚪ vacío |
| `tracking/` | Productor | Identidad, oclusión y edad | ⚪ vacío |
| `publish/` | Consumidor | Publicación TCP/NDJSON | ⚪ vacío (el comportamiento ya está probado en el simulador del contrato) |
| `record/` | Consumidor | Grabación a disco | ⚪ vacío |
| `tools/` | Herramientas | Puesta a punto, fuera de Docker | 🟢 **verificación de geometría** · ⚪ calibración y monitor |

🟢 hay código funcionando · ⚪ planificado, sin código aún

## Cómo correr lo que existe hoy

Desde `vision-system/`, con el entorno virtual ya creado (ver el
[README general](../README.md), sección 8):

```bash
# Verifica el sistema de coordenadas contra la verdad del generador sintético.
# Corre en dos modos: con cámara cenital perfecta y con la cámara inclinada.
.venv/bin/python -m vision.tools.verificar_geometria

# Lo mismo, guardando la imagen generada con lo detectado dibujado encima.
.venv/bin/python -m vision.tools.verificar_geometria --salida /tmp/tablero.png --anotar
```

Todavía no hay nada que capture de una cámara real ni que publique telemetría:
para eso, hoy se usa el simulador de [`../contrato/`](../contrato/README.md).

## Dependencias

Ver `requirements.txt`. Solo dos: `opencv-contrib-python` y `numpy`, con
versiones fijadas y alineadas a la generación NumPy 1.x por estabilidad.

La configuración se lee con el módulo `json` de la biblioteca estándar, así que
no hace falta ninguna biblioteca de YAML.
