"""Mide la precisión de ubicación real de una cámara sobre el tablero.

    python -m vision.tools.precision_ubicacion
    python -m vision.tools.precision_ubicacion --camara "Logitech C270"
    python -m vision.tools.precision_ubicacion --comparar

Para qué existe
---------------
La cámara buena (1080p) no se consigue en cantidad para los equipos, y las
alternativas son 720p. Hay que decidir con un número, no con una impresión, si
720p ubica los objetos con error aceptable.

**Criterio:** error máximo por debajo de 1 cm en toda la cancha. Un cubo mide
6 cm, así que 1 cm de error mantiene el objetivo dentro del cubo.

Por qué se mide una DISTANCIA y no una posición
-----------------------------------------------
Medir una posición absoluta exigiría ubicar el origen —el centro del marcador
ID 0— con precisión, y eso reintroduce el error manual que queremos evitar.
Medir un desplazamiento no necesita saber dónde está el origen: se cancela al
restar.

Y tiene una segunda virtud, que es la decisiva: **neutraliza el paralaje por
construcción**. Un objeto de altura `h` a distancia `d` del punto bajo la cámara
se ve corrido a `d · H/(H−h)`; es decir, una multiplicación alrededor de ese
punto. Las dos posiciones se escalan por el MISMO factor, así que al restarlas
el paralaje queda como un **error de escala puro**, calculable y descontable, en
vez de un corrimiento que varía con la posición y sería inseparable del error de
la cámara.

Por eso esta prueba se salva de necesitar la corrección de paralaje. El sistema
real **sí la necesita**, porque publica posiciones absolutas; sigue planificada
en `geometry/`.

Por qué se mide sobre puntos internos
-------------------------------------
Los cuatro marcadores de esquina son los que el sistema usa para definir sus
coordenadas. Medir el error sobre ellos sería corregir con las propias
respuestas: darían cero por construcción y no probarían nada. Todas las
mediciones van sobre puntos internos de la cuadrícula, independientes del ajuste.

Por qué la cuadrícula es la referencia
--------------------------------------
Cada cuadro del tablero mide exactamente 20 mm, así que la cuadrícula es una
regla ya impresa: **contar cuadros da una distancia exacta**, sin lectura que
interpretar. El único error humano queda en alinear el marcador a las líneas.
"""

from __future__ import annotations

import argparse
import datetime
import glob
import json
import math
import os
import sys
import time

import cv2
import numpy as np

try:  # como paquete
    from ..configuracion import CONFIG_POR_DEFECTO, cargar_config
    from ..geometry.coordenadas import ErrorGeometria, construir_sistema, detectar_marcadores
    from ..geometry.distorsion import (
        ErrorCalibracion, FuenteRectificada, Rectificador, comparar_con_camara, elegir_perfil,
    )
    from ..sources.camara import ErrorCamara, FuenteCamara
    from .panel import AMBAR, BLANCO, GRIS, ROJO, VERDE, Panel, Tipografia, escala_para
except ImportError:  # como script suelto
    from vision.configuracion import CONFIG_POR_DEFECTO, cargar_config  # type: ignore[no-redef]
    from vision.geometry.coordenadas import (  # type: ignore[no-redef]
        ErrorGeometria, construir_sistema, detectar_marcadores,
    )
    from vision.geometry.distorsion import (  # type: ignore[no-redef]
        ErrorCalibracion, FuenteRectificada, Rectificador, comparar_con_camara, elegir_perfil,
    )
    from vision.sources.camara import ErrorCamara, FuenteCamara  # type: ignore[no-redef]
    from vision.tools.panel import (  # type: ignore[no-redef]
        AMBAR, BLANCO, GRIS, ROJO, VERDE, Panel, Tipografia, escala_para,
    )

BASE_VISION = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_VERDE_BGR = (60, 200, 60)
_ROJO_BGR = (60, 60, 235)
_AMARILLO_BGR = (40, 200, 240)


# --------------------------------------------------------------------------
# Paralaje
# --------------------------------------------------------------------------


