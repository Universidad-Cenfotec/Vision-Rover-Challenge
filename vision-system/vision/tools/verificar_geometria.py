"""Verifica la geometría de esquinas contra la verdad del generador sintético.

Cómo se corre:

    python -m vision.tools.verificar_geometria
    python -m vision.tools.verificar_geometria --salida /tmp/tablero.png --anotar

Por qué la prueba está armada así
---------------------------------
Una homografía ajustada con cuatro puntos es **exacta en esos cuatro puntos por
definición**. Verificar sobre los marcadores no probaría nada: daría cero error
aunque la matemática estuviera mal.

Por eso se mide en puntos que **no participaron del ajuste** —el centro, los
medios de los bordes y una rejilla interior— y las cuatro esquinas se dejan como
grupo de control, para ver el contraste entre "exacto por construcción" y
"realmente bien".

Y se corre en dos modos, con y sin inclinación de cámara. Sin inclinación la
homografía degenera en una escala; recién con perspectiva la prueba pone a
prueba lo que dice poner a prueba.
"""

from __future__ import annotations

import argparse
import sys

import cv2
import numpy as np

try:  # como paquete
    from ..configuracion import Perspectiva, cargar_config
    from ..geometry.coordenadas import (
        AnclajeCancha, ErrorGeometria, construir_sistema, detectar_marcadores,
    )
    from ..sources.generador_sintetico import generar
except ImportError:  # como script suelto
    from vision.configuracion import Perspectiva, cargar_config  # type: ignore[no-redef]
    from vision.geometry.coordenadas import (  # type: ignore[no-redef]
        AnclajeCancha,
        ErrorGeometria,
        construir_sistema,
        detectar_marcadores,
    )
    from vision.sources.generador_sintetico import generar  # type: ignore[no-redef]


def puntos_de_prueba(cols: int, rows: int, verdad) -> list[tuple[str, np.ndarray]]:
    """Arma los grupos de celdas donde se va a medir el error.

    Los grupos están separados a propósito: interesa ver si el error se
    concentra en alguna zona, no solo su promedio general.
    """
    c, r = float(cols), float(rows)

    esquinas = np.array([[0, 0], [c, 0], [c, r], [0, r]], dtype=np.float64)
    centro = np.array([[c / 2, r / 2]], dtype=np.float64)
    bordes = np.array([[c / 2, 0], [c, r / 2], [c / 2, r], [0, r / 2]], dtype=np.float64)

    # Rejilla interior de 5x5, sin tocar los bordes: son los puntos más lejanos
    # de los cuatro que ajustaron la homografía, donde más se notaría un error
    # de modelo.
    fracciones = np.linspace(1.0 / 6.0, 5.0 / 6.0, 5)
    rejilla = np.array(
        [[c * fx, r * fy] for fy in fracciones for fx in fracciones], dtype=np.float64
    )

    grupos = [
        ("esquinas de la grilla (control)", esquinas),
        ("centro del tablero", centro),
        ("medios de los bordes", bordes),
        ("rejilla interior 5x5", rejilla),
    ]
    if verdad.rovers:
        grupos.append(
            ("posiciones de los rovers", np.array([[m.col, m.row] for m in verdad.rovers], dtype=np.float64))
        )
    return grupos


def medir(verdad, sistema, celdas: np.ndarray) -> tuple[float, float]:
    """Celda conocida -> píxel (verdad) -> celda (geometría). Devuelve (max, promedio).

    El error se mide como distancia euclídea en celdas entre lo que se pidió y
    lo que devolvió el sistema de coordenadas.
    """
    pixeles = verdad.celdas_a_pixeles(celdas)
    recuperadas = sistema.a_celdas(pixeles)
    distancias = np.linalg.norm(recuperadas - celdas, axis=1)
    return float(distancias.max()), float(distancias.mean())


