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
    from ..configuracion import (
        ConfigVision, CuboDemo, Perspectiva, RoverDemo, diccionario_aruco,
    )
    from .fuente import Cuadro, ahora_ms
except ImportError:  # como script suelto
    from vision.configuracion import (  # type: ignore[no-redef]
        ConfigVision,
        CuboDemo,
        Perspectiva,
        RoverDemo,
        diccionario_aruco,
    )
    from vision.sources.fuente import Cuadro, ahora_ms  # type: ignore[no-redef]


# --------------------------------------------------------------------------
# La cámara
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, eq=False)
class CamaraSintetica:
    """Una cámara estenopeica real: dónde está, hacia dónde mira y sus intrínsecos.

    Por qué una cámara y no una homografía inventada
    ------------------------------------------------
    Antes, el modo "con perspectiva" angostaba el borde superior de la imagen una
    fracción del ancho. Eso deforma parecido a una cámara inclinada, pero **no es
    una cámara**: no tiene centro, no tiene altura, y por lo tanto no hay rayos.

    Sin rayos no se pueden simular las dos cosas que el sistema tiene que
    resolver de verdad:

    - el **paralaje**, que es que un objeto con altura se ve corrido porque su
      rayo hasta la cámara cruza el plano del tablero en otro lado;
    - la **oclusión**, que es que un objeto tapa a otro cuando se le pone en el
      rayo.

    Con una cámara de verdad las dos salen solas, y —lo que más importa— hay una
    **verdad conocida** contra la cual verificarlas.

    El sistema de coordenadas del mundo
    -----------------------------------
    `X = col · cell_mm`, `Y = −row · cell_mm`, `Z` hacia arriba desde el tablero.

    El menos en `Y` no es un capricho: `row` crece hacia abajo en la imagen, y
    una cámara real que mira hacia abajo invierte ese eje. Sin el menos, la
    imagen saldría espejada — y un ArUco espejado no lo detecta nadie, porque no
    coincide con ninguna entrada del diccionario.
    """

    posicion_mm: np.ndarray  # (3,) centro óptico en el mundo
    objetivo_mm: np.ndarray  # (3,) punto del tablero al que apunta
    matriz: np.ndarray  # (3,3) intrínsecos
    ancho_px: int
    alto_px: int
    cell_mm: float

    @property
    def altura_mm(self) -> float:
        return float(self.posicion_mm[2])

    @property
    def nadir_celdas(self) -> tuple[float, float]:
        """La celda que queda justo debajo de la cámara.

        Es el centro de la homotecia del paralaje: un objeto ahí no se corre
        nada por alto que sea, y el corrimiento crece con la distancia a este
        punto. Todo lo que tenga altura se corre **alejándose** de acá.
        """
        return (float(self.posicion_mm[0] / self.cell_mm),
                float(-self.posicion_mm[1] / self.cell_mm))

    def _rotacion(self) -> np.ndarray:
        """Matriz de rotación mundo -> cámara, mirando al objetivo.

        Se construye a mano y no con una función de OpenCV porque el caso
        cenital —la cámara mirando exactamente hacia abajo— hace degenerar la
        receta habitual de "arriba del mundo", que ahí queda paralela al eje
        óptico.
        """
        z = self.objetivo_mm - self.posicion_mm
        z = z / np.linalg.norm(z)
        # Referencia: el "abajo" de la imagen tiene que caer del lado de `row`
        # creciente, que en el mundo es -Y.
        referencia = np.array([0.0, -1.0, 0.0])
        if abs(float(np.dot(z, referencia))) > 0.999:  # mirando a lo largo de Y
            referencia = np.array([0.0, 0.0, 1.0])
        x = np.cross(referencia, z)
        x = x / np.linalg.norm(x)
        y = np.cross(z, x)
        return np.vstack((x, y, z))

    def proyectar(self, puntos_mm: np.ndarray) -> np.ndarray:
        """Proyecta puntos del mundo (N,3) en mm a píxeles (N,2)."""
        puntos = np.asarray(puntos_mm, dtype=np.float64).reshape(-1, 3)
        rot = self._rotacion()
        rvec, _ = cv2.Rodrigues(rot)
        tvec = -rot @ self.posicion_mm.reshape(3, 1)
        salida, _ = cv2.projectPoints(
            puntos, rvec, tvec, self.matriz, np.zeros(5, dtype=np.float64)
        )
        return salida.reshape(-1, 2)

    def celdas_a_mundo(self, celdas: np.ndarray, altura_mm: float = 0.0) -> np.ndarray:
        """Pasa celdas (N,2) a puntos del mundo (N,3) a la altura indicada."""
        celdas = np.asarray(celdas, dtype=np.float64).reshape(-1, 2)
        return np.column_stack((
            celdas[:, 0] * self.cell_mm,
            -celdas[:, 1] * self.cell_mm,
            np.full(len(celdas), float(altura_mm)),
        ))

    def proyectar_celdas(self, celdas: np.ndarray, altura_mm: float = 0.0) -> np.ndarray:
        """Atajo: de celdas a píxeles, a la altura indicada."""
        return self.proyectar(self.celdas_a_mundo(celdas, altura_mm))