def factor_paralaje(altura_camara_mm: float, altura_marcador_mm: float) -> float:
    """Cuánto agranda el paralaje una distancia medida sobre el tablero.

    Devuelve `k = H/(H−h)`. La distancia que reporta el sistema viene inflada
    por ese factor, así que dividir por él deja la distancia como si el marcador
    estuviera al ras.

    Es un factor y no un corrimiento porque el paralaje escala las posiciones
    alrededor del punto bajo la cámara: al restar dos posiciones, el corrimiento
    se cancela y queda solo la escala.
    """
    if altura_marcador_mm <= 0 or altura_camara_mm <= altura_marcador_mm:
        return 1.0
    return altura_camara_mm / (altura_camara_mm - altura_marcador_mm)


# --------------------------------------------------------------------------
# Una medición
# --------------------------------------------------------------------------


class Medicion:
    """Un desplazamiento conocido medido en una zona de la cancha.

    Guarda las dos posiciones que reportó el sistema, la distancia real —que se
    conoce por contar cuadros— y de ahí sale el error, con el aporte del
    paralaje separado para que no contamine el veredicto.
    """

    def __init__(self, zona: str, direccion: str, cuadros: int, cell_mm: float, k_paralaje: float):
        self.zona = zona
        self.direccion = direccion
        self.cuadros = cuadros
        self.distancia_real_mm = cuadros * cell_mm
        self.k = k_paralaje
        self.a: tuple[float, float] | None = None  # en celdas
        self.b: tuple[float, float] | None = None
        self.ruido_a_mm = 0.0
        self.ruido_b_mm = 0.0
        self.cell_mm = cell_mm

    @property
    def completa(self) -> bool:
        return self.a is not None and self.b is not None

    @property
    def distancia_reportada_mm(self) -> float:
        dx = (self.b[0] - self.a[0]) * self.cell_mm
        dy = (self.b[1] - self.a[1]) * self.cell_mm
        return math.hypot(dx, dy)

    @property
    def distancia_sin_paralaje_mm(self) -> float:
        """La distancia como si el marcador estuviera al ras del tablero."""
        return self.distancia_reportada_mm / self.k

    @property
    def aporte_paralaje_mm(self) -> float:
        return abs(self.distancia_reportada_mm - self.distancia_sin_paralaje_mm)

    @property
    def error_mm(self) -> float:
        """El error de la CÁMARA: con el paralaje ya descontado."""
        return abs(self.distancia_sin_paralaje_mm - self.distancia_real_mm)

    @property
    def error_relativo(self) -> float:
        return self.error_mm / self.distancia_real_mm if self.distancia_real_mm else 0.0

    @property
    def ruido_mm(self) -> float:
        """Repetibilidad: cuánto tiembla la posición reportada entre cuadros."""
        return max(self.ruido_a_mm, self.ruido_b_mm)

    def a_dict(self) -> dict:
        return {
            "zona": self.zona, "direccion": self.direccion, "cuadros": self.cuadros,
            "distancia_real_mm": round(self.distancia_real_mm, 2),
            "distancia_reportada_mm": round(self.distancia_reportada_mm, 3),
            "distancia_sin_paralaje_mm": round(self.distancia_sin_paralaje_mm, 3),
            "aporte_paralaje_mm": round(self.aporte_paralaje_mm, 3),
            "error_mm": round(self.error_mm, 3),
            "error_relativo_pct": round(100 * self.error_relativo, 4),
            "ruido_mm": round(self.ruido_mm, 3),
        }


# --------------------------------------------------------------------------
# Captura de una posición
# --------------------------------------------------------------------------


def _posicion_marcador(imagen, cfg, id_prueba):
    """Detecta el marcador de prueba y devuelve su centro en píxeles, o None."""
    detectados = detectar_marcadores(imagen, cfg.marcadores_esquina.nombre_diccionario)
    if id_prueba not in detectados:
        return None, detectados
    esquinas = detectados[id_prueba]
    return esquinas.reshape(4, 2).mean(axis=0), detectados


