"""Carga de la configuración del sistema de visión.

Todo umbral, tamaño, ID y disposición vive en `config_vision.json`, no en el
código (ver CLAUDE.md, sección 6). Este módulo traduce ese archivo a estructuras
inmutables, para que el resto del sistema no ande leyendo diccionarios sueltos
ni pueda modificar la configuración por accidente a mitad de una ronda.

Las claves que empiezan con `_` son notas para quien edita el JSON —que no
admite comentarios— y se ignoran solas, porque acá se leen las claves por nombre
en vez de barrer el diccionario.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import cv2

CONFIG_POR_DEFECTO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_vision.json")

#: Nombres de esquina admitidos y su celda, en función del tamaño de la grilla.
#: Se usan nombres en vez de números para que la disposición no se rompa al
#: cambiar `cols`/`rows` cuando se mida la cancha real.
_ESQUINAS = {
    "origen": lambda cols, rows: (0.0, 0.0),
    "fin_col": lambda cols, rows: (float(cols), 0.0),
    "diagonal": lambda cols, rows: (float(cols), float(rows)),
    "fin_row": lambda cols, rows: (0.0, float(rows)),
}


@dataclass(frozen=True, slots=True)
class Tablero:
    """Dimensiones de la cancha, en celdas.

    La cancha efectiva es el área entre los CENTROS de los cuatro marcadores de
    esquina, no el tablero físico. Por eso estos valores son "a confirmar" hasta
    que la cancha esté montada y medida.
    """

    cols: int
    rows: int
    cell_mm: float


@dataclass(frozen=True, slots=True)
class MarcadoresEsquina:
    """Los cuatro marcadores que anclan el sistema de coordenadas.

    `disposicion` mapea ID de marcador -> celda donde está su centro. El ID 0
    es el origen (0,0) y coincide con la esquina de salida de los robots
    (CLAUDE.md, sección 5). El orden de los otros tres es horario y es una
    REGLA DE MONTAJE FÍSICO: si se pegan en otro orden, todas las coordenadas
    salen rotadas o espejadas.
    """

    nombre_diccionario: str
    disposicion: dict[int, tuple[float, float]]

    @property
    def ids_esperados(self) -> frozenset[int]:
        return frozenset(self.disposicion)


@dataclass(frozen=True, slots=True)
class Perspectiva:
    """Inclinación simulada de la cámara para las imágenes sintéticas."""

    activa: bool
    inclinacion: float


@dataclass(frozen=True, slots=True)
class Sintetico:
    """Parámetros del generador de imágenes de prueba."""

    ancho_px: int
    alto_px: int
    margen_px: int
    lado_marcador_esquina_celdas: float
    lado_marcador_rover_celdas: float
    borde_blanco_celdas: float
    color_fondo: int
    color_grilla: int
    dibujar_grilla: bool
    paso_grilla_celdas: int
    desenfoque_px: int
    ruido_sigma: float
    perspectiva: Perspectiva


@dataclass(frozen=True, slots=True)
class RoverDemo:
    """Un rover de ejemplo para las imágenes de prueba.

    `theta` sigue la convención del contrato: grados, 0 = derecha, antihorario.
    """

    id: int
    col: float
    row: float
    theta: float


@dataclass(frozen=True, slots=True)
class ConfigVision:
    tablero: Tablero
    marcadores_esquina: MarcadoresEsquina
    sintetico: Sintetico
    rovers_demo: tuple[RoverDemo, ...]


def diccionario_aruco(nombre: str):
    """Resuelve el nombre del diccionario ArUco a su objeto de OpenCV.

    Se guarda el NOMBRE en la configuración, no la constante numérica: el número
    no le dice nada a quien edita el archivo, y el nombre además documenta qué
    hay que imprimir para la cancha.
    """
    constante = getattr(cv2.aruco, nombre, None)
    if constante is None:
        raise ValueError(
            "diccionario ArUco desconocido: {!r} (por ejemplo, 'DICT_4X4_50')".format(nombre)
        )
    return cv2.aruco.getPredefinedDictionary(constante)


def _leer_disposicion(bruto: dict[str, Any], cols: int, rows: int) -> dict[int, tuple[float, float]]:
    """Traduce {'0': 'origen', ...} a {0: (0.0, 0.0), ...}."""
    salida: dict[int, tuple[float, float]] = {}
    for id_texto, nombre in bruto.items():
        if nombre not in _ESQUINAS:
            raise ValueError(
                "esquina desconocida {!r} para el marcador {}; válidas: {}".format(
                    nombre, id_texto, sorted(_ESQUINAS)
                )
            )
        salida[int(id_texto)] = _ESQUINAS[nombre](cols, rows)
    return salida


def cargar_config(ruta: str = CONFIG_POR_DEFECTO) -> ConfigVision:
    """Lee y valida el archivo de configuración."""
    with open(ruta, "r", encoding="utf-8") as f:
        d = json.load(f)

    t = d["tablero"]
    tablero = Tablero(cols=int(t["cols"]), rows=int(t["rows"]), cell_mm=float(t["cell_mm"]))

    m = d["marcadores_esquina"]
    marcadores = MarcadoresEsquina(
        nombre_diccionario=m["diccionario"],
        disposicion=_leer_disposicion(m["disposicion"], tablero.cols, tablero.rows),
    )

    s = d["sintetico"]
    p = s["perspectiva"]
    sintetico = Sintetico(
        ancho_px=int(s["ancho_px"]),
        alto_px=int(s["alto_px"]),
        margen_px=int(s["margen_px"]),
        lado_marcador_esquina_celdas=float(s["lado_marcador_esquina_celdas"]),
        lado_marcador_rover_celdas=float(s["lado_marcador_rover_celdas"]),
        borde_blanco_celdas=float(s["borde_blanco_celdas"]),
        color_fondo=int(s["color_fondo"]),
        color_grilla=int(s["color_grilla"]),
        dibujar_grilla=bool(s["dibujar_grilla"]),
        paso_grilla_celdas=int(s["paso_grilla_celdas"]),
        desenfoque_px=int(s["desenfoque_px"]),
        ruido_sigma=float(s["ruido_sigma"]),
        perspectiva=Perspectiva(activa=bool(p["activa"]), inclinacion=float(p["inclinacion"])),
    )

    rovers = tuple(
        RoverDemo(id=int(r["id"]), col=float(r["col"]), row=float(r["row"]), theta=float(r["theta"]))
        for r in d.get("rovers_demo", ())
    )

    cfg = ConfigVision(
        tablero=tablero, marcadores_esquina=marcadores, sintetico=sintetico, rovers_demo=rovers
    )
    error = revisar_config(cfg)
    if error is not None:
        raise ValueError("config_vision.json: " + error)
    return cfg


def revisar_config(cfg: ConfigVision) -> str | None:
    """Revisa que la configuración sea coherente antes de usarla.

    Vale la pena fallar acá con un mensaje claro: una configuración incoherente
    produce imágenes o coordenadas silenciosamente mal, que es mucho más caro de
    diagnosticar que un error al arrancar.
    """
    if cfg.tablero.cols <= 0 or cfg.tablero.rows <= 0:
        return "cols y rows deben ser > 0"
    if cfg.tablero.cell_mm <= 0:
        return "cell_mm debe ser > 0"
    if cfg.marcadores_esquina.ids_esperados != frozenset((0, 1, 2, 3)):
        return "se esperan exactamente los marcadores de esquina 0, 1, 2 y 3; hay {}".format(
            sorted(cfg.marcadores_esquina.ids_esperados)
        )
    if len(set(cfg.marcadores_esquina.disposicion.values())) != 4:
        return "hay dos marcadores de esquina asignados a la misma esquina"
    ids_rover = [r.id for r in cfg.rovers_demo]
    if len(set(ids_rover)) != len(ids_rover):
        return "hay rovers de demostración con el mismo ID de marcador"
    chocan = sorted(set(ids_rover) & cfg.marcadores_esquina.ids_esperados)
    if chocan:
        return "los IDs {} están reservados para los marcadores de esquina".format(chocan)
    s = cfg.sintetico
    if min(s.ancho_px, s.alto_px) <= 2 * s.margen_px:
        return "el margen no deja lugar para el tablero dentro de la imagen"
    if s.borde_blanco_celdas <= 0:
        return "borde_blanco_celdas debe ser > 0: sin zona blanca el detector no ve los marcadores"
    if not (0.0 <= s.perspectiva.inclinacion < 0.5):
        return "perspectiva.inclinacion debe estar en [0, 0.5)"
    return None