def camara_para(cfg: ConfigVision, inclinacion_grados: float = 0.0) -> CamaraSintetica:
    """Arma la cámara a partir de la configuración.

    La distancia focal **se deriva del encuadre** en vez de configurarse: se
    elige la que hace que la cancha ocupe la imagen dejando el margen pedido,
    igual que antes se derivaba el lado de celda en píxeles. Así el tamaño de
    imagen sigue siendo lo configurable y no hay dos números que mantener
    coherentes entre sí.

    `inclinacion_grados` corre la cámara de lado manteniéndola apuntada al
    centro del tablero. Es una inclinación **física**: el ángulo entre el eje
    óptico y la vertical, que es lo que uno mediría con un transportador sobre
    el soporte real.
    """
    s = cfg.sintetico
    t = cfg.tablero

    ancho_cancha_mm = t.cols * t.cell_mm
    alto_cancha_mm = t.rows * t.cell_mm
    centro = np.array([ancho_cancha_mm / 2.0, -alto_cancha_mm / 2.0, 0.0])

    altura = float(s.altura_camara_mm)
    # Focal que hace entrar la cancha con su margen, con la cámara cenital.
    disponible_px = min(s.ancho_px - 2 * s.margen_px, s.alto_px - 2 * s.margen_px)
    focal = disponible_px * altura / max(ancho_cancha_mm, alto_cancha_mm)

    matriz = np.array([
        [focal, 0.0, s.ancho_px / 2.0],
        [0.0, focal, s.alto_px / 2.0],
        [0.0, 0.0, 1.0],
    ], dtype=np.float64)

    # La inclinación corre la cámara de lado; sigue mirando al centro.
    corrimiento = altura * math.tan(math.radians(inclinacion_grados))
    posicion = centro + np.array([0.0, -corrimiento, altura])

    return CamaraSintetica(
        posicion_mm=posicion,
        objetivo_mm=centro,
        matriz=matriz,
        ancho_px=s.ancho_px,
        alto_px=s.alto_px,
        cell_mm=t.cell_mm,
    )


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
    altura_mm: float = 0.0
    col_en_plano: float = 0.0
    row_en_plano: float = 0.0

    @property
    def paralaje_celdas(self) -> float:
        """Cuánto separa el paralaje lo que se ve de dónde está de verdad.

        Cero para cualquier cosa apoyada en el tablero. Para un objeto elevado,
        es la distancia entre su celda real y la celda donde su rayo cruza el
        plano del tablero, que es lo que el sistema mide mientras no exista la
        corrección de paralaje.
        """
        return float(math.hypot(self.col_en_plano - self.col, self.row_en_plano - self.row))


@dataclass(frozen=True, slots=True)
class CuboVerdad:
    """Dónde puso el generador un cubo. La verdad es el centro de su BASE.

    El centro de la base y no el de la mancha: es lo que el contrato publica y
    lo que el detector tiene que llegar a deducir. La base está en el piso, así
    que no la afecta el paralaje.
    """

    color: str
    col: float
    row: float
    theta_grados: float
    base_px: tuple[tuple[float, float], ...]
    tapa_px: tuple[tuple[float, float], ...]


