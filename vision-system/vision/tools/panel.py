"""Dibujado del panel de información que las herramientas superponen al video.

Por qué existe este módulo
--------------------------
`cv2.putText` usa las fuentes **Hershey**, que solo tienen tabla ASCII. Al
pasarle "exposición" dibuja un signo por cada byte del carácter multibyte —de
ahí el `exposici??n`— y **no avisa**: escribe mal en silencio. Como el proyecto
es todo en español, eso deja los paneles ilegibles.

La solución es rasterizar el texto con una fuente TrueType real. Se usa
**Pillow**, que es la forma estándar de poner texto Unicode sobre una imagen;
`cv2.freetype`, que sería el camino nativo de OpenCV, no viene compilado en la
rueda de `opencv-contrib-python`.

Pillow es opcional
------------------
Si no está instalado, el panel se dibuja igual con `cv2.putText`
**transliterando los acentos** ("exposición" -> "exposicion"). Se ve peor pero
funciona: así una instalación incompleta degrada la presentación en vez de
romper la herramienta.

Está aparte de las herramientas porque `diagnostico_camara.py` y
`calibrar_camara.py` tienen el mismo problema y el mismo panel, y no tiene
sentido resolverlo dos veces.
"""

from __future__ import annotations

import sys
import unicodedata
from dataclasses import dataclass

import cv2
import numpy as np

try:
    from PIL import Image, ImageDraw, ImageFont

    HAY_PILLOW = True
except ImportError:  # degradación consciente, ver el docstring del módulo
    HAY_PILLOW = False


# --------------------------------------------------------------------------
# Paleta
#
# El estado se comunica por color ANTES que por texto: en una herramienta que se
# mira de reojo mientras uno mueve la cámara, el color se lee de un vistazo y la
# palabra recién después.
# --------------------------------------------------------------------------

VERDE = (62, 207, 107)  # todo bien
ROJO = (255, 92, 92)  # hay un problema
AMBAR = (255, 176, 32)  # no se pudo determinar
BLANCO = (238, 240, 243)  # dato principal
GRIS = (150, 158, 168)  # dato secundario
TENUE = (108, 116, 128)  # título y pie

_FONDO = (18, 20, 24)
_ALFA_FONDO = 0.82
_SEPARADOR = (58, 64, 72)

