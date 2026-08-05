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

import glob
import json
import math
import os
import re
import sys
import unicodedata
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

    # -- huella del aparato -----------------------------------------------
    #
    # OpenCV no expone el nombre del dispositivo, así que un perfil no puede
    # decir con certeza a qué cámara pertenece. Lo que sí puede es describir el
    # aparato que midió: con qué resolución se calibró y qué campo de visión
    # tiene el lente. Eso alcanza para SOSPECHAR que un perfil no corresponde,
    # que es lo que faltaba cuando la C270 se corrigió con el perfil de la
    # CAM40 y nadie se enteró hasta ver la imagen deformada.
    #
    # El campo de visión se DEDUCE de la matriz en vez de guardarse: así los
    # perfiles hechos antes de este cambio lo tienen igual, sin reescribirlos.

    @property
    def fov_horizontal(self) -> float:
        return 2.0 * math.degrees(math.atan(self.ancho / (2.0 * self.matriz[0, 0])))

    @property
    def fov_vertical(self) -> float:
        return 2.0 * math.degrees(math.atan(self.alto / (2.0 * self.matriz[1, 1])))

    @property
    def fov_diagonal(self) -> float:
        mitad = math.hypot(self.ancho / (2.0 * self.matriz[0, 0]),
                           self.alto / (2.0 * self.matriz[1, 1]))
        return 2.0 * math.degrees(math.atan(mitad))

    @property
    def aspecto(self) -> float:
        return self.ancho / float(self.alto)

    @property
    def desplazamiento_borde_px(self) -> float:
        """Cuánto mueve esta corrección un píxel de la esquina.

        Es la medida de "qué tan fuerte" es el perfil. Un valor grande sobre una
        cámara que no distorsiona tanto es exactamente lo que deforma la imagen.
        """
        c = self.coeficientes.ravel()
        k1 = c[0] if len(c) > 0 else 0.0
        k2 = c[1] if len(c) > 1 else 0.0
        k3 = c[4] if len(c) > 4 else 0.0
        r = math.hypot(self.ancho / (2.0 * self.matriz[0, 0]),
                       self.alto / (2.0 * self.matriz[1, 1]))
        factor = 1.0 + k1 * r ** 2 + k2 * r ** 4 + k3 * r ** 6
        return abs(math.hypot(self.ancho / 2.0, self.alto / 2.0) * (factor - 1.0))

    @property
    def huella(self) -> str:
        """Una línea que describe el aparato, para poder compararlo de un vistazo."""
        return "{}x{}  ·  {:.0f}° diagonal  ·  corrección de {:.0f} px en el borde".format(
            self.ancho, self.alto, self.fov_diagonal, self.desplazamiento_borde_px)

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
            # Estos dos se guardan solo para que el archivo se pueda leer a ojo;
            # al cargar se recalculan, así que un perfil viejo sin ellos vale
            # exactamente igual.
            "campo_vision_grados": {
                "horizontal": round(self.fov_horizontal, 2),
                "vertical": round(self.fov_vertical, 2),
                "diagonal": round(self.fov_diagonal, 2),
            },
            "desplazamiento_borde_px": round(self.desplazamiento_borde_px, 1),
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


@dataclass(frozen=True, slots=True)
class Compatibilidad:
    """Si un perfil parece corresponder a la cámara que está conectada.

    Es una SOSPECHA, no un veredicto: dos cámaras distintas pueden entregar la
    misma resolución, así que la huella no identifica el aparato con certeza.
    Por eso el sistema **avisa y deja seguir** en vez de bloquear: una
    identificación imperfecta que frena por un falso positivo es peor que una
    que informa y deja decidir. A veces uno quiere aplicar un perfil ajeno
    justamente para comprobar que está mal.
    """

    nivel: str  # "compatible" | "sospechoso" | "incompatible"
    motivo: str
    perfil_dice: str
    camara_dice: str
    sugerencia: str

    @property
    def hay_problema(self) -> bool:
        return self.nivel != "compatible"

    @property
    def etiqueta(self) -> str:
        return {"compatible": "el perfil corresponde",
                "sospechoso": "revisar · puede no corresponder",
                "incompatible": "EL PERFIL NO CORRESPONDE"}[self.nivel]

    def mensaje(self) -> str:
        """El aviso para consola: qué esperaba el perfil y qué hay conectado.

        Enfrentar las dos huellas es lo que permite entender *qué pasó*, en vez
        de solo enterarse de que algo anda mal.
        """
        titulo = {"compatible": "  ✓  Perfil compatible con la cámara conectada.",
                  "sospechoso": "  ⚠  REVISAR: el perfil podría no ser de esta cámara",
                  "incompatible": "  ⚠  EL PERFIL NO CORRESPONDE A ESTA CÁMARA"}[self.nivel]
        if self.nivel == "compatible":
            return titulo + ("\n     ℹ  " + self.motivo if self.motivo else "")
        return "\n".join([
            "", titulo, "",
            "     " + self.motivo, "",
            "     El perfil fue hecho con:", "        " + self.perfil_dice, "",
            "     La cámara conectada entrega:", "        " + self.camara_dice, "",
            "     " + self.sugerencia, "",
        ])


