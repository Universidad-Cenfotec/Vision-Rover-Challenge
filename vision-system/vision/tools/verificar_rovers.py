"""Verifica la detección de rovers contra la verdad del generador sintético.

Cómo se corre:

    python -m vision.tools.verificar_rovers
    python -m vision.tools.verificar_rovers --salida /tmp/rovers.png --anotar

Por qué la prueba está armada así
---------------------------------
El generador sintético dibuja los marcadores de los rovers **sabiendo
exactamente** en qué celda y con qué ángulo los puso. Esa verdad es lo que
permite decir "está bien" en vez de "no explotó".

Se corre en los dos modos, cenital y con perspectiva, porque son pruebas
distintas: sin inclinación la homografía degenera en una escala y el ángulo
sale bien casi por accidente. Recién con la cámara inclinada se pone a prueba
lo que de verdad importa, que es calcular la orientación **en celdas y no en
píxeles**.

Los cuatro escenarios
---------------------
1. **Los dos rovers de la configuración.** El caso de todos los días.
2. **Cinco rovers repartidos.** Confirma que cada uno se corresponde con SU ID:
   no alcanza con que los errores sean chicos, hay que descartar que dos rovers
   se hayan intercambiado la identidad.
3. **Ángulos en el borde del círculo** (0°, 0,5°, 359,5°, 90°, 180°). Es la
   trampa clásica: 359,5° y 0,5° están a un grado, y una resta ingenua diría
   359. Este escenario imprime las dos cuentas al lado para que se vea.
4. **Barrido de ángulos cada 10°.** Que el ángulo esté bien en todo el círculo
   y no solo cerca de donde uno probó.
"""

from __future__ import annotations

import argparse
import math
import sys

import cv2
import numpy as np

try:  # como paquete
    from ..configuracion import Perspectiva, RoverDemo, cargar_config
    from ..detectors.rovers import detectar_rovers, diferencia_angular
    from ..geometry.coordenadas import ErrorGeometria, construir_sistema, detectar_marcadores
    from ..sources.generador_sintetico import generar
except ImportError:  # como script suelto
    from vision.configuracion import (  # type: ignore[no-redef]
        Perspectiva,
        RoverDemo,
        cargar_config,
    )
    from vision.detectors.rovers import (  # type: ignore[no-redef]
        detectar_rovers,
        diferencia_angular,
    )
    from vision.geometry.coordenadas import (  # type: ignore[no-redef]
        ErrorGeometria,
        construir_sistema,
        detectar_marcadores,
    )
    from vision.sources.generador_sintetico import generar  # type: ignore[no-redef]


# --------------------------------------------------------------------------
# Los escenarios
# --------------------------------------------------------------------------


def escenario_multi_rover() -> tuple[RoverDemo, ...]:
    """Cinco rovers con IDs y ángulos distintos, bien separados entre sí.

    Separados a propósito: si estuvieran encimados, un error de identidad
    quedaría tapado por la cercanía. Acá, confundir dos rovers da un error de
    decenas de celdas, imposible de pasar por alto.
    """
    ubicaciones = (
        (10, 8.0, 8.0, 0.0),
        (11, 34.0, 8.0, 75.0),
        (12, 21.5, 21.5, 150.0),
        (13, 8.0, 34.0, 225.0),
        (14, 34.0, 34.0, 300.0),
    )
    return tuple(RoverDemo(id=i, col=c, row=r, theta=t) for i, c, r, t in ubicaciones)


def escenario_salto_angular() -> tuple[RoverDemo, ...]:
    """Ángulos elegidos alrededor del cierre del círculo.

    0° y 359,5° están a medio grado, del lado opuesto de la costura. Si el
    cálculo del ángulo o la medición del error se equivocan ahí, este escenario
    lo grita.
    """
    angulos = (0.0, 0.5, 359.5, 90.0, 180.0)
    posiciones = ((10.0, 10.0), (21.5, 10.0), (33.0, 10.0), (10.0, 25.0), (21.5, 25.0))
    return tuple(
        RoverDemo(id=10 + k, col=c, row=r, theta=t)
        for k, (t, (c, r)) in enumerate(zip(angulos, posiciones))
    )


