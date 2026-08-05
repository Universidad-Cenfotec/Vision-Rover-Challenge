"""Sistema de coordenadas anclado a los cuatro marcadores de esquina.

Qué resuelve
------------
La cámara ve **píxeles**; el contrato publica **celdas**. Este módulo construye
el puente entre los dos, usando como única referencia los cuatro marcadores
ArUco pegados en las esquinas de la cancha.

Por qué una homografía y no una simple escala
---------------------------------------------
Porque la cámara real nunca va a estar perfectamente cenital. Con cualquier
inclinación, el tablero se ve como un trapecio y no como un rectángulo: una
escala daría bien en el centro y mal en los bordes. La homografía es la
transformación exacta entre dos planos vistos en perspectiva, y el tablero es
un plano. Cuatro puntos —los cuatro centros de marcador— la determinan por
completo.

Por qué los centros y no las esquinas de los marcadores
-------------------------------------------------------
El centro de un marcador es el promedio de sus cuatro esquinas detectadas, así
que promedia el ruido de las cuatro en vez de arrastrar el de una sola. Además
es lo único medible sin ambigüedad en la cancha física: "el centro del
marcador" no admite discusión, "su esquina superior izquierda" sí.

Separar detectar de decidir
---------------------------
`detectar_marcadores` solo mira la imagen y dice qué encontró. `construir_sistema`
decide si eso alcanza y arma las coordenadas. Son dos responsabilidades
distintas y fallan por motivos distintos (CLAUDE.md, sección 6).
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

try:  # como paquete
    from ..configuracion import ConfigVision, diccionario_aruco
except ImportError:  # como script suelto
    from vision.configuracion import ConfigVision, diccionario_aruco  # type: ignore[no-redef]


class ErrorGeometria(Exception):
    """No se pudo establecer el sistema de coordenadas a partir de la imagen.

    Se levanta excepción en vez de devolver `None` a propósito: un `None` que
    nadie mira se convierte en coordenadas basura publicadas como si fueran
    buenas. El "falla abierto" del CLAUDE.md se implementa **arriba**, en el
    bucle de proceso, que atrapa esto y conserva el último estado bueno; no
    obligando a cada llamador a acordarse de comprobar el retorno.
    """


@dataclass(frozen=True, slots=True, eq=False)
class SistemaCoordenadas:
    """Convierte entre píxeles de la imagen y celdas de la cancha.

    Es inmutable: cada cuadro produce el suyo. Si los marcadores se mueven —o la
    cámara se corre— el sistema del cuadro siguiente es otro objeto, y el
    anterior sigue siendo válido para lo que ya se calculó con él.

    `eq=False` porque guarda matrices de NumPy.
    """

    a_celdas_h: np.ndarray  # homografía píxeles -> celdas
    a_pixeles_h: np.ndarray  # la inversa, útil para dibujar sobre la imagen
    cols: int
    rows: int
    cell_mm: float
    centros_px: dict[int, tuple[float, float]]

    def a_celdas(self, puntos_px: np.ndarray) -> np.ndarray:
        """Convierte puntos en píxeles a celdas. Recibe y devuelve (N, 2)."""
        return _aplicar(self.a_celdas_h, puntos_px)

    def a_pixeles(self, celdas: np.ndarray) -> np.ndarray:
        """Convierte celdas a píxeles. Recibe y devuelve (N, 2)."""
        return _aplicar(self.a_pixeles_h, celdas)

    def celda_de(self, x: float, y: float) -> tuple[float, float]:
        """Versión cómoda para un solo punto."""
        p = self.a_celdas(np.array([[x, y]], dtype=np.float64))
        return (float(p[0, 0]), float(p[0, 1]))


def _aplicar(h: np.ndarray, puntos: np.ndarray) -> np.ndarray:
    puntos = np.asarray(puntos, dtype=np.float64).reshape(-1, 1, 2)
    return cv2.perspectiveTransform(puntos, h).reshape(-1, 2)


def detectar_marcadores(imagen: np.ndarray, nombre_diccionario: str) -> dict[int, np.ndarray]:
    """Detecta todos los marcadores ArUco de la imagen.

    Devuelve `{id: esquinas}` con las esquinas como (4, 2) en orden TL, TR, BR,
    BL. No juzga si son los que hacen falta: eso es decidir, y lo hace
    `construir_sistema`.
    """
    if imagen.ndim == 3:
        imagen = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    detector = cv2.aruco.ArucoDetector(
        diccionario_aruco(nombre_diccionario), cv2.aruco.DetectorParameters()
    )
    esquinas, ids, _ = detector.detectMarkers(imagen)
    if ids is None:
        return {}
    return {
        int(id_aruco): esquina.reshape(4, 2).astype(np.float64)
        for id_aruco, esquina in zip(ids.ravel(), esquinas)
    }


def centro_de(esquinas: np.ndarray) -> tuple[float, float]:
    """Centro de un marcador: el promedio de sus cuatro esquinas.

    Promediar las cuatro reparte el ruido de detección en vez de confiar en una
    sola esquina.
    """
    c = np.asarray(esquinas, dtype=np.float64).reshape(4, 2).mean(axis=0)
    return (float(c[0]), float(c[1]))


def construir_sistema(imagen: np.ndarray, cfg: ConfigVision) -> SistemaCoordenadas:
    """Establece el sistema de coordenadas de la cancha a partir de una imagen.

    Exige los cuatro marcadores de esquina. Con tres no alcanza: una homografía
    necesita cuatro correspondencias, y con menos habría que suponer cosas sobre
    la cámara que no queremos suponer.
    """
    detectados = detectar_marcadores(imagen, cfg.marcadores_esquina.nombre_diccionario)
    esperados = cfg.marcadores_esquina.ids_esperados
    faltantes = sorted(esperados - set(detectados))
    if faltantes:
        raise ErrorGeometria(
            "faltan marcadores de esquina: se esperaban {} y se detectaron {}. "
            "Revisar que los cuatro estén planos, completos, iluminados y con su "
            "zona blanca sin tapar.".format(sorted(esperados), sorted(detectados))
        )

    # El orden importa: cada centro en píxeles tiene que corresponderse con la
    # celda de SU marcador. Se recorre por ID para que no dependa del orden en
    # que el detector los haya devuelto.
    ids = sorted(esperados)
    origen_px = np.array([centro_de(detectados[i]) for i in ids], dtype=np.float32)
    destino_celdas = np.array(
        [cfg.marcadores_esquina.disposicion[i] for i in ids], dtype=np.float32
    )

    a_celdas_h = cv2.getPerspectiveTransform(origen_px, destino_celdas).astype(np.float64)
    a_pixeles_h = cv2.getPerspectiveTransform(destino_celdas, origen_px).astype(np.float64)

    return SistemaCoordenadas(
        a_celdas_h=a_celdas_h,
        a_pixeles_h=a_pixeles_h,
        cols=cfg.tablero.cols,
        rows=cfg.tablero.rows,
        cell_mm=cfg.tablero.cell_mm,
        centros_px={i: centro_de(detectados[i]) for i in ids},
    )
