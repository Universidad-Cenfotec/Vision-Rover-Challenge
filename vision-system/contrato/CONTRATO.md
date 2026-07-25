# Contrato de telemetría — Vision-Rover-Challenge

**Protocolo v1**

Este documento es el acuerdo entre el **sistema de visión** y **los equipos**.
La visión mira la cancha desde arriba y publica, varias veces por segundo, dónde
está cada cosa. Ustedes lo consumen.

Lo que está acá **no cambia por sorpresa**. Si algo tiene que cambiar, sube el
número de versión (`v`) y se les avisa. Pueden escribir código contra este
formato con confianza.

---

## 1. Cómo se conectan

| | |
|---|---|
| **Transporte** | TCP |
| **Puerto** | `2026` |
| **Formato** | NDJSON — **un objeto JSON por línea**, terminada en `\n` |
| **Codificación** | UTF-8 (en la práctica, ASCII) |
| **Dirección** | Solo la visión escribe. Ustedes **nunca envían nada**. |

Se conectan, leen líneas y listo. No hay handshake, ni suscripción, ni comandos.

### El error clásico: TCP no respeta los límites de los mensajes

Un `recv()` puede devolverles **media línea**, o **dos líneas y media**. Si
parsean directo lo que llegó, les va a funcionar en la compu y les va a fallar
en la cancha.

**Hay que acumular en un buffer y cortar por `\n`:**

```python
buffer = b""
while True:
    trozo = conexion.recv(4096)
    if not trozo:
        break                      # la visión cerró la conexión
    buffer += trozo
    while b"\n" in buffer:
        linea, buffer = buffer.split(b"\n", 1)
        mensaje = json.loads(linea)
        # ... usar mensaje ...
```

Está implementado así en [`test_client.py`](test_client.py), listo para copiar.

### Si la conexión se cae

Reconecten. La visión acepta clientes en cualquier momento y les manda el estado
actual: **no hay que ponerse al día con nada**, porque no existe historial. El
primer mensaje que reciben ya es el presente.

---

## 2. El mensaje

Ejemplo real, formateado para leerlo (en el cable viaja **todo en una sola
línea**):

```json
{
  "v": 1,
  "seq": 4137,
  "ts_ms": 1785012345678,
  "phase": "RUNNING",
  "grid": { "cols": 50, "rows": 50, "cell_mm": 20.0 },
  "rovers": [
    { "id": 10, "col": 4.302,  "row": 3.705,  "theta": 46.20, "age_ms": 0 },
    { "id": 11, "col": 18.265, "row": 33.661, "theta": 40.22, "age_ms": 0 }
  ],
  "cubes": [
    { "color": "green", "col": 29.968, "row": 11.999, "age_ms": 0   },
    { "color": "blue",  "col": 18.000, "row": 34.000, "age_ms": 425 },
    { "color": "red",   "col": 38.071, "row": 29.983, "age_ms": 0   }
  ],
  "obstacles": [
    { "col": 24.968, "row": 25.011, "age_ms": 0 },
    { "col": 12.014, "row": 19.952, "age_ms": 0 },
    { "col": 35.946, "row": 17.951, "age_ms": 0 }
  ],
  "start":  { "col": 2.5, "row": 2.5 },
  "depots": [
    { "color": "green", "col": 47.5, "row": 2.5  },
    { "color": "blue",  "col": 2.5,  "row": 47.5 },
    { "color": "red",   "col": 47.5, "row": 47.5 }
  ]
}
```

> Mirá el cubo **azul**: `age_ms: 425`. El rover 11 está justo encima
> (`18.265, 33.661`) y lo tapa. El cubo **no desapareció** de la lista: sigue
> ahí, con su última posición conocida y la edad creciendo. Esto es lo normal,
> no un error. Ver la sección 6.

---

## 3. Campo por campo

### Nivel raíz

| Campo | Tipo | Significado |
|---|---|---|
| `v` | entero | Versión del protocolo. Hoy `1`. **Si ven un número que no conocen, descarten el mensaje**: el formato cambió. |
| `seq` | entero | Número de secuencia, sube de a uno por mensaje publicado. Sirve para detectar pérdidas. |
| `ts_ms` | entero | Instante de **captura del cuadro**, en milisegundos desde época (Unix). **No** es el instante de envío. |
| `phase` | texto | `IDLE`, `READY`, `RUNNING` o `FINISHED`. Ver sección 5. |
| `grid` | objeto | Dimensiones de la cancha. |
| `rovers` | lista | Robots detectados. **Dinámico.** |
| `cubes` | lista | Cubos detectados. **Dinámico.** |
| `obstacles` | lista | Obstáculos detectados. **Dinámico.** |
| `start` | objeto | Esquina de salida. **Estático.** |
| `depots` | lista | Zonas de acopio. **Estático.** |