#: Dónde buscar una fuente, por sistema operativo. La primera que cargue gana.
_FUENTES = {
    "darwin": [
        ("/System/Library/Fonts/Supplemental/Arial.ttf",
         "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        ("/System/Library/Fonts/HelveticaNeue.ttc", None),
        ("/System/Library/Fonts/Helvetica.ttc", None),
    ],
    "win32": [
        ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
        ("C:/Windows/Fonts/calibri.ttf", "C:/Windows/Fonts/calibrib.ttf"),
    ],
    "linux": [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ],
}

#: Caracteres que se reemplazan cuando hay que caer a `cv2.putText`.
# El grado no tiene descomposición Unicode a ASCII: sin equivalencia explícita
# desaparece del texto, y "29.4" a secas no dice que sean grados.
_EQUIVALENTES = {"●": "*", "·": "-", "×": "x", "─": "-", "✓": "OK", "✗": "X",
                 "⚠": "!", "°": " deg"}


def sin_acentos(texto: str) -> str:
    """Deja el texto en ASCII puro, para cuando hay que usar `cv2.putText`.

    Se sustituyen primero los símbolos que no tienen descomposición Unicode y
    después se quitan los diacríticos: "exposición" queda "exposicion", que se
    lee mal pero se lee.
    """
    for original, reemplazo in _EQUIVALENTES.items():
        texto = texto.replace(original, reemplazo)
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


class Tipografia:
    """Carga la fuente una vez y la sirve en los tamaños que usa el panel.

    Cargar una fuente TrueType no es gratis, y el panel se dibuja en cada cuadro:
    si se cargara cada vez, el visor perdería cuadros por dibujar texto.
    """

    def __init__(self, escala: float = 1.0, ruta: str | None = None):
        self.escala = escala
        self.disponible = HAY_PILLOW
        self._cache: dict[tuple[int, bool], object] = {}
        self._regular, self._negrita = (ruta, None) if ruta else self._buscar()

    @staticmethod
    def _buscar() -> tuple[str | None, str | None]:
        import os

        familia = "win32" if sys.platform.startswith("win") else (
            "darwin" if sys.platform == "darwin" else "linux")
        for regular, negrita in _FUENTES.get(familia, []):
            if os.path.exists(regular):
                return regular, (negrita if negrita and os.path.exists(negrita) else None)
        return None, None

    def de(self, tamano: int, negrita: bool = False):
        """Devuelve la fuente del tamaño pedido, ya escalada."""
        if not HAY_PILLOW:
            return None
        px = max(8, int(round(tamano * self.escala)))
        clave = (px, negrita)
        if clave not in self._cache:
            ruta = self._negrita if (negrita and self._negrita) else self._regular
            try:
                self._cache[clave] = ImageFont.truetype(ruta, px) if ruta else \
                    ImageFont.load_default(px)
            except Exception:  # noqa: BLE001 — si la fuente falla, no se cae el visor
                self._cache[clave] = ImageFont.load_default(px)
        return self._cache[clave]


# --------------------------------------------------------------------------
# Filas del panel
# --------------------------------------------------------------------------


@dataclass
class _Fila:
    tipo: str
    texto: str = ""
    color: tuple[int, int, int] = BLANCO
    etiqueta: str = ""
    tamano: int = 13
    negrita: bool = False


class Panel:
    """Acumula filas y las dibuja como un bloque prolijo sobre la imagen.

    Se mide el contenido y el panel se dimensiona en consecuencia, en vez de usar
    un ancho fijo: **tapa el mínimo de video necesario**, que en una herramienta
    donde lo que importa es ver la cámara no es un detalle estético.
    """

    def __init__(self, tipografia: Tipografia):
        self.tipo = tipografia
        self._filas: list[_Fila] = []

    # -- construcción ------------------------------------------------------

    def titulo(self, texto: str) -> "Panel":
        self._filas.append(_Fila("texto", texto.upper(), TENUE, tamano=11))
        return self

    def destacado(self, texto: str, color=BLANCO, subtexto: str = "") -> "Panel":
        """El dato que hay que poder leer de reojo, sin buscarlo."""
        self._filas.append(_Fila("texto", texto, color, tamano=24, negrita=True))
        if subtexto:
            self._filas.append(_Fila("texto", subtexto, GRIS, tamano=12))
        return self

    def datos(self, texto: str, color=BLANCO) -> "Panel":
        self._filas.append(_Fila("texto", texto, color, tamano=13))
        return self

    def estado(self, etiqueta: str, texto: str, color) -> "Panel":
        """Una fila etiqueta/estado, con el punto de color adelante del estado."""
        self._filas.append(_Fila("estado", texto, color, etiqueta=etiqueta, tamano=13))
        return self

    def separador(self) -> "Panel":
        self._filas.append(_Fila("separador"))
        return self

    def pie(self, texto: str) -> "Panel":
        self._filas.append(_Fila("texto", texto, TENUE, tamano=11))
        return self

    # -- dibujado ----------------------------------------------------------

    def dibujar(self, imagen: np.ndarray, x: int = 16, y: int = 16) -> None:
        if self.tipo.disponible:
            self._dibujar_pillow(imagen, x, y)
        else:
            self._dibujar_opencv(imagen, x, y)

    def _medidas(self):
        """Calcula alto de cada fila y ancho necesario, midiendo el texto real."""
        lienzo = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        alto = 0
        ancho = 0
        alturas = []
        col_etiqueta = 0
        for fila in self._filas:
            if fila.tipo == "separador":
                alturas.append(int(13 * self.tipo.escala))
                continue
            fuente = self.tipo.de(fila.tamano, fila.negrita)
            h = int(fila.tamano * self.tipo.escala * 1.62)
            alturas.append(h)
            if fila.tipo == "estado":
                col_etiqueta = max(col_etiqueta, lienzo.textlength(fila.etiqueta, font=fuente))
                ancho = max(ancho, col_etiqueta + lienzo.textlength("  ●  " + fila.texto, font=fuente))
            else:
                ancho = max(ancho, lienzo.textlength(fila.texto, font=fuente))
        alto = sum(alturas)
        return alturas, int(ancho), alto, int(col_etiqueta)

    def _dibujar_pillow(self, imagen: np.ndarray, x: int, y: int) -> None:
        alturas, ancho_texto, alto_texto, col_etiqueta = self._medidas()
        pad = int(18 * self.tipo.escala)
        ancho = ancho_texto + 2 * pad
        alto = alto_texto + 2 * pad
        alto_img, ancho_img = imagen.shape[:2]
        ancho = min(ancho, ancho_img - 2 * x)
        alto = min(alto, alto_img - 2 * y)

        capa = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
        dibujo = ImageDraw.Draw(capa)
        radio = int(14 * self.tipo.escala)
        dibujo.rounded_rectangle(
            [0, 0, ancho - 1, alto - 1], radius=radio,
            fill=_FONDO + (int(255 * _ALFA_FONDO),),
        )

        cursor = pad
        for fila, h in zip(self._filas, alturas):
            if fila.tipo == "separador":
                medio = cursor + h // 2
                dibujo.line([pad, medio, ancho - pad, medio], fill=_SEPARADOR + (200,), width=1)
            elif fila.tipo == "estado":
                fuente = self.tipo.de(fila.tamano, False)
                dibujo.text((pad, cursor), fila.etiqueta, font=fuente, fill=GRIS + (255,))
                punto_x = pad + col_etiqueta + int(14 * self.tipo.escala)
                radio_punto = max(3, int(4 * self.tipo.escala))
                centro_y = cursor + int(fila.tamano * self.tipo.escala * 0.62)
                dibujo.ellipse(
                    [punto_x, centro_y - radio_punto, punto_x + 2 * radio_punto,
                     centro_y + radio_punto], fill=fila.color + (255,),
                )
                dibujo.text((punto_x + 3 * radio_punto, cursor), fila.texto,
                            font=fuente, fill=fila.color + (255,))
            else:
                fuente = self.tipo.de(fila.tamano, fila.negrita)
                dibujo.text((pad, cursor), fila.texto, font=fuente, fill=fila.color + (255,))
            cursor += h

        self._componer(imagen, capa, x, y)

    @staticmethod
    def _componer(imagen: np.ndarray, capa, x: int, y: int) -> None:
        """Mezcla la capa RGBA sobre la imagen BGR, solo en la zona del panel.

        Se compone únicamente el rectángulo del panel y no la imagen entera: a 30
        cuadros por segundo sobre 1080p, convertir todo el cuadro a RGB y de
        vuelta costaría más que dibujar.
        """
        superpuesta = np.array(capa)
        alto, ancho = superpuesta.shape[:2]
        if y + alto > imagen.shape[0] or x + ancho > imagen.shape[1]:
            return
        alfa = superpuesta[:, :, 3:4].astype(np.float32) / 255.0
        color_bgr = superpuesta[:, :, 2::-1].astype(np.float32)
        region = imagen[y:y + alto, x:x + ancho].astype(np.float32)
        imagen[y:y + alto, x:x + ancho] = (region * (1 - alfa) + color_bgr * alfa).astype(np.uint8)

    def _dibujar_opencv(self, imagen: np.ndarray, x: int, y: int) -> None:
        """Respaldo sin Pillow: mismo contenido, sin acentos y sin tipografía."""
        escala = self.tipo.escala
        alto_linea = int(24 * escala)
        filas = [f for f in self._filas]
        alto = alto_linea * len(filas) + int(24 * escala)
        ancho = int(560 * escala)
        capa = imagen.copy()
        cv2.rectangle(capa, (x, y), (x + ancho, y + alto), _FONDO[::-1], -1)
        cv2.addWeighted(capa, _ALFA_FONDO, imagen, 1 - _ALFA_FONDO, 0, imagen)
        cursor = y + int(26 * escala)
        for fila in filas:
            if fila.tipo == "separador":
                cv2.line(imagen, (x + 14, cursor - 6), (x + ancho - 14, cursor - 6),
                         _SEPARADOR[::-1], 1)
            else:
                texto = fila.texto if fila.tipo != "estado" else \
                    "{:<22} {}".format(fila.etiqueta, fila.texto)
                cv2.putText(imagen, sin_acentos(texto), (x + 16, cursor),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.019 * fila.tamano * escala,
                            fila.color[::-1], 1, cv2.LINE_AA)
            cursor += alto_linea


def escala_para(alto_imagen: int) -> float:
    """Cuánto agrandar el panel según la resolución.

    Un panel pensado para 1080p se vuelve ilegible a 480p y ridículo a 4K. Se
    escala con el alto para que se vea igual de bien en cualquier cámara.
    """
    return max(0.72, min(1.6, alto_imagen / 1080.0))
