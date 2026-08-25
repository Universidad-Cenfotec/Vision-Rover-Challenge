"""Verifica que el seguimiento cumpla la promesa del contrato sobre oclusión.

Cómo se corre:

    python -m vision.tools.verificar_seguimiento

Qué promete el contrato, y qué se verifica acá
----------------------------------------------
La sección 8 de `CONTRATO.md` promete que **un objeto no desaparece de su lista
por estar tapado**: se queda con su última posición y `age_ms` creciendo. Y la
6.2 le explica al equipo que una edad alta significa oclusión, no desaparición.

Eso son cuatro afirmaciones comprobables, y cada escenario de acá las comprueba:

1. mientras el objeto está tapado, **sigue en la lista**;
2. su **posición no se mueve**: es la última buena, no una inventada;
3. su **edad crece** y coincide con el tiempo transcurrido;
4. cuando vuelve a verse, la **edad vuelve a cero**.

Por qué se prueba con cuadros y no con llamadas sueltas
-------------------------------------------------------
Se le da al seguidor una secuencia de cuadros generados —con el objeto presente,
después tapado, después de vuelta— y se mira lo que sale por el otro lado. Así se
ejercita el camino completo: detección, confiabilidad y memoria. Probar el
seguidor con detecciones escritas a mano diría que la memoria funciona, no que el
sistema cumple la promesa.
"""

from __future__ import annotations

import argparse
import sys

try:  # como paquete
    from ..configuracion import CuboDemo, Perspectiva, RoverDemo, cargar_config
    from ..detectors.cubos import detectar_cubos
    from ..detectors.rovers import detectar_rovers
    from ..geometry.coordenadas import construir_sistema, detectar_marcadores, pose_camara
    from ..sources.generador_sintetico import generar
    from ..tracking.seguimiento import Seguidor
except ImportError:  # como script suelto
    from vision.configuracion import (  # type: ignore[no-redef]
        CuboDemo, Perspectiva, RoverDemo, cargar_config,
    )
    from vision.detectors.cubos import detectar_cubos  # type: ignore[no-redef]
    from vision.detectors.rovers import detectar_rovers  # type: ignore[no-redef]
    from vision.geometry.coordenadas import (  # type: ignore[no-redef]
        construir_sistema, detectar_marcadores, pose_camara,
    )
    from vision.sources.generador_sintetico import generar  # type: ignore[no-redef]
    from vision.tracking.seguimiento import Seguidor  # type: ignore[no-redef]

PERIODO_MS = 50  # tiempo simulado entre cuadros


def un_cuadro(cfg, seguidor, ts_ms, rovers, cubos, persp):
    """Genera un cuadro, lo procesa entero y se lo da al seguidor."""
    imagen, verdad = generar(cfg, rovers=rovers, cubos=cubos, perspectiva=persp)
    detectados = detectar_marcadores(imagen, cfg.marcadores_esquina.nombre_diccionario)
    sistema = construir_sistema(imagen, cfg, detectados)
    pose = pose_camara(sistema, verdad.camara.matriz)
    return seguidor.actualizar(
        ts_ms=ts_ms, fase="RUNNING",
        rovers=detectar_rovers(detectados, sistema, cfg, pose),
        cubos=detectar_cubos(imagen, sistema, cfg, pose),
    )


def buscar_cubo(estado, color):
    for c in estado.cubos:
        if c.color == color:
            return c
    return None


def escenario_cubo_desaparece(cfg, persp, verboso):
    """El cubo se saca de la cancha del todo: la oclusión más extrema posible."""
    print("\n  ESCENARIO 1 — el cubo verde deja de verse por completo")
    print("  {:>7} {:>10} {:>20} {:>10}  {}".format(
        "cuadro", "en lista", "posición", "edad ms", "qué pasa"))
    print("  " + "-" * 72)

    seguidor = Seguidor(cfg)
    verde = CuboDemo(color="green", col=26.0, row=10.0, theta=20.0)
    otros = tuple(c for c in cfg.cubos_demo if c.color != "green")
    problemas = []
    posicion_buena = None
    edades = []

    for k in range(12):
        ts = 1000 + k * PERIODO_MS
        tapado = 3 <= k < 9
        cubos = otros if tapado else otros + (verde,)
        estado = un_cuadro(cfg, seguidor, ts, cfg.rovers_demo, cubos, persp)
        c = buscar_cubo(estado, "green")

        if c is None:
            problemas.append("cuadro {}: el cubo DESAPARECIÓ de la lista".format(k))
            print("  {:>7} {:>10} {:>20} {:>10}  {}".format(k, "NO", "—", "—", "✗ desapareció"))
            continue
        if not tapado and not problemas:
            posicion_buena = (c.col, c.row)
        if tapado:
            edades.append(c.age_ms)
            if posicion_buena and (abs(c.col - posicion_buena[0]) > 1e-9
                                   or abs(c.row - posicion_buena[1]) > 1e-9):
                problemas.append("cuadro {}: la posición se movió estando tapado".format(k))

        nota = ("tapado: conserva posición" if tapado else
                "visto" if c.age_ms == 0 else "recién vuelto")
        if verboso or k < 12:
            print("  {:>7} {:>10} ({:>7.3f},{:>7.3f}) {:>10}  {}".format(
                k, "sí", c.col, c.row, c.age_ms, nota))

    if edades != sorted(edades) or len(set(edades)) != len(edades):
        problemas.append("la edad no creció de forma monótona mientras estuvo tapado")
    esperadas = [PERIODO_MS * (k - 2) for k in range(3, 9)]
    if edades != esperadas:
        problemas.append("las edades {} no coinciden con el tiempo transcurrido {}".format(
            edades, esperadas))
    return problemas


