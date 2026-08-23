# vision/

Sistema de visión completo del Vision-Rover-Challenge. Una **cámara cenital**
observa la cancha (~1 m × 1 m) y publica varias veces por segundo, por
**TCP/NDJSON**, la posición de cada robot, cada cubo y cada obstáculo, como
telemetría que los equipos consumen.

Este paquete puede depender de `contrato/`, pero **`contrato/` nunca depende de
`vision/`** (ver `CLAUDE.md`, sección 4).

## Piso de versión de Python: 3.10+ acá, 3.9+ en el contrato

| Paquete | Piso | Quién pone el intérprete |
|---|---|---|
| `vision/` | **Python 3.10+** | El **instalador**, que trae su propio Python embebido |
| `contrato/` | **Python 3.9+** | **Cada equipo**, con el Python que ya tenga instalado |

La diferencia es deliberada, y la explica **quién pone el intérprete**.

`vision/` se instala siempre de la misma forma —nativo, con un instalador que
trae su propio Python—, así que la versión **no depende de la máquina donde se
instale**. Por eso acá se puede usar sintaxis moderna sin reparos (`slots=True`
en dataclasses, `match`, etc.).

`contrato/` se entrega **suelto, sin instalador**: cada equipo lo corre con el
Python que ya tiene, y el de fábrica de macOS es 3.9. Subir ese piso dejaría
afuera a equipos por una mejora cosmética.

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
| `config_vision.json` | **Toda** la configuración, como datos: tablero, disposición de marcadores, generador sintético, cámara, calibración y prueba de precisión. Nada incrustado en el código. |
| `requirements.txt` | Las tres dependencias, con versión fijada. |

Y dos carpetas de **datos medidos**, que no son código ni configuración del
sistema sino el resultado de medir aparatos concretos:

| Carpeta | Qué guarda |
|---|---|
| `calibraciones/` | Un **perfil por cámara** con su distorsión de lente. Ver [`geometry/`](geometry/README.md). |
| `mediciones/` | Una sesión por cada prueba de **precisión de ubicación**. Ver [`tools/`](tools/README.md). |

Dos módulos sueltos que no son de ningún lado, y siete subpaquetes:

| Módulo | Qué es |
|---|---|
| `sistema.py` | **El programa.** Encadena todo y se enciende. Elige la fuente, corre el bucle, falla abierto y arbitra las fases |
| `mundo.py` | **La frontera.** El estado del mundo, inmutable: lo único que cruza de productores a consumidores. No es de ninguno de los dos lados, y por eso no vive dentro de ninguno |

La columna de estado dice qué hay **hoy**, no qué va a haber; cada carpeta tiene
su propio README con el detalle:

| Paquete | Lado | Rol | Estado |
|---|---|---|---|
| `sources/` | Productor | De dónde salen las imágenes | 🟢 **cámara USB real** y **generador sintético con cámara estenopeica**, intercambiables |
| `geometry/` | Productor | Píxeles → celdas | 🟢 **coordenadas ArUco**, **corrección de distorsión**, **pose de cámara**, **paralaje** y **degradación con 3 marcadores** |
| `detectors/` | Productor | Qué hay y dónde | 🟢 **rovers** por marcador y **cubos** por color |
| `tracking/` | Productor | Identidad, oclusión y edad | 🟢 **memoria entre cuadros** |
| `publish/` | Consumidor | Publicación TCP/NDJSON | 🟢 **reloj propio y último-valor-gana** (el transporte lo comparte con el contrato) |
| `record/` | Consumidor | Grabación a disco | ⚪ vacío |
| `tools/` | Herramientas | Puesta a punto y verificación | 🟢 **nueve herramientas** · ⚪ alineamiento y monitor en vivo |

🟢 hay código funcionando · ⚪ planificado, sin código aún

### Lo que mide el sistema, hoy

Todo contra la **verdad conocida** del generador sintético, con la cámara
inclinada, y contra un criterio de aceptación de **10 mm**:

| Etapa | Error |
|---|---|
| Píxeles → celdas | 0,52 mm |
| Paralaje del rover | 41 mm sin corregir → **0,9 mm** corregido |
| Rovers | 1,03 mm · 1,2° |
| Cubos | 1,05 mm · **4,88 mm** con un rover empujándolos |

## Cómo correr lo que existe hoy