### `grid`

| Campo | Tipo | Significado |
|---|---|---|
| `cols` | entero | Ancho de la cancha, en celdas. |
| `rows` | entero | Alto de la cancha, en celdas. |
| `cell_mm` | float | Lado de una celda en milímetros. Vale `20.0`. |

**Lean `grid` del mensaje, no lo hardcodeen.** La cancha efectiva es el área
encerrada por los cuatro marcadores ArUco de esquina, y depende de dónde se
peguen los marcadores el día del montaje. Puede no ser exactamente 50×50.

### `rovers[]`

| Campo | Tipo | Significado |
|---|---|---|
| `id` | entero | **ID del marcador ArUco** pegado al robot. Es su identidad. |
| `col` | float | Posición en celdas, eje horizontal. |
| `row` | float | Posición en celdas, eje vertical. |
| `theta` | float | Orientación en **grados**, `0` = derecha, sentido **antihorario**, rango `[0, 360]`. |
| `age_ms` | entero | Milisegundos desde la última vez que se lo vio de verdad. |

Los dos robots son **negros e idénticos**: lo único que los distingue es el
marcador. **Su rover es el del ID de su marcador.** Búsquenlo por `id`, nunca
por posición en la lista.

### `cubes[]`

| Campo | Tipo | Significado |
|---|---|---|
| `color` | texto | `green`, `blue` o `red`. **El color es la identidad.** |
| `col` | float | Posición en celdas. |
| `row` | float | Posición en celdas. |
| `age_ms` | entero | Milisegundos desde la última observación real. |

Cubos de **6 cm**. **No hay dos del mismo color**, por eso no llevan `id`: el
color alcanza para identificarlos. Puede haber 2 o 3 cubos en juego.

### `obstacles[]`

| Campo | Tipo | Significado |
|---|---|---|
| `col` | float | Posición en celdas. |
| `row` | float | Posición en celdas. |
| `age_ms` | entero | Milisegundos desde la última observación real. |

Bloques **amarillos de 10 cm**. No llevan `color` porque **el amarillo está
reservado**: un objeto amarillo **nunca** es un cubo. No llevan `id` porque son
intercambiables entre sí; lo único que importa es esquivarlos.

### `start`

| Campo | Tipo | Significado |
|---|---|---|
| `col` | float | Posición en celdas. |
| `row` | float | Posición en celdas. |

Esquina de salida de los robots. Coincide con el **origen (0,0)**, que es el
marcador ArUco de **menor ID (el 0)**.

### `depots[]`

| Campo | Tipo | Significado |
|---|---|---|
| `color` | texto | `green`, `blue` o `red`. |
| `col` | float | Posición en celdas. |
| `row` | float | Posición en celdas. |

Zonas de acopio, **una por color**, en las tres esquinas que no son la de
salida. **Cada cubo va al depot de su color.** Se cruzan las dos listas por
`color`:

```python
depots_por_color = {d["color"]: d for d in msg["depots"]}
for cubo in msg["cubes"]:
    destino = depots_por_color[cubo["color"]]
```

**No asuman qué color va en qué esquina.** Eso se define al montar la cancha y
puede cambiar. Léanlo del mensaje.

### ¿Por qué `start` y `depots` no tienen `age_ms`?

Porque no se detectan: **se declaran**. Son lugares fijos que siempre están y
nunca se ocluyen. Los cubos, en cambio, se mueven, se tapan y envejecen. Por eso
van en listas separadas aunque compartan el color.

---

## 4. Sistema de coordenadas

```
      col ──────────────────────────────────►
  (0,0) ┌───────────────────────────────────┐
   │    │  ▣ start / origen                 │  ▣ = marcador ArUco de esquina
   │    │  (marcador ID 0)                  │
  row   │                                   │
   │    │            ■ obstáculo            │
   │    │                                   │
   ▼    │       ▪ cubo                      │
        │                                   │
        └───────────────────────────────────┘
                                        (cols, rows)
```

- **Origen (0,0)** = marcador ArUco de **menor ID (el 0)** = **esquina de salida**.
- **`col` crece hacia la derecha.**
- **`row` crece hacia abajo.**
- **Unidad: celdas con decimales.** Una celda = **20 mm**.
  `col = 12.35` significa 247 mm desde el origen. Para pasar a milímetros:
  `mm = celdas * grid["cell_mm"]`.
- **`theta` en grados**, `0` = hacia la derecha (`col` creciente), sentido
  **antihorario**, rango `[0, 360]`.

Ojo con el ángulo: como `row` crece hacia **abajo**, un `theta` de 90° apunta
hacia **arriba** en la pantalla (`row` decreciente). El vector unitario de avance
es:

