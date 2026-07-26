"""Esquema del contrato de telemetría del Vision-Rover-Challenge.

Este módulo es la ÚNICA fuente de verdad sobre la forma del mensaje que el
sistema de visión publica por TCP/NDJSON y que los equipos consumen.

¿Por qué vive acá y no en `vision/`?
    Porque el contrato se entrega a los equipos POR SÍ SOLO. Depende únicamente
    de la biblioteca estándar de Python: nada de OpenCV, cámara ni del paquete
    `vision`. La dependencia va en un solo sentido: `vision` puede importar
    `contrato`, nunca al revés.

¿Por qué las estructuras son inmutables (`frozen=True`)?
    Porque el "estado del mundo" no se muta en el lugar: se produce uno nuevo en
    cada cuadro. Así el lado productor (cámara, detectores) y el lado consumidor
    (publicación, grabación) nunca se pisan, aunque corran en relojes distintos.

Piso de versión: Python 3.9
    El contrato corre en **3.9 en adelante**, a diferencia del sistema de visión
    (`vision/`), que exige 3.10+. La distinción es deliberada y la explica quién
    pone el intérprete: `vision/` se instala con un instalador que trae su propio
    Python embebido, así que su versión no depende de la máquina. El contrato se
    entrega suelto y sin instalador: cada equipo lo corre con el Python que ya
    tiene, y el de fábrica de macOS es 3.9. Excluir a un equipo por una mejora
    cosmética no vale la pena.

    En la práctica esto significa: NO usar `slots=True` en estas dataclasses
    (es 3.10+), ni `match`, ni nada que rompa en 3.9. Las anotaciones modernas
    (`X | None`, `dict[str, Any]`) sí se pueden, porque `from __future__ import
    annotations` hace que no se evalúen en tiempo de ejecución.

El contrato es sagrado: ningún campo cambia de nombre, unidad o semántica sin
subir `PROTOCOL_VERSION` y avisar a los equipos.
"""

# Este import NO es un resto de compatibilidad con versiones viejas: hace que
# las anotaciones no se evalúen en tiempo de definición, y es lo que permite
# escribir `-> Grid` dentro de la propia clase `Grid` sin comillas.
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

# --------------------------------------------------------------------------
# Constantes del contrato
#
# Los equipos deben importar estas constantes en vez de escribir los literales
# a mano: si algo cambia, cambia acá y con un salto de versión.
# --------------------------------------------------------------------------

#: Versión del protocolo. Sube de a uno ante CUALQUIER cambio de forma, nombre
#: de campo, unidad o semántica. Un cliente que ve una versión que no conoce
#: debe rechazar el mensaje, no adivinar.
PROTOCOL_VERSION = 1

#: Fases de la ronda. La visión es árbitro: ella dice en qué fase se está.
PHASES: tuple[str, ...] = ("IDLE", "READY", "RUNNING", "FINISHED")

#: Colores válidos de cubo. El color ES la identidad del cubo: no hay dos cubos
#: del mismo color, por eso no llevan `id`.
CUBE_COLORS: tuple[str, ...] = ("green", "blue", "red")

#: Lado de una celda en milímetros. Las posiciones se expresan en celdas con
#: decimales; multiplicar por este valor da milímetros.
CELL_MM = 20.0

#: El amarillo está RESERVADO para los obstáculos. Nunca es un cubo. Por eso los
#: obstáculos no llevan campo `color`: su color se conoce de antemano.
COLOR_RESERVADO_OBSTACULO = "yellow"

# Campos exactos de cada objeto. La validación es estricta —rechaza faltantes y
# sobrantes— porque un campo de más suele ser un typo o un productor de otra
# versión, y es mejor que falle fuerte y temprano que en medio de una ronda.
_CAMPOS_MENSAJE = frozenset(
    ("v", "seq", "ts_ms", "phase", "grid", "rovers", "cubes", "obstacles", "start", "depots")
)
_CAMPOS_GRID = frozenset(("cols", "rows", "cell_mm"))
_CAMPOS_ROVER = frozenset(("id", "col", "row", "theta", "age_ms"))
_CAMPOS_CUBE = frozenset(("color", "col", "row", "age_ms"))
_CAMPOS_OBSTACLE = frozenset(("col", "row", "age_ms"))
_CAMPOS_START = frozenset(("col", "row"))
_CAMPOS_DEPOT = frozenset(("color", "col", "row"))