def capturar_posicion(fuente, cfg, id_prueba, muestras, tiempo_max=8.0):
    """Promedia la posición del marcador sobre varios cuadros.

    Se promedia en vez de tomar un solo cuadro porque la detección tiene ruido:
    una sola muestra mezclaría ese temblor con el error que queremos medir. Y la
    dispersión de las muestras se devuelve como dato propio: es la
    **repetibilidad** de la cámara, que es lo que más distingue una 720p de una
    1080p.
    """
    celdas = []
    limite = time.monotonic() + tiempo_max
    while len(celdas) < muestras and time.monotonic() < limite:
        cuadro = fuente.leer()
        if cuadro is None:
            time.sleep(0.01)
            continue
        centro, _ = _posicion_marcador(cuadro.imagen, cfg, id_prueba)
        if centro is None:
            time.sleep(0.01)
            continue
        try:
            sistema = construir_sistema(cuadro.imagen, cfg)
        except ErrorGeometria:
            time.sleep(0.01)
            continue
        celdas.append(sistema.celda_de(float(centro[0]), float(centro[1])))
        time.sleep(0.005)
    if len(celdas) < max(3, muestras // 3):
        return None, 0.0
    arreglo = np.array(celdas)
    media = arreglo.mean(axis=0)
    ruido_mm = float(np.linalg.norm(arreglo - media, axis=1).std()) * cfg.tablero.cell_mm
    return (float(media[0]), float(media[1])), ruido_mm


def lejos_de_las_esquinas(celda, cfg, margen) -> bool:
    """¿El punto está suficientemente lejos de los marcadores que calibran?

    Medir el error cerca de los marcadores de esquina no probaría nada: son los
    que definen las coordenadas y ahí el ajuste es exacto por construcción.
    """
    for col, row in cfg.marcadores_esquina.disposicion.values():
        if math.hypot(celda[0] - col, celda[1] - row) < margen:
            return False
    return True


# --------------------------------------------------------------------------
# Guía y presentación
# --------------------------------------------------------------------------


_DIRECCIONES = {
    "horizontal": ("DERECHA", (1.0, 0.0)),
    "vertical": ("ABAJO", (0.0, 1.0)),
}


def plan_de_medicion(cfg):
    """Las zonas y direcciones a recorrer.

    Centro y cuatro esquinas —hacia adentro— porque el error no es uniforme y
    suele ser peor en los bordes; dos direcciones por zona porque la distorsión
    residual no afecta igual a los dos ejes.
    """
    pr = cfg.precision
    pasos = []
    for zona in pr.zonas:
        for direccion in ("horizontal", "vertical"):
            pasos.append((zona["nombre"], zona["col"], zona["row"], direccion))
    return pasos


def _resumen(mediciones, perfil, cfg, ancho, alto) -> str:
    pr = cfg.precision
    completas = [m for m in mediciones if m.completa]
    if not completas:
        return "\nNo se completó ninguna medición."

    errores = [m.error_mm for m in completas]
    ruidos = [m.ruido_mm for m in completas]
    maximo = max(errores)
    peor = completas[errores.index(maximo)]
    relativo_max = max(m.error_relativo for m in completas)
    lado_cancha = max(cfg.tablero.cols, cfg.tablero.rows) * cfg.tablero.cell_mm

    p = ["", "=" * 78,
         "RESUMEN — {} · {}x{} · perfil {}".format(perfil.camara, ancho, alto, perfil.nombre),
         "=" * 78, "",
         "  {:<16} {:<11} {:>9} {:>11} {:>9} {:>8}".format(
             "zona", "dirección", "real", "reportado", "error", "ruido"),
         "  " + "-" * 70]
    for m in completas:
        p.append("  {:<16} {:<11} {:>7.1f}mm {:>9.1f}mm {:>7.2f}mm {:>6.2f}mm".format(
            m.zona[:16], m.direccion, m.distancia_real_mm,
            m.distancia_sin_paralaje_mm, m.error_mm, m.ruido_mm))
    p += ["  " + "-" * 70, "",
          "  error máximo : {:.2f} mm   (en {}, {})".format(maximo, peor.zona, peor.direccion),
          "  error medio  : {:.2f} mm".format(sum(errores) / len(errores)),
          "  ruido típico : {:.2f} mm   (repetibilidad de la cámara)".format(
              sum(ruidos) / len(ruidos))]

    aporte = max(m.aporte_paralaje_mm for m in completas)
    p += ["",
          "  PARALAJE (descontado, no contamina el error de arriba)",
          "    altura de cámara {:.0f} mm · espesor del marcador {:.1f} mm".format(
              pr.altura_camara_mm, pr.altura_marcador_mm),
          "    factor {:.5f}  ->  aportaba hasta {:.2f} mm, ya restados".format(
              factor_paralaje(pr.altura_camara_mm, pr.altura_marcador_mm), aporte)]
    if aporte > 0.2 * pr.umbral_mm:
        p.append("    ⚠ El espesor pesa más del 20 % del umbral: conviene un marcador")
        p.append("      más fino, o medir sobre más cuadros.")

    p += ["",
          "  SI EL ERROR FUERA PROPORCIONAL, a lo ancho de la cancha ({:.0f} mm)".format(
              lado_cancha),
          "    daría ~{:.1f} mm. Medir sobre más cuadros lo confirma o lo descarta.".format(
              relativo_max * lado_cancha)]

    sirve = maximo < pr.umbral_mm
    p += ["", "=" * 78,
          "  CRITERIO: error máximo < {:.1f} mm".format(pr.umbral_mm),
          "  {}  —  {:.2f} mm, {} {:.2f} mm".format(
              "✅ ESTA CÁMARA SIRVE" if sirve else "❌ ESTA CÁMARA NO ALCANZA",
              maximo, "con margen de" if sirve else "excede por",
              abs(pr.umbral_mm - maximo)),
          "=" * 78]
    return "\n".join(p)


def guardar_sesion(mediciones, perfil, cfg, ancho, alto, ruta) -> None:
    completas = [m for m in mediciones if m.completa]
    errores = [m.error_mm for m in completas] or [0.0]
    datos = {
        "fecha": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "camara": perfil.camara,
        "perfil": perfil.nombre,
        "resolucion": {"ancho": ancho, "alto": alto},
        "umbral_mm": cfg.precision.umbral_mm,
        "altura_camara_mm": cfg.precision.altura_camara_mm,
        "altura_marcador_mm": cfg.precision.altura_marcador_mm,
        "error_maximo_mm": round(max(errores), 3),
        "error_medio_mm": round(sum(errores) / len(errores), 3),
        "ruido_medio_mm": round(
            sum(m.ruido_mm for m in completas) / max(1, len(completas)), 3),
        "sirve": max(errores) < cfg.precision.umbral_mm,
        "mediciones": [m.a_dict() for m in completas],
    }
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)
        f.write("\n")


