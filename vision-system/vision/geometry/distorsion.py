"""Corrección de la distorsión del lente.

Qué resuelve
------------
Un lente gran angular **curva las líneas rectas**, y cada vez más cerca de los
bordes. Sin corregirlo, un marcador pegado en una esquina de la cancha aparece
corrido respecto de donde está de verdad, y esa diferencia se traslada tal cual
a las coordenadas que publicamos.

La homografía de `coordenadas.py` **no puede arreglar esto**: una homografía
describe cómo se ve un plano desde otro ángulo, y es exacta para eso, pero
supone que las rectas siguen siendo rectas. La distorsión rompe justamente esa
suposición, así que hay que quitarla antes.

Dónde encaja
------------
Es una capa **previa** a todo lo demás::

    cámara --> [rectificar] --> detectar marcadores --> geometría de esquinas

Una vez rectificada la imagen, todo lo de abajo trabaja sobre ella: los
marcadores se detectan ahí y la homografía se calcula ahí. Por eso no hay que
reconvertir coordenadas en ningún lado. Lo único que no se puede hacer es
**mezclar** imágenes crudas y rectificadas en el mismo camino.

Por qué se precalculan los mapas
--------------------------------
`cv2.undistort` recalcula en cada llamada dónde va a parar cada píxel. Como la
transformación no cambia mientras no se mueva el lente, se calcula **una vez**
con `initUndistortRectifyMap` y después cada cuadro es solo un `remap`. A 30
cuadros por segundo sobre 1080p, esa diferencia se nota.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import cv2
import numpy as np

try:  # como paquete
    from ..sources.fuente import Cuadro
except ImportError:  # como script suelto
    from vision.sources.fuente import Cuadro  # type: ignore[no-redef]


class ErrorCalibracion(Exception):
    """El perfil de calibración falta, está incompleto o no corresponde."""


@dataclass(frozen=True, slots=True, eq=False)
class PerfilCamara:
    """El resultado de calibrar una cámara concreta.

    Es un **perfil de cámara** en el sentido del CLAUDE.md: describe un aparato
    físico, no el sistema. Guardarlo aparte permite tener varias cámaras sin
    bifurcar el código, y volver a usar una calibración sin repetirla.

    `eq=False` porque contiene matrices de NumPy.
    """

    nombre: str
    camara: str
    fecha: str
    ancho: int
    alto: int
    modelo: str
    matriz: np.ndarray  # 3x3, intrínsecos
    coeficientes: np.ndarray  # (1, N) de distorsión
    rms_px: float
    vistas: int
    patron_columnas: int
    patron_filas: int
    patron_lado_mm: float

    def a_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "camara": self.camara,
            "fecha": self.fecha,
            "resolucion": {"ancho": self.ancho, "alto": self.alto},
            "modelo": self.modelo,
            "matriz_camara": self.matriz.tolist(),
            "coeficientes_distorsion": self.coeficientes.ravel().tolist(),
            "rms_px": self.rms_px,
            "vistas": self.vistas,
            "patron": {
                "columnas_internas": self.patron_columnas,
                "filas_internas": self.patron_filas,
                "lado_mm": self.patron_lado_mm,
            },
        }

    @property
    def resumen(self) -> str:
        fx, fy = self.matriz[0, 0], self.matriz[1, 1]
        cx, cy = self.matriz[0, 2], self.matriz[1, 2]
        return (
            "{} · {}x{} · modelo {} · error {:.3f} px con {} vistas\n"
            "  distancia focal fx={:.1f} fy={:.1f} · centro óptico ({:.1f}, {:.1f})\n"
            "  coeficientes: {}".format(
                self.nombre, self.ancho, self.alto, self.modelo, self.rms_px, self.vistas,
                fx, fy, cx, cy,
                ", ".join("{:+.5f}".format(c) for c in self.coeficientes.ravel()),
            )
        )


def guardar_perfil(perfil: PerfilCamara, ruta: str) -> None:
    """Guarda el perfil como JSON legible.

    JSON y no un formato binario a propósito: un perfil de cámara se revisa a
    ojo, se compara entre calibraciones y se versiona. Un `.npz` no deja hacer
    nada de eso.
    """
    carpeta = os.path.dirname(os.path.abspath(ruta))
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(perfil.a_dict(), f, indent=2, ensure_ascii=False)
        f.write("\n")


def cargar_perfil(ruta: str) -> PerfilCamara:
    """Lee un perfil guardado. Falla con un mensaje que dice qué hacer."""
    if not os.path.exists(ruta):
        raise ErrorCalibracion(
            "no hay perfil de calibración en {}. Hay que calibrar la cámara primero:\n"
            "  python -m vision.tools.calibrar_camara".format(ruta)
        )
    with open(ruta, "r", encoding="utf-8") as f:
        d = json.load(f)
    try:
        return PerfilCamara(
            nombre=d["nombre"],
            camara=d.get("camara", "desconocida"),
            fecha=d.get("fecha", ""),
            ancho=int(d["resolucion"]["ancho"]),
            alto=int(d["resolucion"]["alto"]),
            modelo=d.get("modelo", "estandar"),
            matriz=np.array(d["matriz_camara"], dtype=np.float64),
            coeficientes=np.array(d["coeficientes_distorsion"], dtype=np.float64).reshape(1, -1),
            rms_px=float(d["rms_px"]),
            vistas=int(d.get("vistas", 0)),
            patron_columnas=int(d["patron"]["columnas_internas"]),
            patron_filas=int(d["patron"]["filas_internas"]),
            patron_lado_mm=float(d["patron"]["lado_mm"]),
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise ErrorCalibracion("el perfil {} está incompleto o dañado: {}".format(ruta, exc))


class Rectificador:
    """Quita la distorsión del lente de cada imagen.

    Los mapas se calculan una sola vez al construirlo; después cada cuadro es
    solo un `remap`, que es lo que permite hacerlo a la velocidad de la cámara.

    Sobre `alpha`
    -------------
    Controla cuánto campo visual se conserva:

    - `0` recorta a la zona donde todos los píxeles son válidos. No quedan bordes
      negros, pero se pierde algo de borde de imagen.
    - `1` conserva todo el campo, a costa de bordes negros curvados que pueden
      confundir a los detectores.

    Por defecto 0. Si con eso se pierde de vista algún marcador de esquina,
    conviene subirlo en vez de mover la cámara.
    """

    def __init__(self, perfil: PerfilCamara, alpha: float = 0.0,
                 tamano: tuple[int, int] | None = None):
        self.perfil = perfil
        self.alpha = float(alpha)
        self.tamano = tamano or (perfil.ancho, perfil.alto)
        self.escalado = self.tamano != (perfil.ancho, perfil.alto)

        matriz = perfil.matriz
        if self.escalado:
            # La calibración vale para la resolución en la que se hizo. Si la
            # cámara ahora entrega otra, los intrínsecos se escalan linealmente;
            # los coeficientes de distorsión, en cambio, no cambian porque están
            # normalizados. Escalar es correcto solo si cambió la resolución y no
            # el recorte del sensor, así que se avisa.
            sx = self.tamano[0] / perfil.ancho
            sy = self.tamano[1] / perfil.alto
            matriz = matriz.copy()
            matriz[0, 0] *= sx
            matriz[0, 2] *= sx
            matriz[1, 1] *= sy
            matriz[1, 2] *= sy

        self.matriz_original = matriz
        self.matriz_nueva, self.roi = cv2.getOptimalNewCameraMatrix(
            matriz, perfil.coeficientes, self.tamano, self.alpha, self.tamano
        )
        self._mapa_x, self._mapa_y = cv2.initUndistortRectifyMap(
            matriz, perfil.coeficientes, None, self.matriz_nueva, self.tamano, cv2.CV_16SC2
        )

    def rectificar(self, imagen: np.ndarray) -> np.ndarray:
        """Devuelve la imagen sin distorsión, del mismo tamaño que la original."""
        if (imagen.shape[1], imagen.shape[0]) != self.tamano:
            raise ErrorCalibracion(
                "la imagen es {}x{} pero el rectificador está preparado para {}x{}".format(
                    imagen.shape[1], imagen.shape[0], self.tamano[0], self.tamano[1])
            )
        return cv2.remap(imagen, self._mapa_x, self._mapa_y, cv2.INTER_LINEAR)

    @property
    def aviso(self) -> str | None:
        if self.escalado:
            return (
                "el perfil se hizo a {}x{} y la cámara entrega {}x{}: los parámetros se "
                "escalaron. Es correcto si solo cambió la resolución, pero conviene "
                "recalibrar en la resolución de trabajo.".format(
                    self.perfil.ancho, self.perfil.alto, self.tamano[0], self.tamano[1])
            )
        return None


class FuenteRectificada:
    """Envuelve una fuente de imágenes y entrega los cuadros ya corregidos.

    Cumple la misma interfaz `FuenteImagen`, así que se enchufa delante sin que
    nada de lo que viene después se entere::

        fuente = FuenteRectificada(FuenteCamara(cfg.camara), rectificador)
        cuadro = fuente.leer()          # ya viene sin distorsión

    Se hace por composición y no agregándole la corrección a `FuenteCamara`
    porque son dos responsabilidades distintas —capturar y corregir— y así la
    misma capa sirve también para la fuente sintética o para una grabación.

    La marca de tiempo y el índice **se conservan**: rectificar no cambia cuándo
    se capturó el cuadro, y esa marca es la que después mide la latencia real.
    """

    def __init__(self, fuente, rectificador: Rectificador):
        self.fuente = fuente
        self.rectificador = rectificador

    def leer(self) -> Cuadro | None:
        cuadro = self.fuente.leer()
        if cuadro is None:
            return None
        return Cuadro(
            imagen=self.rectificador.rectificar(cuadro.imagen),
            ts_ms=cuadro.ts_ms,
            indice=cuadro.indice,
        )

    def cerrar(self) -> None:
        self.fuente.cerrar()

    def __getattr__(self, nombre):
        """Deja pasar lo que sea propio de la fuente envuelta (fps, informes...).

        Así el diagnóstico y las herramientas siguen viendo `fps_real` o
        `formato_negociado` aunque haya una capa en el medio.
        """
        return getattr(self.fuente, nombre)

    def __enter__(self) -> "FuenteRectificada":
        return self

    def __exit__(self, *_) -> None:
        self.cerrar()


def rectificador_desde_config(cfg, base_vision: str, tamano: tuple[int, int] | None = None):
    """Atajo: carga el perfil que indica la configuración y arma el rectificador.

    Devuelve `None` si todavía no hay calibración, para que quien lo use pueda
    seguir trabajando sin corrección en vez de quedar bloqueado.
    """
    ruta = cfg.calibracion.ruta_perfil(base_vision)
    if not os.path.exists(ruta):
        return None
    return Rectificador(cargar_perfil(ruta), alpha=cfg.calibracion.alpha, tamano=tamano)