def comparar_con_camara(perfil: PerfilCamara, ancho: int, alto: int) -> Compatibilidad:
    """Contrasta la huella del perfil contra lo que entrega la cámara.

    Se acumulan TODAS las señales en vez de quedarse con la primera, porque
    suelen aparecer juntas y cada una explica una parte. El caso real que motivó
    todo esto —la C270 corregida con el perfil de la CAM40— tiene la misma
    relación de aspecto (los dos son 16:9), así que el chequeo de forma solo no
    alcanzaba: lo que lo delata es que la corrección es desproporcionada.

    Señales, de más grave a menos:

    1. **Relación de aspecto distinta**: el perfil describe un sensor de otra
       forma. Aplicarlo no corrige; deforma. Es incompatible sin vuelta.
    2. **Corrección desproporcionada**: si mueve los píxeles del borde más de un
       5 % del ancho, es un perfil de lente muy ancho. Sobre una cámara normal,
       eso es exactamente lo que se ve como imagen deformada.
    3. **Misma forma, distinto tamaño**: se escala y suele andar, pero pierde
       precisión.
    """
    perfil_dice = perfil.huella
    camara_dice = "{}x{}  ·  relación {:.3f}".format(ancho, alto, ancho / float(alto))
    calibrar = ("Para calibrar esta cámara:\n"
                "        python -m vision.tools.calibrar_camara --camara \"NOMBRE DE TU CÁMARA\"")
    aspecto_camara = ancho / float(alto)

    nivel = "compatible"
    notas = []

    if abs(aspecto_camara - perfil.aspecto) > 0.02:
        nivel = "incompatible"
        notas.append(
            "La relación de aspecto no coincide ({:.3f} en el perfil contra {:.3f} en la "
            "cámara): el perfil describe un sensor de otra forma. Aplicarlo va a DEFORMAR "
            "la imagen en vez de corregirla.".format(perfil.aspecto, aspecto_camara))
    elif (ancho, alto) != (perfil.ancho, perfil.alto):
        nivel = "sospechoso"
        notas.append(
            "El perfil se hizo a {}x{} y esta cámara entrega {}x{}: los parámetros se "
            "escalan, lo que suele andar, pero pierde precisión.".format(
                perfil.ancho, perfil.alto, ancho, alto))

    # La corrección fuerte NO levanta la alarma por sí sola: en un gran angular
    # es lo normal y correcto. Un aviso que salta siempre que se usa la CAM40
    # con su propio perfil sería ruido, y el ruido entrena a ignorar los avisos.
    # Solo AMPLIFICA una sospecha que ya existe por otro motivo; si no, queda
    # como dato informativo.
    if perfil.desplazamiento_borde_px > 0.05 * ancho:
        texto = ("La corrección es fuerte: mueve los píxeles del borde {:.0f} px, un {:.0f} % "
                 "del ancho, que es propio de un lente GRAN ANGULAR.".format(
                     perfil.desplazamiento_borde_px,
                     100.0 * perfil.desplazamiento_borde_px / ancho))
        if nivel == "compatible":
            informativo = texto + " Es lo esperable si esta cámara es gran angular."
            return Compatibilidad("compatible", informativo, perfil_dice, camara_dice, "")
        notas.append(texto + " Si esta cámara NO es gran angular, el perfil no es suyo y la "
                             "imagen va a verse PEOR que la original.")

    return Compatibilidad(nivel, "  ".join(notas), perfil_dice, camara_dice,
                          calibrar if notas else "")


# --------------------------------------------------------------------------
# Los perfiles como archivos: nombrar, listar y elegir
# --------------------------------------------------------------------------