Desde `vision-system/`, con el entorno virtual ya creado (ver el
[README general](../README.md), sección 8).

### El sistema completo

```bash
.venv/bin/python -m vision.sistema                # con la cámara real
.venv/bin/python -m vision.sistema --sintetico    # sin cámara, con imágenes generadas
```

Sin argumentos abre la **cámara**. Lo sintético hay que pedirlo, y el sistema lo
avisa en pantalla todo el tiempo. Mientras corre se le escribe `ready`, `start`,
`stop` o `quit`.

### Las verificaciones y las herramientas

```bash
# Las cuatro verificaciones contra verdad conocida. Todas corren SIN cámara y
# devuelven código distinto de cero si algo se sale de umbral.
.venv/bin/python -m vision.tools.verificar_geometria      # píxeles → celdas
.venv/bin/python -m vision.tools.verificar_rovers         # posición y ángulo
.venv/bin/python -m vision.tools.verificar_cubos          # color, base y oclusión
.venv/bin/python -m vision.tools.verificar_seguimiento    # memoria, oclusión y edad

# Los desfases marcador ↔ robot, medidos con el propio sistema.
.venv/bin/python -m vision.tools.medir_desfases --autoprueba   # verifica la matemática
.venv/bin/python -m vision.tools.medir_desfases                # con el robot real

# Verifica el sistema de coordenadas contra la verdad del generador sintético.
# Corre en dos modos: con cámara cenital perfecta y con la cámara inclinada.
.venv/bin/python -m vision.tools.verificar_geometria

# Lo mismo, guardando la imagen generada con lo detectado dibujado encima.
.venv/bin/python -m vision.tools.verificar_geometria --salida /tmp/tablero.png --anotar

# Diagnóstico de la cámara real: fps, ajustes y marcadores de esquina en vivo.
.venv/bin/python -m vision.tools.diagnostico_camara
.venv/bin/python -m vision.tools.diagnostico_camara --listar     # ¿qué cámaras hay?

# Calibración de la distorsión del lente. El nombre de --camara define a qué
# perfil va: cada cámara guarda el suyo en calibraciones/.
.venv/bin/python -m vision.tools.patron_calibracion --salida patron.pdf   # imprimir esto
.venv/bin/python -m vision.tools.calibrar_camara --camara "Logitech C270" # capturar y calibrar
.venv/bin/python -m vision.tools.calibrar_camara --verificar              # antes y después

# ¿Esta cámara ubica con error aceptable? Se mide sobre el tablero real.
.venv/bin/python -m vision.tools.patron_calibracion --marcador-prueba 20  # imprimir esto
.venv/bin/python -m vision.tools.precision_ubicacion --camara "Logitech C270"
.venv/bin/python -m vision.tools.precision_ubicacion --comparar           # tabla de cámaras
```

El sistema publica telemetría real en el puerto 2026, el mismo del simulador de
[`../contrato/`](../contrato/README.md). Para mirarla, `test_client.py` del
contrato sirve igual contra los dos — que es exactamente lo que el contrato les
promete a los equipos.

## Dependencias

Ver `requirements.txt`. Son **tres**:

| Dependencia | Para qué | ¿Obligatoria? |
|---|---|---|
| `opencv-contrib-python==4.9.0.80` | Cámara, ArUco, calibración, homografías | Sí |
| `numpy==1.26.4` | Aritmética de imágenes y matrices | Sí |
| `pillow==12.3.0` | **Solo** dibujar texto en español sobre el video de las herramientas visuales | **No**: es opcional en el código |

Las versiones están fijadas y alineadas a la generación **NumPy 1.x** por
estabilidad de ABI: OpenCV 4.9.0.80 se compiló contra NumPy 1.x.

**Por qué Pillow.** `cv2.putText` usa las fuentes Hershey, que son ASCII puro:
escriben "exposición" como "exposici??n" sin avisar. El camino nativo sería
`cv2.freetype`, que no viene compilado en la rueda de `opencv-contrib-python`.
Está tratada como **opcional**: si falta, el panel cae a `cv2.putText`
transliterando los acentos —se ve peor, pero la herramienta no se rompe—.

> El paquete `contrato/`, que es lo que se entrega a los equipos, **sigue sin
> ninguna dependencia**. Pillow es solo del lado de visión.

La configuración se lee con el módulo `json` de la biblioteca estándar, así que
no hace falta ninguna biblioteca de YAML.