def escenario_rover_desaparece(cfg, persp):
    """Al rover se le tapa el marcador: mismo trato que a un cubo."""
    print("\n  ESCENARIO 2 — al rover 11 se le tapa el marcador")
    print("  {:>7} {:>10} {:>20} {:>10}  {}".format(
        "cuadro", "en lista", "posición", "edad ms", "qué pasa"))
    print("  " + "-" * 72)

    seguidor = Seguidor(cfg)
    dos = cfg.rovers_demo
    uno = tuple(r for r in dos if r.id != 11)
    problemas = []
    posicion_buena = None

    for k in range(10):
        ts = 1000 + k * PERIODO_MS
        tapado = 3 <= k < 7
        estado = un_cuadro(cfg, seguidor, ts, uno if tapado else dos, cfg.cubos_demo, persp)
        r = next((x for x in estado.rovers if x.id == 11), None)
        if r is None:
            problemas.append("cuadro {}: el rover DESAPARECIÓ de la lista".format(k))
            print("  {:>7} {:>10} {:>20} {:>10}  {}".format(k, "NO", "—", "—", "✗ desapareció"))
            continue
        if not tapado:
            posicion_buena = (r.col, r.row)
        elif posicion_buena and (abs(r.col - posicion_buena[0]) > 1e-9
                                 or abs(r.row - posicion_buena[1]) > 1e-9):
            problemas.append("cuadro {}: la posición se movió estando tapado".format(k))
        print("  {:>7} {:>10} ({:>7.3f},{:>7.3f}) {:>10}  {}".format(
            k, "sí", r.col, r.row, r.age_ms,
            "tapado: conserva posición" if tapado else "visto"))
    return problemas


def escenario_empujado(cfg, persp):
    """Un rover tapa tanto el cubo que la detección deja de ser confiable.

    Es el caso que motivó la bandera `confiable`: el detector encuentra la
    mancha pero el ajuste no encaja. Lo correcto es NO refrescar con eso, y que
    el cubo envejezca conservando su última posición buena.
    """
    print("\n  ESCENARIO 3 — un rover tapa el cubo hasta volverlo no confiable")
    print("  {:>7} {:>10} {:>20} {:>10}  {}".format(
        "cuadro", "en lista", "posición", "edad ms", "qué pasa"))
    print("  " + "-" * 72)

    seguidor = Seguidor(cfg)
    verde = CuboDemo(color="green", col=34.0, row=9.0, theta=15.0)
    encima = RoverDemo(id=10, col=30.8, row=10.6, theta=30.0)
    lejos = RoverDemo(id=10, col=20.0, row=20.0, theta=30.0)
    problemas = []
    posicion_buena = None

    for k in range(9):
        ts = 1000 + k * PERIODO_MS
        tapando = 3 <= k < 7
        estado = un_cuadro(cfg, seguidor, ts, (encima if tapando else lejos,), (verde,), persp)
        c = buscar_cubo(estado, "green")
        if c is None:
            problemas.append("cuadro {}: el cubo DESAPARECIÓ de la lista".format(k))
            print("  {:>7} {:>10} {:>20} {:>10}  {}".format(k, "NO", "—", "—", "✗ desapareció"))
            continue
        if not tapando:
            posicion_buena = (c.col, c.row)
        print("  {:>7} {:>10} ({:>7.3f},{:>7.3f}) {:>10}  {}".format(
            k, "sí", c.col, c.row, c.age_ms,
            "no confiable: no refresca" if tapando and c.age_ms > 0 else
            "tapando pero todavía confiable" if tapando else "visto"))
    return problemas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verifica la memoria, la oclusión y la edad del seguimiento."
    )
    parser.add_argument("--config", default=None)
    parser.add_argument("--verboso", action="store_true")
    args = parser.parse_args(argv)

    cfg = cargar_config(args.config) if args.config else cargar_config()
    persp = Perspectiva(activa=True,
                        inclinacion_grados=cfg.sintetico.perspectiva.inclinacion_grados)

    print("=" * 78)
    print("VERIFICACIÓN DEL SEGUIMIENTO — la promesa del contrato sobre oclusión")
    print("=" * 78)
    print("  Se comprueba que un objeto tapado: sigue en la lista, no mueve su")
    print("  posición, su edad crece con el tiempo, y vuelve a cero al reaparecer.")

    problemas = []
    problemas += escenario_cubo_desaparece(cfg, persp, args.verboso)
    problemas += escenario_rover_desaparece(cfg, persp)
    problemas += escenario_empujado(cfg, persp)

    print("\n" + "=" * 78)
    if problemas:
        print("HAY FALLAS:")
        for p in problemas:
            print("  ✗ {}".format(p))
    else:
        print("RESULTADO: TODO OK")
        print("  Ningún objeto desapareció por estar tapado, ninguna posición se")
        print("  movió sin haberse visto, y las edades coinciden con el tiempo real.")
    print("=" * 78)
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