@dataclass(frozen=True, slots=True, eq=False)
class VerdadTablero:
    """Todo lo que el generador sabe de la imagen que acaba de crear.

    `eq=False` porque contiene una cámara con matrices de NumPy adentro:
    comparar dos verdades con `==` no tendría un resultado booleano claro, y no
    lo necesitamos.
    """

    ancho_px: int
    alto_px: int
    cols: int
    rows: int
    cell_mm: float
    px_por_celda: float
    camara: CamaraSintetica
    con_perspectiva: bool
    esquinas: tuple[MarcadorVerdad, ...]
    rovers: tuple[MarcadorVerdad, ...]
    cubos: tuple[CuboVerdad, ...] = ()

    @property
    def nadir_celdas(self) -> tuple[float, float]:
        """La celda bajo la cámara. La verdad contra la que se verifica la pose."""
        return self.camara.nadir_celdas

    def celda_a_pixel(self, col: float, row: float, altura_mm: float = 0.0) -> tuple[float, float]:
        """Convierte una celda al píxel donde el generador la dibujó.

        Este es **el mapeo verdadero**: lo que el módulo de geometría tiene que
        llegar a invertir a partir de la imagen sola. Toda la verificación se
        apoya en esta función.

        `altura_mm` es la altura sobre el tablero. Con 0 —lo habitual— devuelve
        dónde cae un punto del piso. Con altura, devuelve dónde se ve un objeto
        elevado, que es otro píxel: eso es el paralaje.
        """
        punto = self.celdas_a_pixeles(np.array([[col, row]], dtype=np.float64), altura_mm)
        return (float(punto[0, 0]), float(punto[0, 1]))

    def celdas_a_pixeles(self, celdas: np.ndarray, altura_mm: float = 0.0) -> np.ndarray:
        """Versión vectorizada de `celda_a_pixel`. Recibe y devuelve (N, 2)."""
        return self.camara.proyectar_celdas(celdas, altura_mm)

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


def _cuadrilatero_celdas(col: float, row: float, lado_celdas: float,
                         theta_grados: float) -> np.ndarray:
    """Las cuatro esquinas de un cuadrado en CELDAS, en orden TL, TR, BR, BL.

    En celdas y no en píxeles porque ahora hay una cámara de por medio: primero
    se sabe dónde está la cosa en el mundo y después se la proyecta. Antes las
    dos cuentas estaban mezcladas.
    """
    return _cuadrilatero((col, row), lado_celdas, theta_grados)


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
    """Genera el marcador con su zona blanca alrededor, en BGR.

    La zona blanca no es decorativa: el detector de ArUco necesita contraste en
    todo el contorno para encontrar el marcador. Sin ella, el marcador es
    invisible aunque esté perfectamente dibujado.

    Sale en color porque la imagen sintética ahora es BGR, como la que entrega
    la cámara real: los cubos tienen color y la fuente sintética tiene que
    parecerse a la que va a reemplazar.
    """
    marcador = cv2.aruco.generateImageMarker(diccionario, id_aruco, lado_px)
    total = lado_px + 2 * borde_px
    lienzo = np.full((total, total), 255, np.uint8)
    lienzo[borde_px : borde_px + lado_px, borde_px : borde_px + lado_px] = marcador
    return cv2.cvtColor(lienzo, cv2.COLOR_GRAY2BGR)


# --------------------------------------------------------------------------
# Generación
# --------------------------------------------------------------------------