```python
dcol = math.cos(math.radians(theta))
drow = -math.sin(math.radians(theta))   # el signo menos es porque row va hacia abajo
```

### Nunca redondeen a entero

Las posiciones vienen con decimales **a propósito**. Un cubo en `col = 12.4` no
está "en la celda 12": está a 248 mm del origen. Redondear tira 10 mm de
precisión, que es la mitad de una celda. Trabajen en float.

### Puede haber valores apenas fuera de la grilla

La visión corrige el **paralaje** (los objetos altos se ven corridos hacia
afuera desde el centro de la cámara). Después de corregir, un objeto pegado al
borde puede quedar en `col = -0.3`. Es un dato **válido**, no un error. Si
necesitan acotarlo, acótenlo ustedes.

---

## 5. Fases

**La visión es árbitro.** Ella dice en qué fase está la ronda, y los rovers
obedecen.

| Fase | Qué significa | Qué hace su rover |
|---|---|---|
| `IDLE` | Sistema encendido, ronda no preparada. | Quieto. |
| `READY` | Cancha lista, robots en la salida. Está por empezar. | Quieto. Pueden leer telemetría y planificar. |
| `RUNNING` | **Ronda en juego.** | Se mueve. |
| `FINISHED` | Ronda terminada. | **Frenar de inmediato.** |

Transiciones normales: `IDLE → READY → RUNNING → FINISHED`, y `FINISHED → READY`
para la ronda siguiente.

**En `RUNNING` se juega, en todo lo demás se está quieto.** Un rover que se
mueve fuera de `RUNNING` está infringiendo.

La visión **sigue publicando en todas las fases**, incluso en `IDLE`. Que llegue
telemetría no significa que la ronda esté corriendo: hay que mirar `phase`.

---

## 6. Reglas de consumo

Estas cinco reglas son la diferencia entre un cliente que anda en la cancha y
uno que anda solo en la compu.

### 6.1. Iterar, nunca indexar por posición fija

**Mal:**

```python
mi_rover = msg["rovers"][0]        # ¿y si esta vez sos vos el [1]?
cubo_verde = msg["cubes"][0]       # ¿y si el verde está ocluido... o el orden cambió?
```

**Bien:**

```python
mi_rover = None
for r in msg["rovers"]:
    if r["id"] == MI_ID_ARUCO:
        mi_rover = r
        break

cubo_verde = next((c for c in msg["cubes"] if c["color"] == "green"), None)
```

La cantidad de objetos **cambia entre mensajes** y el orden **no está
garantizado**. Busquen siempre por identidad: `id` para rovers, `color` para
cubos y depots. Y manejen el caso de que **no esté**: `mi_rover` puede ser
`None`.

### 6.2. `age_ms` alto significa oclusión, no desaparición

Cuando algo se tapa —un rover encima de un cubo, un reflejo sobre un marcador—
la visión **no lo saca de la lista**. Lo mantiene con su **última posición
conocida** y **`age_ms` creciendo**.

Esto es deliberado: un objeto que parpadea entre existir y no existir vuelve
loco al consumidor. Es preferible un dato viejo y marcado como viejo, que un
agujero.

**Cómo se usa:**

```python
if cubo["age_ms"] < 200:
    pass    # dato fresco, se puede navegar hacia ahí
elif cubo["age_ms"] < 1500:
    pass    # probablemente tapado por un rover; sigue estando ahí, con menos certeza
else:
    pass    # muy viejo: acercarse con cuidado y volver a mirar
```

Elijan sus umbrales, pero **elíjanlos**. Tratar un dato de 3 segundos igual que
uno de 20 ms es la forma más rápida de chocar.

Y al revés: **que un cubo tenga `age_ms` alto no quiere decir que se lo llevaron**.
Quiere decir que la visión no lo ve. Casi siempre sigue justo donde dice.

### 6.3. Quédense con el último mensaje

La visión publica con la política **"el último valor gana"**: hay un buffer de
**un solo mensaje por cliente**, y si ustedes no lo drenan a tiempo, **se pisa**.
Nunca se les va a encolar telemetría vieja.

Esto significa que **los saltos en `seq` son normales**. Si ven `seq` 100, 101,
104, se perdieron dos: ustedes estaban ocupados. No hay nada que recuperar,
porque no hay nada que valga la pena recuperar — dónde estaba su rover hace
150 ms no le sirve a nadie.

**Lo que sí importa:** si `seq` salta **mucho**, su bucle es demasiado lento.
Midan los saltos y usen ese número para calibrar. `test_client.py` los cuenta.

**No acumulen mensajes para procesarlos después.** Lean, quédense con el más
nuevo, descarten el resto.

### 6.4. No naveguen con datos viejos