# --------------------------------------------------------------------------
# Estructuras del mensaje
#
# Todas son `frozen`: representan una foto del mundo en un instante, y una foto
# no se retoca. Para "cambiar" algo se construye una foto nueva
# (`dataclasses.replace` sirve para eso).
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Grid:
    """Dimensiones de la cancha, en celdas.

    La cancha efectiva es el área encerrada por los cuatro marcadores ArUco de
    esquina, por eso `cols`/`rows` se leen del mensaje y no se asumen fijos.
    """

    cols: int
    rows: int
    cell_mm: float = CELL_MM

    def a_dict(self) -> dict[str, Any]:
        return {"cols": self.cols, "rows": self.rows, "cell_mm": self.cell_mm}

    @staticmethod
    def desde_dict(d: dict[str, Any]) -> Grid:
        return Grid(cols=d["cols"], rows=d["rows"], cell_mm=d["cell_mm"])


@dataclass(frozen=True)
class Rover:
    """Un robot. Su identidad es el ID de su marcador ArUco.

    Los dos robots son negros e idénticos: lo único que los distingue es el
    marcador. Por eso `id` nunca se infiere de la posición ni del orden en la
    lista.
    """

    id: int
    col: float
    row: float
    theta: float  # grados, 0 = derecha, sentido antihorario
    age_ms: int  # 0 = recién visto; creciente = ocluido o no detectado

    def a_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "col": self.col,
            "row": self.row,
            "theta": self.theta,
            "age_ms": self.age_ms,
        }

    @staticmethod
    def desde_dict(d: dict[str, Any]) -> Rover:
        return Rover(
            id=d["id"], col=d["col"], row=d["row"], theta=d["theta"], age_ms=d["age_ms"]
        )


@dataclass(frozen=True)
class Cube:
    """Un cubo de 6 cm. El color es la identidad: no hay dos del mismo color."""

    color: str
    col: float
    row: float
    age_ms: int

    def a_dict(self) -> dict[str, Any]:
        return {"color": self.color, "col": self.col, "row": self.row, "age_ms": self.age_ms}

    @staticmethod
    def desde_dict(d: dict[str, Any]) -> Cube:
        return Cube(color=d["color"], col=d["col"], row=d["row"], age_ms=d["age_ms"])


@dataclass(frozen=True)
class Obstacle:
    """Un bloque amarillo de 10 cm.

    No lleva `color` porque el amarillo está reservado para obstáculos, ni `id`
    porque son intercambiables entre sí: lo único que importa es dónde están.
    """

    col: float
    row: float
    age_ms: int

    def a_dict(self) -> dict[str, Any]:
        return {"col": self.col, "row": self.row, "age_ms": self.age_ms}

    @staticmethod
    def desde_dict(d: dict[str, Any]) -> Obstacle:
        return Obstacle(col=d["col"], row=d["row"], age_ms=d["age_ms"])


@dataclass(frozen=True)
class Start:
    """Esquina de salida de los robots. Coincide con el origen (0,0), que es el
    marcador ArUco de menor ID (el 0).

    Es un lugar FIJO: se declara por configuración, no se detecta. Por eso no
    lleva `age_ms`: nunca envejece ni se ocluye.
    """

    col: float
    row: float

    def a_dict(self) -> dict[str, Any]:
        return {"col": self.col, "row": self.row}

    @staticmethod
    def desde_dict(d: dict[str, Any]) -> Start:
        return Start(col=d["col"], row=d["row"])


@dataclass(frozen=True)
class Depot:
    """Zona de acopio de un color. Cada cubo va al depot de SU color.

    Va en una lista separada de `cubes` aunque compartan el color, porque los
    cubos se DETECTAN (se mueven, se ocluyen, envejecen) y los depots se
    DECLARAN (son fijos y siempre están).
    """

    color: str
    col: float
    row: float

    def a_dict(self) -> dict[str, Any]:
        return {"color": self.color, "col": self.col, "row": self.row}

    @staticmethod
    def desde_dict(d: dict[str, Any]) -> Depot:
        return Depot(color=d["color"], col=d["col"], row=d["row"])