def generar(
    cfg: ConfigVision,
    rovers: tuple[RoverDemo, ...] | None = None,
    perspectiva: Perspectiva | None = None,
    semilla: int = 0,
    cubos: tuple[CuboDemo, ...] | None = None,
    con_cuerpo: bool = True,
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
    lista_cubos = cfg.cubos_demo if cubos is None else cubos

    inclinacion = persp.inclinacion_grados if persp.activa else 0.0
    camara = camara_para(cfg, inclinacion)

    # Cuántos píxeles mide una celda, para reportar y para dimensionar bitmaps.
    # Con la cámara inclinada no es constante en toda la imagen, así que se toma
    # la del centro del tablero, que es representativa.
    ppc = _px_por_celda(camara, t)

    lienzo = np.full((s.alto_px, s.ancho_px, 3), s.color_fondo, np.uint8)
    if s.dibujar_grilla:
        _dibujar_grilla(lienzo, t, s, camara)

    diccionario = diccionario_aruco(cfg.marcadores_esquina.nombre_diccionario)

    # --- marcadores de esquina --------------------------------------------
    # Se dibujan derechos (theta = 90: su borde superior mira hacia arriba) y
    # AL RAS del tablero. Su orientación no se usa para nada; lo que ancla las
    # coordenadas es su centro, y su altura cero es lo que hace que la
    # homografía del plano del tablero sea exacta para ellos.
    esquinas: list[MarcadorVerdad] = []
    for id_aruco, (col, row) in sorted(cfg.marcadores_esquina.disposicion.items()):
        esquinas.append(
            _dibujar_marcador(
                lienzo, camara, diccionario, id_aruco, col, row, 90.0,
                s.lado_marcador_esquina_celdas, s.borde_blanco_celdas, ppc, 0.0,
            )
        )

    # --- cubos y rovers, de lejos a cerca ----------------------------------
    # El orden importa: lo que está más cerca de la cámara se dibuja después y
    # tapa a lo que está detrás. Es el algoritmo del pintor, y es lo que hace
    # aparecer la OCLUSIÓN sin programarla: un rover empujando un cubo le
    # esconde la arista de la base porque su chasis está en el rayo, igual que
    # en la cancha.
    altura_rover = cfg.paralaje.altura_marcador_rover_mm
    marcadores_rover: list[MarcadorVerdad] = []
    verdad_cubos: list[CuboVerdad] = []

    piezas = []
    for cubo in lista_cubos:
        piezas.append((_distancia_a_camara(camara, cubo.col, cubo.row), "cubo", cubo))
    for rover in lista_rovers:
        piezas.append((_distancia_a_camara(camara, rover.col, rover.row), "rover", rover))
    piezas.sort(key=lambda x: -x[0])  # el más lejano primero

    for _, tipo, pieza in piezas:
        if tipo == "cubo":
            verdad_cubos.append(
                _dibujar_cubo(lienzo, camara, pieza, cfg.elementos.cubos.lado_mm, s)
            )
        else:
            if con_cuerpo:
                _dibujar_cuerpo_rover(lienzo, camara, pieza, s.cuerpo_rover)
            marcadores_rover.append(
                _dibujar_marcador(
                    lienzo, camara, diccionario, pieza.id, pieza.col, pieza.row, pieza.theta,
                    s.lado_marcador_rover_celdas, s.borde_blanco_celdas, ppc, altura_rover,
                )
            )

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
        camara=camara,
        con_perspectiva=bool(inclinacion > 0),
        esquinas=tuple(esquinas),
        rovers=tuple(sorted(marcadores_rover, key=lambda m: m.id)),
        cubos=tuple(verdad_cubos),
    )
    return lienzo, verdad


def _px_por_celda(camara: CamaraSintetica, tablero) -> float:
    """Cuántos píxeles mide una celda en el centro del tablero."""
    centro = np.array([[tablero.cols / 2.0, tablero.rows / 2.0],
                       [tablero.cols / 2.0 + 1.0, tablero.rows / 2.0]], dtype=np.float64)
    p = camara.proyectar_celdas(centro)
    return float(np.hypot(p[1, 0] - p[0, 0], p[1, 1] - p[0, 1]))