Midan la latencia: **`ahora_ms - ts_ms`**. `ts_ms` es el instante de **captura**,
así que ese número es la edad real del dato desde que la cámara lo vio.

```python
latencia_ms = int(time.time() * 1000) - msg["ts_ms"]
if latencia_ms > 500:
    frenar()        # estoy manejando a ciegas
```

Si la latencia se dispara —red saturada, su bucle trabado, la visión atrasada—
lo correcto es **frenar**, no seguir con la última orden. Un rover que sigue
avanzando con datos de hace un segundo choca.

> Esto supone que el reloj del rover y el de la visión están más o menos en
> hora. Si difieren mucho, la latencia absoluta va a estar corrida; en ese caso
> miren la **variación** de la latencia, que sigue siendo útil.

### 6.5. Validen la versión

```python
if msg["v"] != 1:
    continue      # formato desconocido: descartar, no adivinar
```

Es una línea y les evita interpretar mal un mensaje del futuro.

---

## 7. Herramientas incluidas

Todo corre con **Python puro**: sin OpenCV, sin cámara, sin instalar nada.

### `schema.py` — el contrato en código

Las constantes y la validación. Si programan en Python, **importen de acá** en
vez de escribir los literales a mano:

```python
from contrato.schema import PROTOCOL_VERSION, PHASES, CUBE_COLORS, CELL_MM, validate_message

error = validate_message(msg)
if error is not None:
    print("mensaje inválido:", error)
```

`validate_message` devuelve `None` si el mensaje cumple, o un texto con el error
si no. **No lanza excepción**, para que puedan descartar un mensaje malo y
seguir andando.

### `mock_publisher.py` — el simulador

Publica telemetría sintética con **el mismo formato** que el sistema real, para
que desarrollen sin cancha:

```bash
python -m contrato.mock_publisher
```

Comandos por teclado, mientras corre: `ready`, `start`, `stop`, `quit`. Son las
transiciones de fase, para que prueben cómo reacciona su rover.

**El simulador miente feo a propósito.** Reproduce las patologías reales:

- **ruido** en posición y orientación;
- **oclusiones**: un rover que pasa sobre un cubo lo tapa, y el `age_ms` del
  cubo crece;
- **pérdidas** ocasionales de detección de un rover;
- **cubos que se mueven** cuando un rover los empuja.

Si su código anda contra el simulador, tiene chance en la cancha. Si el ruido
del simulador lo rompe, la cancha lo va a romper igual.

Todo lo configurable está en [`config_simulador.json`](config_simulador.json):
tamaño de grilla, IDs de los rovers, cuántos cubos y de qué color, posiciones de
`start` y `depots`, nivel de ruido y tasa de publicación. Editen ese archivo,
no el código, para probar otros escenarios.

### `test_client.py` — cliente de referencia

Ejemplo mínimo y funcional de consumo. Se conecta, parsea, **valida cada mensaje**
y mide latencia y saltos de secuencia:

```bash
python -m contrato.test_client --host 127.0.0.1 --port 2026
```

Úsenlo de dos formas: como **punto de partida** para su propio cliente, y como
**diagnóstico** — si no están seguros de si el problema es suyo o de la red,
corran esto al lado y comparen.

### Probar todo junto

En una terminal:

```bash
python -m contrato.mock_publisher
```

En otra:

```bash
python -m contrato.test_client
```

En la primera, escriban `ready` y después `start`.

---

## 8. Qué garantiza la visión y qué no

**Garantiza:**

- El formato de este documento, mientras `v` valga `1`.
- Que va a **seguir publicando** aunque algo falle adentro: ante un error se
  conserva el último estado bueno y se sigue emitiendo. El sistema no se cae a
  mitad de ronda.
- Que un objeto **no desaparece** de su lista por estar tapado: se queda con su
  última posición y `age_ms` creciendo.
- Que `seq` sube de a uno **por mensaje publicado** (los huecos que ustedes ven
  son mensajes que se pisaron por la política de último-valor-gana).

**No garantiza:**

- Que todos los objetos estén siempre frescos. Miren `age_ms`.
- Que las listas tengan un largo fijo, ni un orden estable. Iteren y busquen por
  identidad.
- Que las posiciones caigan siempre dentro de la grilla (corrección de paralaje).
- Una tasa de entrega exacta a cada cliente. Un cliente lento recibe menos
  mensajes, siempre los más nuevos.

---

## 9. Cambios de contrato

Este formato **es un contrato**. No cambia sin:

1. **subir `v`**, y
2. **avisarles** con tiempo.

Si algo de este documento les resulta ambiguo, **pregunten antes de asumir**.
Una ambigüedad aclarada a tiempo cuesta cinco minutos; descubierta el día de la
competencia, cuesta la ronda.