def modo_comparar(cfg) -> int:
    """Pone lado a lado las sesiones guardadas, para decidir entre cámaras."""
    carpeta = os.path.join(BASE_VISION, cfg.precision.carpeta_mediciones)
    archivos = sorted(glob.glob(os.path.join(carpeta, "*.json")))
    if not archivos:
        print("No hay mediciones guardadas en {}".format(carpeta))
        return 1
    print("=" * 82)
    print("COMPARACIÓN DE CÁMARAS  —  criterio: error máximo < {:.1f} mm".format(
        cfg.precision.umbral_mm))
    print("=" * 82)
    print("  {:<22} {:<11} {:>9} {:>9} {:>9} {:>8}".format(
        "cámara", "resolución", "err. máx", "err. med", "ruido", "veredicto"))
    print("  " + "-" * 74)
    for a in archivos:
        try:
            d = json.load(open(a, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        print("  {:<22} {:<11} {:>7.2f}mm {:>7.2f}mm {:>7.2f}mm {:>8}".format(
            d["camara"][:22], "{}x{}".format(d["resolucion"]["ancho"], d["resolucion"]["alto"]),
            d["error_maximo_mm"], d["error_medio_mm"], d.get("ruido_medio_mm", 0.0),
            "SIRVE" if d["sirve"] else "NO"))
    print("  " + "-" * 74)
    return 0


# --------------------------------------------------------------------------
# Programa
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mide la precisión de ubicación real de una cámara sobre el tablero.")
    parser.add_argument("--config", default=CONFIG_POR_DEFECTO)
    parser.add_argument("--indice", type=int, default=None)
    parser.add_argument("--camara", default=None, help="nombre de la cámara y de su perfil")
    parser.add_argument("--umbral-mm", type=float, default=None)
    parser.add_argument("--cuadros", type=int, default=None,
                        help="cuántos cuadros de la cuadrícula mover en cada medición")
    parser.add_argument("--comparar", action="store_true",
                        help="mostrar las sesiones ya medidas y salir")
    args = parser.parse_args(argv)

    cfg = cargar_config(args.config)
    pr = cfg.precision
    umbral = args.umbral_mm or pr.umbral_mm
    cuadros = args.cuadros or pr.cuadros_por_medicion

    if args.comparar:
        return modo_comparar(cfg)

    print("=" * 78)
    print("PRECISIÓN DE UBICACIÓN")
    print("=" * 78)
    print("  criterio        : error máximo < {:.1f} mm".format(umbral))
    print("  marcador prueba : ID {} de {:.0f} mm ({:.0f} cuadros)".format(
        pr.id_marcador_prueba, pr.lado_marcador_mm, pr.lado_marcador_mm / cfg.tablero.cell_mm))
    print("  desplazamiento  : {} cuadros = {:.0f} mm".format(
        cuadros, cuadros * cfg.tablero.cell_mm))
    k = factor_paralaje(pr.altura_camara_mm, pr.altura_marcador_mm)
    print("  paralaje        : cámara a {:.0f} mm, marcador de {:.1f} mm -> factor {:.5f}".format(
        pr.altura_camara_mm, pr.altura_marcador_mm, k))
    print("                    (se descuenta; aporta {:.2f} mm sobre {:.0f} mm)".format(
        cuadros * cfg.tablero.cell_mm * (1 - 1 / k), cuadros * cfg.tablero.cell_mm))
    print()

    try:
        camara = FuenteCamara(cfg.camara, indice=args.indice)
    except ErrorCamara as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        return 2

    primero = None
    limite = time.monotonic() + 10.0
    while primero is None and time.monotonic() < limite:
        primero = camara.leer()
        time.sleep(0.01)
    if primero is None:
        print("ERROR: la cámara no entregó imágenes.", file=sys.stderr)
        camara.cerrar()
        return 2
    alto, ancho = primero.imagen.shape[:2]

    interactivo = bool(sys.stdin and sys.stdin.isatty())
    try:
        perfil = elegir_perfil(cfg.calibracion, BASE_VISION, ancho, alto,
                               nombre=args.camara, interactivo=interactivo)
    except ErrorCalibracion as exc:
        print("\nERROR: {}".format(exc), file=sys.stderr)
        camara.cerrar()
        return 2

    compat = comparar_con_camara(perfil, ancho, alto)
    print(compat.mensaje())

    # La corrección de distorsión se aplica ANTES de medir: es la misma cadena
    # que va a usar el sistema real, y medir sin ella daría un número que no
    # corresponde a nada.
    fuente = FuenteRectificada(camara, Rectificador(perfil, alpha=cfg.calibracion.alpha,
                                                    tamano=(ancho, alto)))

    pasos = plan_de_medicion(cfg)
    mediciones: list[Medicion] = []
    tipografia = Tipografia(escala_para(alto))
    ventana = "Precision de ubicacion"
    indice_paso = 0
    etapa = "A"
    actual = None
    mensaje = ""

    try:
        while indice_paso < len(pasos):
            zona, col_obj, row_obj, direccion = pasos[indice_paso]
            nombre_dir, vector = _DIRECCIONES[direccion]
            if actual is None:
                actual = Medicion(zona, direccion, cuadros, cfg.tablero.cell_mm, k)

            cuadro = fuente.leer()
            if cuadro is None:
                time.sleep(0.01)
                continue
            lienzo = cuadro.imagen.copy()
            centro, detectados = _posicion_marcador(lienzo, cfg, pr.id_marcador_prueba)

            celda_actual = None
            try:
                sistema = construir_sistema(cuadro.imagen, cfg)
                hay_esquinas = True
                if centro is not None:
                    celda_actual = sistema.celda_de(float(centro[0]), float(centro[1]))
            except ErrorGeometria:
                hay_esquinas = False

            for id_m, esq in detectados.items():
                color = (_VERDE_BGR if id_m == pr.id_marcador_prueba else _AMARILLO_BGR)
                cv2.polylines(lienzo, [esq.astype(np.int32).reshape(-1, 1, 2)], True, color, 2)

            panel = Panel(tipografia)
            panel.titulo("Precisión de ubicación · paso {} de {}".format(
                indice_paso + 1, len(pasos)))
            panel.destacado("{} · {}".format(zona, direccion), BLANCO,
                            "objetivo aproximado: celda ({:.0f}, {:.0f})".format(col_obj, row_obj))
            panel.separador()
            if etapa == "A":
                panel.datos("1) Alineá el marcador a la cuadrícula en esta zona")
                panel.datos("2) ESPACIO para capturar el punto A", GRIS)
            else:
                panel.datos("3) Movelo {} cuadros hacia {} = {:.0f} mm".format(
                    cuadros, nombre_dir, cuadros * cfg.tablero.cell_mm))
                panel.datos("4) ESPACIO para capturar el punto B", GRIS)
            panel.separador()
            panel.estado("Esquinas", "4 de 4" if hay_esquinas else "faltan marcadores",
                         VERDE if hay_esquinas else ROJO)
            panel.estado("Marcador {}".format(pr.id_marcador_prueba),
                         "celda ({:.2f}, {:.2f})".format(*celda_actual) if celda_actual
                         else "no se ve", VERDE if celda_actual else ROJO)
            if mensaje:
                panel.separador()
                panel.datos(mensaje, AMBAR)
            panel.separador()
            panel.pie("espacio capturar · r rehacer zona · s saltear · q terminar")
            panel.dibujar(lienzo)

            escala = min(1.0, 1400.0 / lienzo.shape[1])
            if escala < 1.0:
                lienzo = cv2.resize(lienzo, None, fx=escala, fy=escala,
                                    interpolation=cv2.INTER_AREA)
            try:
                cv2.imshow(ventana, lienzo)
            except cv2.error as exc:
                print("No se pudo abrir la ventana: {}".format(exc), file=sys.stderr)
                return 2
            tecla = cv2.waitKey(1) & 0xFF

            if tecla in (ord("q"), 27):
                break
            if tecla == ord("s"):
                indice_paso += 1
                actual, etapa, mensaje = None, "A", ""
                continue
            if tecla == ord("r"):
                actual, etapa, mensaje = None, "A", "zona reiniciada"
                continue
            if tecla == ord(" "):
                if not hay_esquinas:
                    mensaje = "faltan marcadores de esquina: no se puede medir"
                    continue
                posicion, ruido = capturar_posicion(
                    fuente, cfg, pr.id_marcador_prueba, pr.muestras_por_punto)
                if posicion is None:
                    mensaje = "no se pudo ver el marcador el tiempo suficiente"
                    continue
                if not lejos_de_las_esquinas(posicion, cfg, pr.margen_marcadores_celdas):
                    mensaje = ("demasiado cerca de un marcador de esquina: corré el "
                               "marcador hacia adentro")
                    continue
                if etapa == "A":
                    actual.a, actual.ruido_a_mm = posicion, ruido
                    etapa = "B"
                    mensaje = "punto A tomado (ruido {:.2f} mm)".format(ruido)
                else:
                    actual.b, actual.ruido_b_mm = posicion, ruido
                    mediciones.append(actual)
                    print("  {:<16} {:<11} real {:.0f} mm · reportado {:.1f} mm · "
                          "error {:.2f} mm · ruido {:.2f} mm".format(
                              actual.zona, actual.direccion, actual.distancia_real_mm,
                              actual.distancia_sin_paralaje_mm, actual.error_mm,
                              actual.ruido_mm))
                    indice_paso += 1
                    actual, etapa = None, "A"
                    mensaje = ""
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()

    print(_resumen(mediciones, perfil, cfg, ancho, alto))
    completas = [m for m in mediciones if m.completa]
    if completas:
        ruta = os.path.join(BASE_VISION, pr.carpeta_mediciones,
                            "{}_{}.json".format(perfil.nombre,
                                                datetime.datetime.now().strftime("%Y%m%d_%H%M")))
        guardar_sesion(mediciones, perfil, cfg, ancho, alto, ruta)
        print("\n  medición guardada en: {}".format(ruta))
        print("  Para comparar todas las cámaras medidas:")
        print("    python -m vision.tools.precision_ubicacion --comparar")
    fuente.cerrar()
    return 0 if completas and max(m.error_mm for m in completas) < umbral else 1


if __name__ == "__main__":
    sys.exit(main())