def _dibujar_marcador(
    lienzo, camara, diccionario, id_aruco, col, row, theta,
    lado_celdas, borde_celdas, ppc, altura_mm
) -> MarcadorVerdad:
    """Estampa un marcador a la altura indicada y devuelve dónde quedó.

    Primero se calcula el cuadrado en **celdas** —el mundo— y recién después se
    lo proyecta con la cámara. Ese orden es el que hace que el paralaje aparezca
    solo: un marcador a 90 mm se proyecta en otro lado que el mismo marcador al
    ras, sin que haya que programar ninguna corrección.
    """
    # El cuadrilátero que se estampa incluye la zona blanca; el que se guarda
    # como verdad es el del marcador en sí, que es lo que va a detectar OpenCV.
    total_celdas = lado_celdas + 2 * borde_celdas
    esquinas_celdas = _cuadrilatero_celdas(col, row, lado_celdas, theta)
    total_esquinas = _cuadrilatero_celdas(col, row, total_celdas, theta)

    esquinas_px = camara.proyectar_celdas(esquinas_celdas, altura_mm)
    total_px = camara.proyectar_celdas(total_esquinas, altura_mm)
    centro_px = camara.proyectar_celdas(np.array([[col, row]]), altura_mm)[0]

    # Dónde PARECE estar sobre el tablero: el punto donde el rayo cámara-marcador
    # cruza el plano del piso. Es una homotecia centrada en el nadir, y es
    # exactamente lo que el sistema va a medir mientras el paralaje no se
    # corrija. Guardarlo permite separar "el detector se equivocó" de "falta la
    # corrección de paralaje", que son dos cosas muy distintas.
    en_plano = _proyectar_al_plano(camara, col, row, altura_mm)

    lado_bitmap = max(8, int(round(lado_celdas * ppc)))
    borde_bitmap = max(1, int(round(borde_celdas * ppc)))
    _estampar(
        lienzo,
        _bitmap_marcador(diccionario, id_aruco, lado_bitmap, borde_bitmap),
        total_px,
    )
    return MarcadorVerdad(
        id=id_aruco,
        col=col,
        row=row,
        theta_grados=theta,
        centro_px=(float(centro_px[0]), float(centro_px[1])),
        esquinas_px=tuple((float(x), float(y)) for x, y in esquinas_px),
        altura_mm=float(altura_mm),
        col_en_plano=en_plano[0],
        row_en_plano=en_plano[1],
    )


def _proyectar_al_plano(camara, col, row, altura_mm) -> tuple[float, float]:
    """Dónde cruza el plano del tablero el rayo que va de la cámara al objeto.

    Es la homotecia del paralaje: centro en el nadir, factor `H/(H−h)`. Vale
    para cualquier inclinación de cámara, porque el rayo solo depende del centro
    óptico y no de hacia dónde mire.
    """
    if altura_mm == 0.0:
        return (float(col), float(row))
    nadir_col, nadir_row = camara.nadir_celdas
    k = camara.altura_mm / (camara.altura_mm - altura_mm)
    return (float(nadir_col + (col - nadir_col) * k),
            float(nadir_row + (row - nadir_row) * k))


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


def _dibujar_cubo(lienzo, camara, cubo: CuboDemo, lado_mm: float, sintetico) -> CuboVerdad:
    """Dibuja un cubo como caja 3D y devuelve dónde está su base.

    Un cubo NO se ve como un cuadrado de color: se ve como su **tapa más una o
    dos caras laterales**, y la tapa aparece corrida hacia afuera del punto bajo
    la cámara porque está a 60 mm de altura. Dibujarlo así es lo que le da al
    detector un problema de verdad que resolver.

    La silueta es el **casco convexo** de los ocho vértices proyectados, porque
    un cubo es convexo y el contorno de un cuerpo convexo es el casco de sus
    vértices. Se rellena con el tono lateral y encima se pinta la tapa más
    clara, que es lo que hace la luz.
    """
    lado_celdas = lado_mm / camara.cell_mm
    base = _cuadrilatero_celdas(cubo.col, cubo.row, lado_celdas, cubo.theta)
    base_px = camara.proyectar_celdas(base, 0.0)
    tapa_px = camara.proyectar_celdas(base, lado_mm)

    color = sintetico.colores_cubo_bgr[cubo.color]
    lateral = tuple(int(round(c * sintetico.brillo_lateral)) for c in color)
    tapa = tuple(min(255, int(round(c * sintetico.brillo_tapa))) for c in color)

    silueta = cv2.convexHull(np.vstack((base_px, tapa_px)).astype(np.float32))
    cv2.fillConvexPoly(lienzo, silueta.astype(np.int32), lateral, cv2.LINE_AA)
    cv2.fillConvexPoly(lienzo, tapa_px.astype(np.int32), tapa, cv2.LINE_AA)

    return CuboVerdad(
        color=cubo.color, col=cubo.col, row=cubo.row, theta_grados=cubo.theta,
        base_px=tuple((float(x), float(y)) for x, y in base_px),
        tapa_px=tuple((float(x), float(y)) for x, y in tapa_px),
    )


