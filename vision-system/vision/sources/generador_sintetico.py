"""Generador de imágenes cenitales sintéticas del tablero.

Para qué existe
---------------
Para poder probar la visión **sin cámara y sin cancha**, y sobre todo para poder
**verificarla**: el generador sabe exactamente dónde puso cada cosa, así que lo
detectado se puede comparar contra la verdad. Sin esa verdad conocida, una
prueba solo diría "no explotó", no "está bien".

Esto NO es el simulador de `contrato/`
--------------------------------------
Aquel emite **posiciones en JSON** por la red, para que los equipos prueben su
rover. Este dibuja **imágenes del tablero**, para que el sistema de visión tenga
qué procesar. Uno se consume por TCP; el otro entra por el lado de la cámara.

Convención de orientación
-------------------------
El "adelante" de un marcador es la dirección que va **del centro al punto medio
de su borde superior**. `theta` es el ángulo de esa dirección, en grados, con
`0 = derecha` y sentido antihorario — la misma convención que publica el
contrato. Como `row` crece hacia abajo, el vector de avance en píxeles es
`(cos θ, −sin θ)`.
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass

import cv2
import numpy as np

try:  # como paquete: python -m vision.sources.generador_sintetico
    from ..configuracion import ConfigVision, Perspectiva, RoverDemo, diccionario_aruco
    from .fuente import Cuadro, ahora_ms
except ImportError:  # como script suelto
    from vision.configuracion import (  # type: ignore[no-redef]
        ConfigVision,
        Perspectiva,
        RoverDemo,
        diccionario_aruco,
    )
    from vision.sources.fuente import Cuadro, ahora_ms  # type: ignore[no-redef]


# --------------------------------------------------------------------------
# La verdad conocida
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MarcadorVerdad:
    """Dónde puso el generador un marcador, en celdas y en píxeles.

    Guarda las dos cosas a propósito: la celda es lo que el sistema de visión
    tiene que llegar a deducir, y los píxeles son el dato de entrada con el que
    se puede armar la prueba sin pasar por el detector.
    """

    id: int
    col: float
    row: float
    theta_grados: float
    centro_px: tuple[float, float]
    esquinas_px: tuple[tuple[float, float], ...]


@dataclass(frozen=True, slots=True, eq=False)
class VerdadTablero:
    """Todo lo que el generador sabe de la imagen que acaba de crear.

    `eq=False` porque contiene una matriz de NumPy: comparar dos verdades con
    `==` no tendría un resultado booleano claro, y no lo necesitamos.
    """

    ancho_px: int
    alto_px: int
    cols: int
    rows: int
    cell_mm: float
    px_por_celda: float
    origen_px: tuple[float, float]
    homografia: np.ndarray  # celdas escaladas -> píxeles finales (identidad si no hay perspectiva)
    con_perspectiva: bool
    esquinas: tuple[MarcadorVerdad, ...]
    rovers: tuple[MarcadorVerdad, ...]

    def celda_a_pixel(self, col: float, row: float) -> tuple[float, float]:
        """Convierte una celda al píxel donde el generador la dibujó.

        Este es **el mapeo verdadero**: lo que el módulo de geometría tiene que
        llegar a invertir a partir de la imagen sola. Toda la verificación se
        apoya en esta función.
        """
        punto = self.celdas_a_pixeles(np.array([[col, row]], dtype=np.float64))
        return (float(punto[0, 0]), float(punto[0, 1]))

    def celdas_a_pixeles(self, celdas: np.ndarray) -> np.ndarray:
        """Versión vectorizada de `celda_a_pixel`. Recibe y devuelve (N, 2)."""
        celdas = np.asarray(celdas, dtype=np.float64).reshape(-1, 2)
        x0, y0 = self.origen_px
        ideales = np.column_stack(
            (x0 + celdas[:, 0] * self.px_por_celda, y0 + celdas[:, 1] * self.px_por_celda)
        )
        return _aplicar_homografia(self.homografia, ideales)

    def marcador(self, id_aruco: int) -> MarcadorVerdad | None:
        """Busca un marcador por ID, entre esquinas y rovers. Itera, no indexa."""
        for m in tuple(self.esquinas) + tuple(self.rovers):
            if m.id == id_aruco:
                return m
        return None


# --------------------------------------------------------------------------
# Utilidades geométricas
# --------------------------------------------------------------------------


def _aplicar_homografia(h: np.ndarray, puntos: np.ndarray) -> np.ndarray:
    """Aplica una homografía 3x3 a un arreglo (N, 2)."""
    puntos = np.asarray(puntos, dtype=np.float64).reshape(-1, 1, 2)
    return cv2.perspectiveTransform(puntos, h).reshape(-1, 2)


def _cuadrilatero(centro: tuple[float, float], lado_px: float, theta_grados: float) -> np.ndarray:
    """Las cuatro esquinas de un marcador cuadrado, en orden TL, TR, BR, BL.

    Ese es el mismo orden en el que OpenCV devuelve las esquinas detectadas, así
    que lo generado y lo detectado se pueden comparar directamente.

    Calcular las esquinas de forma analítica —en vez de rotar un bitmap y
    después buscar dónde quedó— es lo que hace que la verdad sea **exacta por
    construcción** y no una aproximación.
    """
    rad = math.radians(theta_grados)
    # "Adelante" del marcador. El signo menos en la componente vertical es
    # porque `row` (y por lo tanto el eje Y de la imagen) crece hacia abajo.
    fx, fy = math.cos(rad), -math.sin(rad)
    ux, uy = -fy, fx  # eje local +X: la derecha del marcador
    vx, vy = -fx, -fy  # eje local +Y: el abajo del marcador
    h = lado_px / 2.0
    cx, cy = centro
    esquinas = [
        (cx + a * h * ux + b * h * vx, cy + a * h * uy + b * h * vy)
        for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))
    ]
    return np.array(esquinas, dtype=np.float64)


def _estampar(lienzo: np.ndarray, bitmap: np.ndarray, cuadrilatero: np.ndarray) -> None:
    """Pega `bitmap` deformado sobre el cuadrilátero indicado del lienzo.

    Se estampa por cuadrilátero en vez de rotar y pegar, porque así el marcador
    cae exactamente donde dicen las esquinas calculadas: la imagen y la verdad
    no pueden desincronizarse.
    """
    alto, ancho = bitmap.shape[:2]
    origen = np.array(
        [[0, 0], [ancho - 1, 0], [ancho - 1, alto - 1], [0, alto - 1]], dtype=np.float32
    )
    m = cv2.getPerspectiveTransform(origen, cuadrilatero.astype(np.float32))
    destino = (lienzo.shape[1], lienzo.shape[0])
    deformado = cv2.warpPerspective(bitmap, m, destino, flags=cv2.INTER_LINEAR)
    mascara = cv2.warpPerspective(
        np.full((alto, ancho), 255, np.uint8), m, destino, flags=cv2.INTER_NEAREST
    )
    lienzo[mascara > 0] = deformado[mascara > 0]


def _bitmap_marcador(diccionario, id_aruco: int, lado_px: int, borde_px: int) -> np.ndarray:
    """Genera el marcador con su zona blanca alrededor.

    La zona blanca no es decorativa: el detector de ArUco necesita contraste en
    todo el contorno para encontrar el marcador. Sin ella, el marcador es
    invisible aunque esté perfectamente dibujado.
    """
    marcador = cv2.aruco.generateImageMarker(diccionario, id_aruco, lado_px)
    total = lado_px + 2 * borde_px
    lienzo = np.full((total, total), 255, np.uint8)
    lienzo[borde_px : borde_px + lado_px, borde_px : borde_px + lado_px] = marcador
    return lienzo


# --------------------------------------------------------------------------
# Generación
# --------------------------------------------------------------------------


def generar(
    cfg: ConfigVision,
    rovers: tuple[RoverDemo, ...] | None = None,
    perspectiva: Perspectiva | None = None,
    semilla: int = 0,
) -> tuple[np.ndarray, VerdadTablero]:
    """Dibuja una imagen sintética del tablero y devuelve `(imagen, verdad)`.

    `rovers` y `perspectiva` permiten pisar lo que dice la configuración sin
    tocar el archivo, que es lo que necesita una batería de pruebas para
    recorrer varios escenarios.
    """
    s = cfg.sintetico
    t = cfg.tablero
    persp = perspectiva if perspectiva is not None else s.perspectiva
    lista_rovers = cfg.rovers_demo if rovers is None else rovers

    # El lado de celda se deriva del tamaño de imagen para que la grilla entre
    # con sus márgenes; el tablero queda centrado.
    ppc = min(
        (s.ancho_px - 2 * s.margen_px) / t.cols,
        (s.alto_px - 2 * s.margen_px) / t.rows,
    )
    x0 = (s.ancho_px - t.cols * ppc) / 2.0
    y0 = (s.alto_px - t.rows * ppc) / 2.0

    def ideal(col: float, row: float) -> tuple[float, float]:
        return (x0 + col * ppc, y0 + row * ppc)

    lienzo = np.full((s.alto_px, s.ancho_px), s.color_fondo, np.uint8)
    if s.dibujar_grilla:
        _dibujar_grilla(lienzo, t, s, ideal)

    diccionario = diccionario_aruco(cfg.marcadores_esquina.nombre_diccionario)
    borde_px = max(1, int(round(s.borde_blanco_celdas * ppc)))

    # --- marcadores de esquina --------------------------------------------
    # Se dibujan derechos (theta = 90: su borde superior mira hacia arriba). Su
    # orientación no se usa para nada; lo que ancla las coordenadas es su centro.
    esquinas: list[MarcadorVerdad] = []
    for id_aruco, (col, row) in sorted(cfg.marcadores_esquina.disposicion.items()):
        esquinas.append(
            _dibujar_marcador(
                lienzo, diccionario, id_aruco, col, row, 90.0,
                s.lado_marcador_esquina_celdas, ppc, borde_px, ideal,
            )
        )

    # --- rovers ------------------------------------------------------------
    marcadores_rover: list[MarcadorVerdad] = []
    for rover in lista_rovers:
        marcadores_rover.append(
            _dibujar_marcador(
                lienzo, diccionario, rover.id, rover.col, rover.row, rover.theta,
                s.lado_marcador_rover_celdas, ppc, borde_px, ideal,
            )
        )

    # --- inclinación de cámara --------------------------------------------
    homografia = np.eye(3, dtype=np.float64)
    if persp.activa and persp.inclinacion > 0:
        homografia = _homografia_perspectiva(s.ancho_px, s.alto_px, persp.inclinacion)
        lienzo = cv2.warpPerspective(
            lienzo,
            homografia,
            (s.ancho_px, s.alto_px),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=int(s.color_fondo),
        )
        esquinas = [_reproyectar(m, homografia) for m in esquinas]
        marcadores_rover = [_reproyectar(m, homografia) for m in marcadores_rover]

    # --- degradación opcional ---------------------------------------------
    if s.desenfoque_px > 0:
        k = 2 * s.desenfoque_px + 1
        lienzo = cv2.GaussianBlur(lienzo, (k, k), 0)
    if s.ruido_sigma > 0:
        rng = np.random.default_rng(semilla)
        ruido = rng.normal(0.0, s.ruido_sigma, lienzo.shape)
        lienzo = np.clip(lienzo.astype(np.float64) + ruido, 0, 255).astype(np.uint8)

    verdad = VerdadTablero(
        ancho_px=s.ancho_px,
        alto_px=s.alto_px,
        cols=t.cols,
        rows=t.rows,
        cell_mm=t.cell_mm,
        px_por_celda=ppc,
        origen_px=(x0, y0),
        homografia=homografia,
        con_perspectiva=bool(persp.activa and persp.inclinacion > 0),
        esquinas=tuple(esquinas),
        rovers=tuple(marcadores_rover),
    )
    return lienzo, verdad


def _dibujar_marcador(
    lienzo, diccionario, id_aruco, col, row, theta, lado_celdas, ppc, borde_px, ideal
) -> MarcadorVerdad:
    """Estampa un marcador y devuelve la verdad de dónde quedó."""
    centro = ideal(col, row)
    lado_px = lado_celdas * ppc
    # El cuadrilátero que se estampa incluye la zona blanca; el que se guarda
    # como verdad es el del marcador en sí, que es lo que va a detectar OpenCV.
    total_px = lado_px + 2 * borde_px
    _estampar(
        lienzo,
        _bitmap_marcador(diccionario, id_aruco, int(round(lado_px)), borde_px),
        _cuadrilatero(centro, total_px, theta),
    )
    esquinas = _cuadrilatero(centro, lado_px, theta)
    return MarcadorVerdad(
        id=id_aruco,
        col=col,
        row=row,
        theta_grados=theta,
        centro_px=(centro[0], centro[1]),
        esquinas_px=tuple((float(x), float(y)) for x, y in esquinas),
    )


def _reproyectar(m: MarcadorVerdad, homografia: np.ndarray) -> MarcadorVerdad:
    """Lleva la verdad de un marcador a la imagen ya inclinada.

    Se produce un objeto nuevo en vez de modificar el anterior: la verdad, como
    el estado del mundo, es inmutable.
    """
    puntos = np.array((m.centro_px,) + tuple(m.esquinas_px), dtype=np.float64)
    movidos = _aplicar_homografia(homografia, puntos)
    return MarcadorVerdad(
        id=m.id,
        col=m.col,
        row=m.row,
        theta_grados=m.theta_grados,
        centro_px=(float(movidos[0, 0]), float(movidos[0, 1])),
        esquinas_px=tuple((float(x), float(y)) for x, y in movidos[1:]),
    )


def _homografia_perspectiva(ancho: int, alto: int, inclinacion: float) -> np.ndarray:
    """Simula una cámara que no está perfectamente cenital.

    Angosta el borde superior de la imagen, que es lo que se ve cuando la cámara
    mira el tablero con algo de ángulo. La cámara real nunca va a estar perfecta,
    y con una imagen perfectamente cenital la homografía se reduciría a una
    escala: la verificación pasaría aunque la matemática estuviera mal.
    """
    d = inclinacion * ancho
    origen = np.array([[0, 0], [ancho, 0], [ancho, alto], [0, alto]], dtype=np.float32)
    destino = np.array([[d, 0], [ancho - d, 0], [ancho, alto], [0, alto]], dtype=np.float32)
    return cv2.getPerspectiveTransform(origen, destino).astype(np.float64)


# --------------------------------------------------------------------------
# Fuente de imágenes — la misma interfaz que la cámara real
# --------------------------------------------------------------------------


class FuenteSintetica:
    """Entrega imágenes sintéticas cumpliendo la interfaz de `fuente.py`.

    Sirve para correr contra el sistema completo **sin cámara**: cualquier pieza
    que reciba una `FuenteImagen` funciona igual con esta o con `FuenteCamara`.
    Y como sigue exponiendo la `verdad` de lo que dibujó, permite verificar lo
    que el sistema deduce, cosa que la cámara real no puede hacer.

    La imagen se genera **una sola vez** al construir y se reutiliza: para
    diagnóstico alcanza, y evita rehacer el mismo dibujo decenas de veces por
    segundo. Lo que cambia en cada lectura es la marca de tiempo, que es lo que
    el consumidor usa para medir edad.
    """

    def __init__(
        self,
        cfg: ConfigVision,
        rovers: tuple[RoverDemo, ...] | None = None,
        perspectiva: Perspectiva | None = None,
    ):
        self.imagen, self.verdad = generar(cfg, rovers=rovers, perspectiva=perspectiva)
        self._indice = 0
        self._marcas: deque[float] = deque(maxlen=90)

    def leer(self) -> Cuadro:
        self._indice += 1
        self._marcas.append(time.monotonic())
        return Cuadro(imagen=self.imagen, ts_ms=ahora_ms(), indice=self._indice)

    @property
    def fps_real(self) -> float:
        """Cuadros por segundo que está entregando de hecho.

        La fuente sintética no tiene una tasa propia: entrega tan rápido como se
        lo pidan. Se mide igual para que el diagnóstico muestre lo mismo en las
        dos fuentes en vez de un hueco.
        """
        if len(self._marcas) < 2:
            return 0.0
        lapso = self._marcas[-1] - self._marcas[0]
        return (len(self._marcas) - 1) / lapso if lapso > 0 else 0.0

    def cerrar(self) -> None:
        """No hay nada que liberar; existe para cumplir la interfaz."""

    def __enter__(self) -> "FuenteSintetica":
        return self

    def __exit__(self, *_) -> None:
        self.cerrar()


def _dibujar_grilla(lienzo, tablero, sintetico, ideal) -> None:
    """Dibuja la grilla tenue. Es ayuda visual: no interviene en la detección."""
    paso = max(1, sintetico.paso_grilla_celdas)
    color = int(sintetico.color_grilla)
    for col in range(0, tablero.cols + 1, paso):
        p1 = tuple(int(round(v)) for v in ideal(col, 0))
        p2 = tuple(int(round(v)) for v in ideal(col, tablero.rows))
        cv2.line(lienzo, p1, p2, color, 1, cv2.LINE_AA)
    for row in range(0, tablero.rows + 1, paso):
        p1 = tuple(int(round(v)) for v in ideal(0, row))
        p2 = tuple(int(round(v)) for v in ideal(tablero.cols, row))
        cv2.line(lienzo, p1, p2, color, 1, cv2.LINE_AA)