def anotar(imagen: np.ndarray, sistema, verdad) -> np.ndarray:
    """Dibuja lo detectado sobre la imagen, para poder mirarla y creerle."""
    # La fuente sintética ya entrega BGR, igual que la cámara real; se convierte
    # solo si viniera en gris, para que la herramienta sirva con las dos.
    lienzo = imagen.copy() if imagen.ndim == 3 else cv2.cvtColor(imagen, cv2.COLOR_GRAY2BGR)
    for id_aruco, (x, y) in sistema.centros_px.items():
        cv2.circle(lienzo, (int(round(x)), int(round(y))), 9, (0, 0, 255), 2)
        cv2.putText(
            lienzo, "ID {}".format(id_aruco), (int(x) + 12, int(y) - 12),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA,
        )
    # Reproyecta una rejilla de celdas conocidas: si la geometría está bien, los
    # puntos caen sobre las intersecciones de la grilla dibujada.
    paso = max(1, verdad.cols // 5)
    celdas = np.array(
        [[c, r] for c in range(0, verdad.cols + 1, paso) for r in range(0, verdad.rows + 1, paso)],
        dtype=np.float64,
    )
    for x, y in sistema.a_pixeles(celdas):
        cv2.drawMarker(lienzo, (int(round(x)), int(round(y))), (0, 150, 0), cv2.MARKER_CROSS, 10, 1)
    return lienzo


def correr_modo(cfg, con_perspectiva: bool, umbral_mm: float, salida: str | None, quiere_anotar: bool) -> bool:
    """Corre la verificación completa en un modo. Devuelve True si pasó."""
    persp = Perspectiva(
        activa=con_perspectiva, inclinacion_grados=cfg.sintetico.perspectiva.inclinacion_grados
    )
    imagen, verdad = generar(cfg, perspectiva=persp)

    titulo = "CON perspectiva (cámara inclinada {:.1f}°)".format(persp.inclinacion_grados) if con_perspectiva else "SIN perspectiva (cenital perfecta)"
    print("=" * 78)
    print("MODO: {}".format(titulo))
    print("=" * 78)
    print("  imagen {}x{} px  |  grilla {}x{} celdas de {:.0f} mm  |  {:.2f} px por celda".format(
        verdad.ancho_px, verdad.alto_px, verdad.cols, verdad.rows, verdad.cell_mm, verdad.px_por_celda))

    # --- detección ---------------------------------------------------------
    detectados = detectar_marcadores(imagen, cfg.marcadores_esquina.nombre_diccionario)
    esperados = sorted(cfg.marcadores_esquina.ids_esperados)
    encontrados_esquina = sorted(set(detectados) & set(esperados))
    print("\n  marcadores de esquina esperados : {}".format(esperados))
    print("  marcadores de esquina detectados: {}  -> {}".format(
        encontrados_esquina, "OK" if encontrados_esquina == esperados else "FALTAN"))
    otros = sorted(set(detectados) - set(esperados))
    if otros:
        print("  otros marcadores en la imagen   : {} (rovers; todavía no se procesan)".format(otros))

    try:
        sistema = construir_sistema(imagen, cfg)
    except ErrorGeometria as exc:
        print("\n  ERROR DE GEOMETRÍA: {}".format(exc))
        return False

    # Cuánto se corrió el centro detectado respecto del centro real: es el ruido
    # de entrada que después arrastra toda la geometría.
    errores_centro = []
    for m in verdad.esquinas:
        cx, cy = sistema.centros_px[m.id]
        errores_centro.append(np.hypot(cx - m.centro_px[0], cy - m.centro_px[1]))
    print("  error de los centros detectados : máx {:.3f} px (contra la verdad)".format(max(errores_centro)))

    # --- error de conversión ----------------------------------------------
    print("\n  celda conocida -> píxel (verdad del generador) -> celda (geometría detectada)\n")
    print("  {:<38} {:>3} {:>9} {:>9} {:>9} {:>9}  {}".format(
        "grupo de puntos", "n", "máx celd", "máx mm", "prom celd", "prom mm", "estado"))
    print("  " + "-" * 92)
    umbral_celdas = umbral_mm / verdad.cell_mm
    todo_bien = True
    for nombre, celdas in puntos_de_prueba(verdad.cols, verdad.rows, verdad):
        peor, prom = medir(verdad, sistema, celdas)
        paso = peor <= umbral_celdas
        todo_bien = todo_bien and paso
        print("  {:<38} {:>3} {:>9.4f} {:>9.3f} {:>9.4f} {:>9.3f}  {}".format(
            nombre, len(celdas), peor, peor * verdad.cell_mm,
            prom, prom * verdad.cell_mm, "OK" if paso else "FALLA"))

    print("\n  umbral de aprobación: {:.2f} mm ({:.4f} celdas)".format(umbral_mm, umbral_celdas))
    print("  resultado: {}".format("TODO OK" if todo_bien else "HAY GRUPOS FUERA DE UMBRAL"))

    if salida:
        a_guardar = anotar(imagen, sistema, verdad) if quiere_anotar else imagen
        cv2.imwrite(salida, a_guardar)
        print("  imagen guardada en: {}".format(salida))
    print()
    return todo_bien


def _tapar(imagen, verdad, cuantos):
    """Pinta encima de los primeros marcadores de esquina, como un reflejo.

    Se agranda el cuadrilátero un 60 % para tapar también la zona blanca: sin
    ella el detector no encuentra el marcador aunque el negro esté intacto, que
    es exactamente cómo se pierde un marcador en la cancha real.
    """
    salida = imagen.copy()
    for m in sorted(verdad.esquinas, key=lambda x: x.id)[:cuantos]:
        puntos = np.array(m.esquinas_px, np.int32)
        centro = puntos.mean(axis=0)
        cv2.fillConvexPoly(salida, ((puntos - centro) * 1.6 + centro).astype(np.int32),
                           (200, 200, 200))
    return salida


def verificar_degradacion(cfg, umbral_mm: float) -> bool:
    """¿Aguanta el sistema que se pierda un marcador de esquina?

    Con los cuatro, la homografía se recalcula. Con TRES no se puede reajustar
    —una homografía tiene ocho grados de libertad y tres puntos dan seis, así
    que lo que falta son justo los términos de perspectiva— pero sí se puede
    **conservar** la última buena: la cámara está atornillada. Y los tres
    visibles alcanzan para comprobar que sigue valiendo.

    Lo que se verifica acá es que la precisión NO se degrade al conservar, y que
    el sistema **rechace** cuando no puede sostener la geometría: con dos
    marcadores, o cuando los tres delatan que la cámara se movió.
    """
    print("=" * 78)
    print("DEGRADACIÓN: ¿qué pasa si se pierde un marcador de esquina?")
    print("=" * 78)

    persp = Perspectiva(activa=True,
                        inclinacion_grados=cfg.sintetico.perspectiva.inclinacion_grados)
    imagen, verdad = generar(cfg, perspectiva=persp)
    celdas = np.array([[verdad.cols * fx, verdad.rows * fy]
                       for fy in np.linspace(.15, .85, 5) for fx in np.linspace(.15, .85, 5)])
    anclaje = AnclajeCancha(cfg)
    todo_bien = True

    print("  {:<44} {:>9} {:>10} {:>10}".format("situación", "visibles", "error mm", "desvío mm"))
    print("  " + "-" * 78)
    for etiqueta, tapados, debe_andar in (
        ("los cuatro visibles", 0, True),
        ("uno tapado: conserva y verifica", 1, True),
        ("uno tapado, cuadro siguiente", 1, True),
        ("dos tapados: no hay con qué verificar", 2, False),
    ):
        im = _tapar(imagen, verdad, tapados)
        detectados = detectar_marcadores(im, cfg.marcadores_esquina.nombre_diccionario)
        try:
            sistema = anclaje.actualizar(im, detectados)
            peor, _ = medir(verdad, sistema, celdas)
            error_mm = peor * verdad.cell_mm
            paso = debe_andar and error_mm <= umbral_mm
            print("  {:<44} {:>9} {:>10.3f} {:>10.2f}  {}".format(
                etiqueta, anclaje.esquinas_visibles, error_mm, anclaje.desvio_mm,
                "OK" if paso else "DEBERÍA HABER RECHAZADO"))
        except ErrorGeometria:
            paso = not debe_andar
            print("  {:<44} {:>9} {:>10} {:>10}  {}".format(
                etiqueta, anclaje.esquinas_visibles, "rechaza", "—",
                "OK" if paso else "NO DEBERÍA RECHAZAR"))
        todo_bien = todo_bien and paso

    # Con un marcador tapado Y la cámara movida, tiene que darse cuenta.
    print("\n  Y si además la cámara SE MUEVE, los tres visibles la delatan:\n")
    print("  {:<44} {:>10} {:>10}".format("la cámara se movió", "desvío mm", "veredicto"))
    print("  " + "-" * 68)
    for grados, debe_rechazar in ((0.1, False), (0.5, True), (2.0, True)):
        anclaje2 = AnclajeCancha(cfg)
        base, _ = generar(cfg, perspectiva=persp)
        anclaje2.actualizar(base, detectar_marcadores(
            base, cfg.marcadores_esquina.nombre_diccionario))
        movida = Perspectiva(activa=True, inclinacion_grados=persp.inclinacion_grados + grados)
        im2, v2 = generar(cfg, perspectiva=movida)
        im2 = _tapar(im2, v2, 1)
        try:
            anclaje2.actualizar(im2, detectar_marcadores(
                im2, cfg.marcadores_esquina.nombre_diccionario))
            paso = not debe_rechazar
            veredicto = "acepta"
        except ErrorGeometria:
            paso = debe_rechazar
            veredicto = "RECHAZA"
        todo_bien = todo_bien and paso
        print("  {:<44} {:>10.2f} {:>10}  {}".format(
            "movida {:.1f}°".format(grados), anclaje2.desvio_mm, veredicto,
            "OK" if paso else "MAL"))

    print("\n  resultado: {}\n".format("TODO OK" if todo_bien else "HAY FALLAS"))
    return todo_bien


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verifica el sistema de coordenadas contra la verdad del generador sintético."
    )
    parser.add_argument("--config", default=None, help="archivo de configuración")
    parser.add_argument(
        "--modo", choices=("ambos", "cenital", "perspectiva"), default="ambos",
        help="qué modo verificar (por defecto los dos)",
    )
    parser.add_argument("--umbral-mm", type=float, default=5.0, help="error máximo aceptado")
    parser.add_argument("--salida", default=None, help="ruta donde guardar la imagen (PNG)")
    parser.add_argument("--anotar", action="store_true", help="dibujar lo detectado sobre la imagen")
    args = parser.parse_args(argv)

    cfg = cargar_config(args.config) if args.config else cargar_config()

    modos = {"ambos": (False, True), "cenital": (False,), "perspectiva": (True,)}[args.modo]
    resultados = []
    for con_persp in modos:
        salida = args.salida
        if salida and len(modos) > 1:
            # Un archivo por modo, para poder mirar los dos.
            base, punto, ext = salida.rpartition(".")
            sufijo = "_perspectiva" if con_persp else "_cenital"
            salida = "{}{}{}{}".format(base or salida, sufijo, punto, ext) if punto else salida + sufijo
        resultados.append(correr_modo(cfg, con_persp, args.umbral_mm, salida, args.anotar))
    if args.modo == "ambos":
        resultados.append(verificar_degradacion(cfg, args.umbral_mm))

    print("=" * 78)
    print("RESULTADO GENERAL: {}".format("TODO OK" if all(resultados) else "HAY FALLAS"))
    print("=" * 78)
    return 0 if all(resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