@dataclass(frozen=True)
class Mensaje:
    """Un mensaje completo de telemetría: la foto del mundo en un instante.

    `seq` y `ts_ms` los pone el publicador, no el detector: sirven para que el
    consumidor detecte pérdidas (saltos de `seq`) y mida latencia real
    (`ahora - ts_ms`, con `ts_ms` = instante de CAPTURA del cuadro, no de envío).
    """

    seq: int
    ts_ms: int
    phase: str
    grid: Grid
    start: Start
    depots: tuple[Depot, ...] = ()
    rovers: tuple[Rover, ...] = ()
    cubes: tuple[Cube, ...] = ()
    obstacles: tuple[Obstacle, ...] = ()
    v: int = PROTOCOL_VERSION

    def a_dict(self) -> dict[str, Any]:
        return {
            "v": self.v,
            "seq": self.seq,
            "ts_ms": self.ts_ms,
            "phase": self.phase,
            "grid": self.grid.a_dict(),
            "rovers": [r.a_dict() for r in self.rovers],
            "cubes": [c.a_dict() for c in self.cubes],
            "obstacles": [o.a_dict() for o in self.obstacles],
            "start": self.start.a_dict(),
            "depots": [d.a_dict() for d in self.depots],
        }

    @staticmethod
    def desde_dict(d: dict[str, Any]) -> Mensaje:
        """Construye un `Mensaje` a partir de un dict ya parseado.

        Valida primero: preferimos fallar con un mensaje claro antes que
        construir un objeto a medias que reviente más adelante.
        """
        error = validate_message(d)
        if error is not None:
            raise ValueError(error)
        return Mensaje(
            v=d["v"],
            seq=d["seq"],
            ts_ms=d["ts_ms"],
            phase=d["phase"],
            grid=Grid.desde_dict(d["grid"]),
            start=Start.desde_dict(d["start"]),
            depots=tuple(Depot.desde_dict(x) for x in d["depots"]),
            rovers=tuple(Rover.desde_dict(x) for x in d["rovers"]),
            cubes=tuple(Cube.desde_dict(x) for x in d["cubes"]),
            obstacles=tuple(Obstacle.desde_dict(x) for x in d["obstacles"]),
        )


# --------------------------------------------------------------------------
# Validación
# --------------------------------------------------------------------------


def _es_entero(valor: Any) -> bool:
    """True si es un entero de verdad.

    `bool` es subclase de `int` en Python, así que `True` pasaría como entero.
    Lo excluimos a mano: un `True` en `seq` es un bug, no un dato.
    """
    return isinstance(valor, int) and not isinstance(valor, bool)


def _es_numero(valor: Any) -> bool:
    """True si es un número finito.

    Aceptamos `int` donde el contrato dice `float` porque JSON serializa `2.0`
    como `2`: rechazarlo tiraría mensajes perfectamente válidos. La regla de
    "nunca redondear a entero" es del PRODUCTOR, no del validador.
    """
    if isinstance(valor, bool):
        return False
    if not isinstance(valor, (int, float)):
        return False
    return math.isfinite(valor)


def _revisar_campos(obj: Any, esperados: frozenset, donde: str) -> str | None:
    """Verifica que `obj` sea un dict con exactamente los campos esperados."""
    if not isinstance(obj, dict):
        return "{}: se esperaba un objeto, llegó {}".format(donde, type(obj).__name__)
    presentes = set(obj.keys())
    faltantes = esperados - presentes
    if faltantes:
        return "{}: faltan campos {}".format(donde, sorted(faltantes))
    sobrantes = presentes - esperados
    if sobrantes:
        return "{}: campos no reconocidos {}".format(donde, sorted(sobrantes))
    return None


def _revisar_posicion(obj: dict[str, Any], donde: str) -> str | None:
    """Valida `col`/`row`.

    NO se exige que caigan dentro de la grilla: la corrección de paralaje puede
    dejar un objeto apenas afuera del borde, y eso es un dato válido, no un
    error de contrato. Solo se exige que sean números finitos.
    """
    for campo in ("col", "row"):
        if not _es_numero(obj[campo]):
            return "{}: '{}' debe ser un número finito, llegó {!r}".format(
                donde, campo, obj[campo]
            )
    return None