def escenario_barrido() -> tuple[RoverDemo, ...]:
    """Un rover por cada 10° del círculo, en una rejilla de 6x6.

    Treinta y seis rovers a la vez es una situación que nunca va a pasar en la
    cancha, y justamente por eso sirve: si el ángulo estuviera bien solo en
    algún cuadrante, acá se ve de una.
    """
    coordenadas = (6.0, 12.0, 18.0, 24.0, 30.0, 36.0)
    rovers = []
    k = 0
    for row in coordenadas:
        for col in coordenadas:
            rovers.append(RoverDemo(id=4 + k, col=col, row=row, theta=float(k * 10)))
            k += 1
    return tuple(rovers)


def escenarios(cfg) -> list[tuple[str, tuple[RoverDemo, ...]]]:
    return [
        ("los dos rovers de la configuración", cfg.rovers_demo),
        ("cinco rovers repartidos (identidad por ID)", escenario_multi_rover()),
        ("ángulos en el borde del círculo", escenario_salto_angular()),
        ("barrido de ángulos cada 10°", escenario_barrido()),
    ]


# --------------------------------------------------------------------------
# Medición
# --------------------------------------------------------------------------


class Resultado:
    """Lo medido en un escenario. Junta números y veredictos en un solo lugar."""

    def __init__(self) -> None:
        self.errores_pos: list[float] = []  # en celdas
        self.errores_ang: list[float] = []  # en grados, ya sin el salto
        self.ids_esperados: list[int] = []
        self.ids_detectados: list[int] = []
        self.esquinas_coladas: list[int] = []
        self.identidades_ok = True
        self.paralajes: list[float] = []  # en celdas: lo que cuesta no corregirlo
        self.detalle: list[tuple[int, float, float, float, float]] = []

    @property
    def completo(self) -> bool:
        return sorted(self.ids_detectados) == sorted(self.ids_esperados)

    def peor_pos(self) -> float:
        return max(self.errores_pos) if self.errores_pos else 0.0

    def prom_pos(self) -> float:
        return sum(self.errores_pos) / len(self.errores_pos) if self.errores_pos else 0.0

    def peor_ang(self) -> float:
        return max(self.errores_ang) if self.errores_ang else 0.0

    def prom_ang(self) -> float:
        return sum(self.errores_ang) / len(self.errores_ang) if self.errores_ang else 0.0

    def peor_paralaje(self) -> float:
        return max(self.paralajes) if self.paralajes else 0.0


def medir(verdad, rovers, ids_esquina) -> Resultado:
    """Compara lo detectado contra la verdad, buscando cada rover por su ID.

    Se busca por identidad y no por posición en la lista, que es la misma regla
    que le pedimos a los equipos: el orden no está garantizado y la cantidad
    cambia.
    """
    r = Resultado()
    verdad_por_id = {m.id: m for m in verdad.rovers}
    r.ids_esperados = sorted(verdad_por_id)
    r.ids_detectados = sorted(x.id for x in rovers)
    r.esquinas_coladas = sorted(set(r.ids_detectados) & set(ids_esquina))

    for rover in rovers:
        real = verdad_por_id.get(rover.id)
        if real is None:
            continue
        # Se compara contra donde el marcador SE VE sobre el plano del tablero,
        # no contra donde el rover está de verdad. Son dos preguntas distintas:
        # "¿el detector midió bien lo que la cámara le mostró?" y "¿cuánto cuesta
        # que todavía no exista la corrección de paralaje?". Mezclarlas haría que
        # un detector perfecto pareciera roto.
        error_pos = math.hypot(rover.col - real.col_en_plano, rover.row - real.row_en_plano)
        r.paralajes.append(real.paralaje_celdas)
        error_ang = abs(diferencia_angular(rover.theta_grados, real.theta_grados))
        r.errores_pos.append(error_pos)
        r.errores_ang.append(error_ang)
        r.detalle.append((rover.id, real.theta_grados, rover.theta_grados, error_ang, error_pos))

        # Prueba de identidad: este rover tiene que estar más cerca de SU verdad
        # que de la de cualquier otro. Si dos se intercambiaron el ID, los
        # errores individuales podrían ser chicos y aun así estar todo mal.
        for otro_id, otro in verdad_por_id.items():
            if otro_id == rover.id:
                continue
            if math.hypot(rover.col - otro.col_en_plano, rover.row - otro.row_en_plano) <= error_pos:
                r.identidades_ok = False
    return r