def nombre_archivo(nombre_camara: str) -> str:
    """Convierte "Logitech C270" en "logitech_c270".

    El nombre humano se guarda dentro del perfil; el del archivo tiene que ser
    seguro en cualquier sistema de archivos y fácil de escribir en una línea de
    comandos.
    """
    texto = unicodedata.normalize("NFKD", nombre_camara).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^a-zA-Z0-9]+", "_", texto).strip("_").lower()
    return texto or "camara"


def perfiles_disponibles(carpeta: str) -> list[PerfilCamara]:
    """Todos los perfiles guardados, ordenados por nombre. Ignora los ilegibles."""
    perfiles = []
    for ruta in sorted(glob.glob(os.path.join(carpeta, "*.json"))):
        try:
            perfiles.append(cargar_perfil(ruta))
        except ErrorCalibracion:
            continue  # un archivo roto no debe impedir usar los demás
    return perfiles


def _menu_perfiles(perfiles: list[PerfilCamara], por_defecto: int) -> PerfilCamara | None:
    """Deja elegir el perfil, marcando cuál calza con la cámara conectada."""
    print()
    print("  PERFILES DE CALIBRACIÓN DISPONIBLES")
    print("  " + "-" * 72)
    for i, p in enumerate(perfiles):
        print("  [{}]  {:<20} {:<11} {:>3.0f}° diag   error {:.3f} px   {}".format(
            i, p.camara[:20], "{}x{}".format(p.ancho, p.alto), p.fov_diagonal,
            p.rms_px, p.fecha[:10]))
    print("  " + "-" * 72)
    while True:
        try:
            respuesta = input(
                "\n  Elegí el perfil para esta cámara [Enter = {}, q = salir]: ".format(
                    por_defecto)).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if respuesta in ("q", "salir"):
            return None
        if respuesta == "":
            return perfiles[por_defecto]
        if respuesta.isdigit() and 0 <= int(respuesta) < len(perfiles):
            return perfiles[int(respuesta)]
        print("  Valor inválido. Opciones: 0 a {}".format(len(perfiles) - 1))


def elegir_perfil(
    cal, base_vision: str, ancho: int | None = None, alto: int | None = None,
    nombre: str | None = None, interactivo: bool = False,
) -> PerfilCamara:
    """Decide qué perfil de calibración usar.

    La cascada, de más explícito a más automático:

    1. **`nombre` dado** (`--camara`): se usa ese y nada más. Sin ambigüedad.
    2. **Un solo perfil guardado**: se usa ese.
    3. **Varios, con terminal**: menú, preseleccionando el que coincide con la
       resolución de la cámara conectada; si ninguno coincide, el perfil por
       defecto de la configuración.
    4. **Varios, sin terminal** (modo automático): el **perfil por defecto**.

    El punto 4 es el que mantiene andando lo que ya funcionaba: el sistema
    corriendo solo nunca pregunta y carga la cámara declarada por defecto.
    """
    carpeta = cal.carpeta(base_vision)

    if nombre:
        ruta = os.path.join(carpeta, nombre_archivo(nombre) + ".json")
        if not os.path.exists(ruta):
            disponibles = [p.nombre for p in perfiles_disponibles(carpeta)]
            raise ErrorCalibracion(
                "no hay perfil para {!r} (se buscó {}).\n"
                "  Perfiles disponibles: {}\n"
                "  Para calibrar esa cámara:\n"
                "    python -m vision.tools.calibrar_camara --camara {!r}".format(
                    nombre, os.path.basename(ruta), disponibles or "ninguno", nombre)
            )
        return cargar_perfil(ruta)

    perfiles = perfiles_disponibles(carpeta)
    if not perfiles:
        raise ErrorCalibracion(
            "no hay ningún perfil de calibración en {}.\n"
            "  Hay que calibrar la cámara primero:\n"
            "    python -m vision.tools.calibrar_camara --camara \"NOMBRE DE TU CÁMARA\"".format(
                carpeta)
        )
    if len(perfiles) == 1:
        return perfiles[0]

    # Preselección: el que calza con la cámara conectada; si no, el por defecto.
    indice = 0
    if ancho and alto:
        calzan = [i for i, p in enumerate(perfiles) if (p.ancho, p.alto) == (ancho, alto)]
        if calzan:
            indice = calzan[0]
    if indice == 0 and cal.perfil_por_defecto:
        porn = [i for i, p in enumerate(perfiles) if p.nombre == cal.perfil_por_defecto]
        if porn:
            indice = porn[0]

    if interactivo:
        elegido = _menu_perfiles(perfiles, indice)
        if elegido is None:
            raise ErrorCalibracion("elección de perfil cancelada.")
        return elegido
    return perfiles[indice]


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