def _revisar_edad(obj: dict[str, Any], donde: str) -> str | None:
    if not _es_entero(obj["age_ms"]) or obj["age_ms"] < 0:
        return "{}: 'age_ms' debe ser un entero >= 0, llegó {!r}".format(donde, obj["age_ms"])
    return None


def _revisar_lista(msg: dict[str, Any], nombre: str) -> str | None:
    if not isinstance(msg[nombre], list):
        return "'{}' debe ser una lista, llegó {}".format(nombre, type(msg[nombre]).__name__)
    return None


def validate_message(msg: Any) -> str | None:
    """Valida un mensaje contra el contrato.

    Devuelve `None` si el mensaje cumple, o un texto claro con el PRIMER error
    encontrado si no. Devolver texto en vez de lanzar excepción es a propósito:
    un cliente debe poder descartar un mensaje malo y seguir andando, sin
    envolver todo en try/except.

    Rechaza, entre otras cosas: versión desconocida, campos faltantes o
    sobrantes, fase inválida, `theta` fuera de rango, colores fuera del
    contrato, colores de cubo duplicados (el color es la identidad), IDs de
    rover duplicados, y cubos sin un depot de su color.
    """
    # --- raíz -------------------------------------------------------------
    error = _revisar_campos(msg, _CAMPOS_MENSAJE, "mensaje")
    if error:
        return error

    # La versión se revisa primero: si no la conocemos, el resto de la forma no
    # es confiable y cualquier otro error sería ruido.
    if not _es_entero(msg["v"]):
        return "'v' debe ser un entero, llegó {!r}".format(msg["v"])
    if msg["v"] != PROTOCOL_VERSION:
        return "versión de protocolo desconocida: {} (esta implementación entiende {})".format(
            msg["v"], PROTOCOL_VERSION
        )

    if not _es_entero(msg["seq"]) or msg["seq"] < 0:
        return "'seq' debe ser un entero >= 0, llegó {!r}".format(msg["seq"])
    if not _es_entero(msg["ts_ms"]) or msg["ts_ms"] < 0:
        return "'ts_ms' debe ser un entero >= 0, llegó {!r}".format(msg["ts_ms"])
    if msg["phase"] not in PHASES:
        return "'phase' inválida: {!r} (válidas: {})".format(msg["phase"], list(PHASES))

    # --- grid -------------------------------------------------------------
    error = _revisar_campos(msg["grid"], _CAMPOS_GRID, "grid")
    if error:
        return error
    grid = msg["grid"]
    for campo in ("cols", "rows"):
        if not _es_entero(grid[campo]) or grid[campo] <= 0:
            return "grid: '{}' debe ser un entero > 0, llegó {!r}".format(campo, grid[campo])
    if not _es_numero(grid["cell_mm"]) or grid["cell_mm"] <= 0:
        return "grid: 'cell_mm' debe ser un número > 0, llegó {!r}".format(grid["cell_mm"])

    # --- listas dinámicas -------------------------------------------------
    for nombre in ("rovers", "cubes", "obstacles", "depots"):
        error = _revisar_lista(msg, nombre)
        if error:
            return error

    # --- rovers -----------------------------------------------------------
    ids_vistos = set()
    for i, rover in enumerate(msg["rovers"]):
        donde = "rovers[{}]".format(i)
        error = _revisar_campos(rover, _CAMPOS_ROVER, donde)
        if error:
            return error
        if not _es_entero(rover["id"]) or rover["id"] < 0:
            return "{}: 'id' debe ser un entero >= 0 (ID del marcador ArUco), llegó {!r}".format(
                donde, rover["id"]
            )
        if rover["id"] in ids_vistos:
            return "{}: 'id' duplicado {} — cada rover aparece una sola vez".format(
                donde, rover["id"]
            )
        ids_vistos.add(rover["id"])
        error = _revisar_posicion(rover, donde) or _revisar_edad(rover, donde)
        if error:
            return error
        if not _es_numero(rover["theta"]) or not (0.0 <= rover["theta"] <= 360.0):
            return "{}: 'theta' debe estar en grados dentro de [0, 360], llegó {!r}".format(
                donde, rover["theta"]
            )

    # --- depots (se validan antes que los cubos porque los cubos dependen) --
    colores_depot = set()
    for i, depot in enumerate(msg["depots"]):
        donde = "depots[{}]".format(i)
        error = _revisar_campos(depot, _CAMPOS_DEPOT, donde)
        if error:
            return error
        if depot["color"] not in CUBE_COLORS:
            return "{}: color fuera del contrato: {!r} (válidos: {})".format(
                donde, depot["color"], list(CUBE_COLORS)
            )
        if depot["color"] in colores_depot:
            return "{}: hay más de un depot de color {!r} — debe haber uno por color".format(
                donde, depot["color"]
            )
        colores_depot.add(depot["color"])
        error = _revisar_posicion(depot, donde)
        if error:
            return error

    # --- cubes ------------------------------------------------------------
    colores_cubo = set()
    for i, cubo in enumerate(msg["cubes"]):
        donde = "cubes[{}]".format(i)
        error = _revisar_campos(cubo, _CAMPOS_CUBE, donde)
        if error:
            return error
        if cubo["color"] not in CUBE_COLORS:
            return "{}: color fuera del contrato: {!r} (válidos: {}; el {} está reservado " \
                   "para obstáculos)".format(
                       donde, cubo["color"], list(CUBE_COLORS), COLOR_RESERVADO_OBSTACULO
                   )
        if cubo["color"] in colores_cubo:
            return "{}: color de cubo duplicado {!r} — el color ES la identidad del cubo".format(
                donde, cubo["color"]
            )
        colores_cubo.add(cubo["color"])
        error = _revisar_posicion(cubo, donde) or _revisar_edad(cubo, donde)
        if error:
            return error

    # Invariante de juego: todo cubo tiene a dónde ir. Un cubo sin depot de su
    # color dejaría a los equipos con una tarea imposible.
    sin_destino = sorted(colores_cubo - colores_depot)
    if sin_destino:
        return "hay cubos sin depot de su color: {} (depots presentes: {})".format(
            sin_destino, sorted(colores_depot)
        )

    # --- obstacles --------------------------------------------------------
    for i, obst in enumerate(msg["obstacles"]):
        donde = "obstacles[{}]".format(i)
        error = _revisar_campos(obst, _CAMPOS_OBSTACLE, donde)
        if error:
            return error
        error = _revisar_posicion(obst, donde) or _revisar_edad(obst, donde)
        if error:
            return error

    # --- start ------------------------------------------------------------
    error = _revisar_campos(msg["start"], _CAMPOS_START, "start")
    if error:
        return error
    error = _revisar_posicion(msg["start"], "start")
    if error:
        return error

    return None


# --------------------------------------------------------------------------
# Formato de cable (NDJSON)
#
# Vive en el contrato para que el simulador, el cliente de referencia y el
# sistema de visión real usen exactamente el mismo código de serialización. Si
# el formato de cable estuviera duplicado, tarde o temprano divergiría.
# --------------------------------------------------------------------------


def codificar_ndjson(msg: Any) -> str:
    """Serializa un mensaje (dict o `Mensaje`) a una línea NDJSON con `\\n`.

    `separators` sin espacios para no gastar ancho de banda, y `ensure_ascii`
    en False porque no hay razón para escapar: el contrato es ASCII puro.
    """
    if isinstance(msg, Mensaje):
        msg = msg.a_dict()
    return json.dumps(msg, separators=(",", ":"), ensure_ascii=False) + "\n"


def decodificar_ndjson(linea: str) -> dict[str, Any]:
    """Parsea una línea NDJSON a dict. Lanza `ValueError` si no es JSON válido.

    No valida el contrato: eso es trabajo de `validate_message`. Separar
    "parsear" de "validar" permite reportar los dos errores por separado.
    """
    dato = json.loads(linea)
    if not isinstance(dato, dict):
        raise ValueError("la línea no contiene un objeto JSON")
    return dato