# --------------------------------------------------------------------------
# Salida por pantalla
# --------------------------------------------------------------------------


def anotar(imagen: np.ndarray, sistema, rovers) -> np.ndarray:
    """Dibuja cada rover con su ID y una flecha hacia donde apunta."""
    # La fuente sintética ya entrega BGR, igual que la cámara real; se convierte
    # solo si viniera en gris, para que la herramienta sirva con las dos.
    lienzo = imagen.copy() if imagen.ndim == 3 else cv2.cvtColor(imagen, cv2.COLOR_GRAY2BGR)
    for rover in rovers:
        rad = math.radians(rover.theta_grados)
        largo = 3.0  # celdas
        puntas = sistema.a_pixeles(
            np.array(
                [
                    [rover.col, rover.row],
                    [rover.col + largo * math.cos(rad), rover.row - largo * math.sin(rad)],
                ],
                dtype=np.float64,
            )
        )
        origen = (int(round(puntas[0][0])), int(round(puntas[0][1])))
        destino = (int(round(puntas[1][0])), int(round(puntas[1][1])))
        cv2.arrowedLine(lienzo, origen, destino, (255, 0, 0), 2, cv2.LINE_AA, tipLength=0.3)
        cv2.circle(lienzo, origen, 5, (0, 0, 255), -1)
        cv2.putText(
            lienzo, "ID {}  {:.0f}deg".format(rover.id, rover.theta_grados),
            (origen[0] + 10, origen[1] - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA,
        )
    return lienzo


def imprimir_detalle_angular(resultado: Resultado) -> None:
    """Muestra la resta ingenua al lado de la buena, para ver el salto."""
    print("\n    el salto de 359° a 0°: resta ingenua contra diferencia angular\n")
    print("    {:>4} {:>10} {:>10} {:>14} {:>14}".format(
        "ID", "real", "detectado", "resta ingenua", "diferencia real"))
    print("    " + "-" * 56)
    for id_rover, real, detectado, error, _ in sorted(resultado.detalle):
        ingenua = abs(detectado - real)
        aviso = "  <-- la resta miente" if ingenua > 180.0 else ""
        print("    {:>4} {:>10.2f} {:>10.2f} {:>14.2f} {:>14.3f}{}".format(
            id_rover, real, detectado, ingenua, error, aviso))


def correr_modo(cfg, con_perspectiva: bool, umbral_mm: float, umbral_grados: float,
                salida: str | None, quiere_anotar: bool) -> bool:
    """Corre los cuatro escenarios en un modo. Devuelve True si pasó todo."""
    persp = Perspectiva(activa=con_perspectiva, inclinacion_grados=cfg.sintetico.perspectiva.inclinacion_grados)
    titulo = ("CON perspectiva (cámara inclinada {:.1f}°)".format(persp.inclinacion_grados)
              if con_perspectiva else "SIN perspectiva (cenital perfecta)")
    print("=" * 78)
    print("MODO: {}".format(titulo))
    print("=" * 78)

    ids_esquina = sorted(cfg.marcadores_esquina.ids_esperados)
    umbral_celdas = umbral_mm / cfg.tablero.cell_mm
    todo_bien = True
    resultado_angular = None

    print("  {:<40} {:>3} {:>8} {:>8} {:>8} {:>12}  {}".format(
        "escenario", "n", "pos mm", "ang máx", "ang prom", "paralaje mm", "estado"))
    print("  " + "-" * 96)

    for nombre, rovers_demo in escenarios(cfg):
        imagen, verdad = generar(cfg, rovers=rovers_demo, perspectiva=persp)
        detectados = detectar_marcadores(imagen, cfg.marcadores_esquina.nombre_diccionario)
        try:
            # Se le pasa la detección ya hecha: un solo paso del detector por cuadro.
            sistema = construir_sistema(imagen, cfg, detectados)
        except ErrorGeometria as exc:
            print("  {:<40} ERROR DE GEOMETRÍA: {}".format(nombre, exc))
            todo_bien = False
            continue

        rovers = detectar_rovers(detectados, sistema, cfg)
        r = medir(verdad, rovers, ids_esquina)

        paso = (r.completo and not r.esquinas_coladas and r.identidades_ok
                and r.peor_pos() <= umbral_celdas and r.peor_ang() <= umbral_grados)
        todo_bien = todo_bien and paso

        motivo = "OK"
        if not r.completo:
            faltan = sorted(set(r.ids_esperados) - set(r.ids_detectados))
            sobran = sorted(set(r.ids_detectados) - set(r.ids_esperados))
            motivo = "FALTAN {}".format(faltan) if faltan else "SOBRAN {}".format(sobran)
        elif r.esquinas_coladas:
            motivo = "ESQUINAS COMO ROVER {}".format(r.esquinas_coladas)
        elif not r.identidades_ok:
            motivo = "IDENTIDADES CRUZADAS"
        elif not paso:
            motivo = "FUERA DE UMBRAL"

        print("  {:<40} {:>3} {:>8.3f} {:>8.3f} {:>8.3f} {:>12.1f}  {}".format(
            nombre, len(r.errores_pos), r.peor_pos() * cfg.tablero.cell_mm,
            r.peor_ang(), r.prom_ang(), r.peor_paralaje() * cfg.tablero.cell_mm, motivo))

        if nombre.startswith("ángulos"):
            resultado_angular = r
        if salida and nombre.startswith("cinco"):
            a_guardar = anotar(imagen, sistema, rovers) if quiere_anotar else imagen
            cv2.imwrite(salida, a_guardar)

    if resultado_angular is not None:
        imprimir_detalle_angular(resultado_angular)

    print("\n  umbrales: posición {:.2f} mm ({:.4f} celdas)  |  orientación {:.2f}°".format(
        umbral_mm, umbral_celdas, umbral_grados))
    print("  esquinas {} reservadas y nunca reportadas como rover".format(ids_esquina))
    print("  La columna 'paralaje mm' NO es un error del detector: es cuánto se corre el\n"
          "  marcador del rover por estar a {:.0f} mm del tablero. Lo va a descontar la\n"
          "  etapa de paralaje, que todavía no existe.".format(cfg.paralaje.altura_marcador_rover_mm))
    print("  resultado: {}".format("TODO OK" if todo_bien else "HAY ESCENARIOS QUE FALLAN"))
    if salida:
        print("  imagen guardada en: {}".format(salida))
    print()
    return todo_bien


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verifica la detección de rovers contra la verdad del generador sintético."
    )
    parser.add_argument("--config", default=None, help="archivo de configuración")
    parser.add_argument(
        "--modo", choices=("ambos", "cenital", "perspectiva"), default="ambos",
        help="qué modo verificar (por defecto los dos)",
    )
    parser.add_argument("--umbral-mm", type=float, default=5.0,
                        help="error de posición máximo aceptado")
    parser.add_argument("--umbral-grados", type=float, default=2.0,
                        help="error de orientación máximo aceptado")
    parser.add_argument("--salida", default=None, help="ruta donde guardar la imagen (PNG)")
    parser.add_argument("--anotar", action="store_true", help="dibujar lo detectado sobre la imagen")
    args = parser.parse_args(argv)

    cfg = cargar_config(args.config) if args.config else cargar_config()

    modos = {"ambos": (False, True), "cenital": (False,), "perspectiva": (True,)}[args.modo]
    resultados = []
    for con_persp in modos:
        salida = args.salida
        if salida and len(modos) > 1:
            base, punto, ext = salida.rpartition(".")
            sufijo = "_perspectiva" if con_persp else "_cenital"
            salida = "{}{}{}{}".format(base or salida, sufijo, punto, ext) if punto else salida + sufijo
        resultados.append(
            correr_modo(cfg, con_persp, args.umbral_mm, args.umbral_grados, salida, args.anotar)
        )

    print("=" * 78)
    print("RESULTADO GENERAL: {}".format("TODO OK" if all(resultados) else "HAY FALLAS"))
    print("=" * 78)
    return 0 if all(resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