def _dibujar_cuerpo_rover(lienzo, camara, rover: RoverDemo, cuerpo) -> None:
    """Dibuja el chasis negro del rover, que es lo que TAPA.

    Sin cuerpo no hay oclusión que simular, y sin oclusión no se puede verificar
    el caso más frecuente del juego: el rover empujando un cubo hacia una zona
    de acopio, con su chasis del lado del centro de la cancha, escondiéndole al
    cubo justo la arista de la base que el detector querría usar.

    El chasis es negro: croma casi cero. Por eso NO se confunde con un cubo al
    segmentar por color — el problema que genera es de **recorte del contorno**,
    no de manchas que se mezclan.
    """
    rad = math.radians(rover.theta)
    # Ejes del robot en celdas: adelante y a la izquierda.
    fx, fy = math.cos(rad), -math.sin(rad)
    ux, uy = -fy, fx
    medio_largo = cuerpo.largo_mm / 2.0 / camara.cell_mm
    medio_ancho = cuerpo.ancho_mm / 2.0 / camara.cell_mm
    esquinas = np.array([
        [rover.col + a * medio_largo * fx + b * medio_ancho * ux,
         rover.row + a * medio_largo * fy + b * medio_ancho * uy]
        for a, b in ((1, -1), (1, 1), (-1, 1), (-1, -1))
    ], dtype=np.float64)

    base_px = camara.proyectar_celdas(esquinas, 0.0)
    tapa_px = camara.proyectar_celdas(esquinas, cuerpo.alto_mm)
    gris = (cuerpo.gris,) * 3
    silueta = cv2.convexHull(np.vstack((base_px, tapa_px)).astype(np.float32))
    cv2.fillConvexPoly(lienzo, silueta.astype(np.int32), gris, cv2.LINE_AA)
    cv2.fillConvexPoly(lienzo, tapa_px.astype(np.int32), tuple(min(255, g + 18) for g in gris),
                       cv2.LINE_AA)


def _distancia_a_camara(camara, col, row) -> float:
    """Distancia del centro óptico a un punto del tablero. Ordena el dibujado."""
    punto = camara.celdas_a_mundo(np.array([[col, row]]), 0.0)[0]
    return float(np.linalg.norm(punto - camara.posicion_mm))


def _dibujar_grilla(lienzo, tablero, sintetico, camara) -> None:
    """Dibuja la grilla tenue. Es ayuda visual: no interviene en la detección.

    Las líneas se proyectan por sus extremos porque una recta del mundo se ve
    como una recta en la imagen: la cámara no la curva. Lo que sí la curvaría es
    la distorsión del lente, que el generador no simula a propósito —el sistema
    real la corrige antes de mirar nada, así que la imagen sintética representa
    el cuadro **ya rectificado**.
    """
    paso = max(1, sintetico.paso_grilla_celdas)
    color = (int(sintetico.color_grilla),) * 3
    lineas = []
    for col in range(0, tablero.cols + 1, paso):
        lineas.append(((col, 0), (col, tablero.rows)))
    for row in range(0, tablero.rows + 1, paso):
        lineas.append(((0, row), (tablero.cols, row)))
    for inicio, fin in lineas:
        p = camara.proyectar_celdas(np.array([inicio, fin], dtype=np.float64))
        cv2.line(lienzo,
                 (int(round(p[0, 0])), int(round(p[0, 1]))),
                 (int(round(p[1, 0])), int(round(p[1, 1]))),
                 color, 1, cv2.LINE_AA)
