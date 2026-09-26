"""Verifica el conteo de cubos en posición contra la verdad del generador.

Cómo se corre:

    python -m vision.tools.verificar_acopio
    python -m vision.tools.verificar_acopio --holgura-mm 5
    python -m vision.tools.verificar_acopio --modo cenital

Qué se verifica, y por qué en dos bloques
-----------------------------------------
**La matemática** primero, sin imágenes: que el límite de la ventana esté donde
dice —acepta un pelo adentro, rechaza un micrón afuera— y —lo que de verdad
importa— que el criterio sea **conservador para cualquier rotación**.

**El recorrido** después: que una sola llamada evalúe **las tres zonas**,
cuenten o no cuenten. Un recorrido que se cortara en la primera zona en posición
devolvería menos de tres zonas, y en la pantalla eso se ve como un conteo bajo
sin ninguna explicación. Los dos casos usan las tres zonas a la vez, que es lo
que ese defecto necesitaría para manifestarse. Un cubo cuyo centro está justo en
el borde de la ventana tiene que caber entero dentro del rectángulo esté como
esté girado, y eso se comprueba barriendo el giro y mirando las cuatro esquinas.
Si esa propiedad no se cumpliera, todo lo demás daría igual: el sistema
declararía entregado un cubo que sobresale.

**El sistema entero** después, sobre imágenes sintéticas: se ponen los cubos en
sus zonas —en el centro, justo adentro del criterio, justo afuera y girados 45
grados—, se procesa el cuadro completo y se comprueba que el veredicto sea el
esperado. Acá no se prueba una fórmula: se prueba la cadena, detección de color
y ajuste de la base incluidos, que es donde entra el error real de ubicación.

La holgura
----------
"Justo adentro" y "justo afuera" no pueden ser *exactamente* el borde: el
detector ubica el cubo con un error medido de alrededor de 1 mm, así que un
cubo puesto a cero del límite caería de un lado o del otro según el ruido, y la
prueba estaría midiendo la detección en vez del criterio. La holgura por defecto
son 3 mm, tres veces ese error.

**"Justo afuera" empuja hacia adentro de la cancha**, no hacia el borde: es el
error que de verdad ocurre en una ronda —el rover no terminó de empujar el cubo
al fondo de la zona— y es el que hay que cazar.
"""

from __future__ import annotations

import argparse
import math
import sys

try:  # como paquete
    from ..configuracion import CuboDemo, Perspectiva, cargar_config, geometrias_deposito
    from ..detectors.cubos import cuadrado, detectar_cubos
    from ..detectors.rovers import detectar_rovers
    from ..geometry.coordenadas import (
        ErrorGeometria, construir_sistema, detectar_marcadores, pose_camara,
    )
    from ..mundo import CuboEnMundo, EstadoMundo, RelojRonda
    from ..reglas.acopio import ContadorAcopio
    from ..sources.generador_sintetico import generar
    from ..tracking.seguimiento import Seguidor
except ImportError:  # como script suelto
    from vision.configuracion import (  # type: ignore[no-redef]
        CuboDemo, Perspectiva, cargar_config, geometrias_deposito,
    )
    from vision.detectors.cubos import cuadrado, detectar_cubos  # type: ignore[no-redef]
    from vision.detectors.rovers import detectar_rovers  # type: ignore[no-redef]
    from vision.geometry.coordenadas import (  # type: ignore[no-redef]
        ErrorGeometria, construir_sistema, detectar_marcadores, pose_camara,
    )
    from vision.mundo import CuboEnMundo, EstadoMundo, RelojRonda  # type: ignore[no-redef]
    from vision.reglas.acopio import ContadorAcopio  # type: ignore[no-redef]
    from vision.sources.generador_sintetico import generar  # type: ignore[no-redef]
    from vision.tracking.seguimiento import Seguidor  # type: ignore[no-redef]

from contrato import schema  # noqa: E402  (después de `configuracion`, que arma el camino)


# --------------------------------------------------------------------------
# Bloque 1 — la matemática del criterio, sin imágenes
# --------------------------------------------------------------------------


def _punto(geo, eje: str, signo: float, distancia: float) -> tuple[float, float]:
    """Un punto a `distancia` del centro de la zona, sobre uno de los dos ejes."""
    if eje == "col":
        return (geo.col + signo * distancia, geo.row)
    return (geo.col, geo.row + signo * distancia)


def esquinas_adentro(geo, col: float, row: float, lado_celdas: float, theta: float) -> bool:
    """¿Las cuatro esquinas del cubo caen dentro del rectángulo de la zona?"""
    for x, y in cuadrado(col, row, lado_celdas, theta):
        if not (geo.col - geo.semi_col - 1e-9 <= x <= geo.col + geo.semi_col + 1e-9
                and geo.row - geo.semi_row - 1e-9 <= y <= geo.row + geo.semi_row + 1e-9):
            return False
    return True


def verificar_matematica(cfg) -> list[str]:
    """El criterio, sin cámara de por medio. Devuelve los problemas encontrados."""
    problemas = []
    cell = cfg.tablero.cell_mm
    lado_celdas = cfg.elementos.cubos.lado_mm / cell
    geometrias = geometrias_deposito(cfg)

    print("\n  BLOQUE 1 — el criterio, sin imágenes")
    print("  " + "-" * 74)
    for color, geo in sorted(geometrias.items()):
        print("  zona {:<6} lado {:<10} ventana {:.4f} x {:.4f} celdas = {:.2f} x {:.2f} mm".format(
            color, geo.lado, geo.ventana_col * 2, geo.ventana_row * 2,
            geo.ventana_col * 2 * cell, geo.ventana_row * 2 * cell))

    # El límite se prueba APENAS adentro y APENAS afuera, nunca exactamente
    # encima. No es una concesión: el borde exacto no se puede representar.
    # `21.5 + 2.8786796564403576 - 21.5` devuelve 2.8786796564403594, dos
    # milésimas de femtocelda de más —4 x 10^-14 mm—, así que un criterio que es
    # una desigualdad cae de un lado o del otro según la zona y el eje. Probar
    # ese punto mediría la coma flotante; lo que importa es que la frontera esté
    # donde dice, y eso se ve con un margen que sí existe.
    PELO = 1e-9        # celdas: 20 picómetros adentro
    MICRON = 1e-6      # celdas: 20 nanómetros afuera
    antes = len(problemas)
    for color, geo in sorted(geometrias.items()):
        for eje, ventana in (("col", geo.ventana_col), ("row", geo.ventana_row)):
            for signo in (1.0, -1.0):
                col, row = _punto(geo, eje, signo, ventana - PELO)
                if not schema.cubo_en_depot(col=col, row=row, geometria=geo).adentro:
                    problemas.append(
                        "zona {}: un pelo adentro del límite sobre {} se rechaza".format(
                            color, eje))
                col, row = _punto(geo, eje, signo, ventana + MICRON)
                if schema.cubo_en_depot(col=col, row=row, geometria=geo).adentro:
                    problemas.append(
                        "zona {}: un micrón afuera del límite sobre {} se acepta".format(
                            color, eje))
    print("\n  límite nítido (un pelo adentro entra, un micrón afuera no), en los dos ejes,")
    print("  los dos sentidos y las tres zonas: {}".format(
        "OK (12 límites)" if len(problemas) == antes else "FALLA"))

    # La propiedad que sostiene todo: en el borde de la ventana, el cubo entra
    # entero con CUALQUIER rotación. Si esto se rompe, el sistema declararía
    # entregado un cubo que sobresale de la zona.
    peor = None
    for color, geo in sorted(geometrias.items()):
        for grados in range(0, 91, 5):
            for dc, dr in ((geo.ventana_col, 0.0), (0.0, geo.ventana_row),
                           (-geo.ventana_col, 0.0), (0.0, -geo.ventana_row)):
                col, row = geo.col + dc, geo.row + dr
                if not esquinas_adentro(geo, col, row, lado_celdas, float(grados)):
                    peor = (color, grados)
                    problemas.append(
                        "zona {}: con el centro en el borde de la ventana y el cubo girado "
                        "{}°, una esquina se sale de la zona".format(color, grados))
    print("  cubo entero adentro en el borde de la ventana, girando de 0° a 90°: {}".format(
        "OK (19 giros x 4 bordes x 3 zonas)" if peor is None else "FALLA en {}".format(peor)))
    return problemas


# --------------------------------------------------------------------------
# Bloque 2 — el recorrido de las TRES zonas, en una sola llamada
# --------------------------------------------------------------------------

#: Épsilon de los casos de borde, en MILÍMETROS. Es una distancia FÍSICA y no el
#: épsilon de la coma flotante, a propósito: lo que se prueba es que el límite
#: esté donde dice sobre la cancha, no cómo redondea el intérprete. Medio
#: milímetro es la mitad del error de ubicación medido del sistema.
EPSILON_BORDE_MM = 0.5

#: Las tres posiciones medidas sobre la cancha montada, con los cubos puestos y
#: quietos, leídas de la telemetría el 11-sep-2026. No son inventadas: son el
#: caso que hizo dudar del conteo, y por eso quedan como regresión.
MEDIDOS_EN_CANCHA = {"green": (21.37, 3.15), "red": (40.54, 22.20), "blue": (22.93, 40.26)}


def _contar(cfg, posiciones: dict) -> "object":
    """Evalúa las tres zonas EN UNA SOLA LLAMADA, ya pasada la permanencia.

    Que sea una sola llamada con las tres zonas es el punto de este bloque: un
    recorrido que se cortara en la primera zona en posición —un `break` de más—
    devolvería menos de tres zonas y dejaría a las siguientes sin evaluar, y eso
    en la pantalla se ve como un conteo bajo sin ninguna explicación.
    """
    contador = ContadorAcopio(cfg)
    cubos = tuple(CuboEnMundo(color=color, col=p[0], row=p[1], age_ms=0)
                  for color, p in sorted(posiciones.items()))
    permanencia = cfg.conteo_acopio.permanencia_minima_ms
    contador.actualizar(EstadoMundo(ts_ms=0, fase="RUNNING", cubos=cubos), 0)
    return contador.actualizar(
        EstadoMundo(ts_ms=permanencia, fase="RUNNING", cubos=cubos), permanencia)


def _apenas_afuera(cfg) -> dict:
    """Un cubo medio milímetro afuera de la ventana, en cada una de las tres zonas.

    Se corre sobre el eje MÁS ANGOSTO de cada zona, que es el del fondo: es
    donde el criterio se juega de verdad y donde un error de signo o de eje
    pasaría inadvertido sobre el eje largo.
    """
    cell = cfg.tablero.cell_mm
    epsilon = EPSILON_BORDE_MM / cell
    posiciones = {}
    for color, geo in geometrias_deposito(cfg).items():
        if geo.ventana_row <= geo.ventana_col:      # zona apoyada arriba o abajo
            posiciones[color] = (geo.col, geo.row + geo.ventana_row + epsilon)
        else:                                       # zona apoyada a los costados
            posiciones[color] = (geo.col + geo.ventana_col + epsilon, geo.row)
    return posiciones


def verificar_recorrido(cfg) -> list[str]:
    """Que la llamada evalúe las tres zonas, cuenten o no cuenten."""
    problemas = []
    colores = set(geometrias_deposito(cfg))

    print("\n  BLOQUE 2 — el recorrido de las tres zonas, en una sola llamada")
    print("  " + "-" * 74)
    print("  {:<44} {:>10} {:>10}  {}".format("caso", "esperado", "obtenido", "estado"))
    print("  " + "-" * 74)

    casos = (
        ("los tres cubos medidos en la cancha", MEDIDOS_EN_CANCHA, 3),
        ("uno apenas afuera ({:.1f} mm) en cada zona".format(EPSILON_BORDE_MM),
         _apenas_afuera(cfg), 0),
    )
    for nombre, posiciones, esperado in casos:
        r = _contar(cfg, posiciones)
        fallas = []
        if r.en_posicion != esperado:
            fallas.append("se esperaban {} y dio {}".format(esperado, r.en_posicion))
        # La comprobación que caza el recorrido cortado: NO alcanza con que el
        # número dé, tienen que estar las tres zonas en la respuesta.
        if {z.color for z in r.zonas} != colores:
            fallas.append("la llamada devolvió {} y las zonas son {}".format(
                sorted(z.color for z in r.zonas), sorted(colores)))
        print("  {:<44} {:>10} {:>10}  {}".format(
            nombre, "{} de 3".format(esperado), "{} de {}".format(r.en_posicion, r.total),
            "OK" if not fallas else "FALLA"))
        for falla in fallas:
            print("      ✗ {}".format(falla))
            problemas.append("{}: {}".format(nombre, falla))
    return problemas


def verificar_hora_de_entrada(cfg) -> list[str]:
    """Que la hora de entrada se tome al entrar, se borre al salir y se retome.

    Se sigue UN cubo —el de la zona verde— a lo largo de una ronda inventada,
    con el cronómetro puesto a mano en cada cuadro. Lo que se comprueba es la
    regla completa: la marca es la del cronómetro al ENTRAR, no la de cuando se
    cumple la permanencia; se pierde apenas el cubo sale, por titileo o porque
    se lo llevaron; se vuelve a tomar al volver a entrar, con la hora nueva; no
    existe para un cubo que ya estaba puesto al arrancar; y no sobrevive a la
    preparación de otra ronda.
    """
    problemas = []
    geo = geometrias_deposito(cfg)["green"]
    adentro = (geo.col, geo.row)
    afuera = (geo.col, geo.row + geo.semi_row * 3)     # lejos, sin ambigüedad
    permanencia = cfg.conteo_acopio.permanencia_minima_ms

    def paso(contador, fase, transcurrido, ts, pos):
        cubos = () if pos is None else (CuboEnMundo(color="green", col=pos[0], row=pos[1]),)
        reloj = RelojRonda(transcurrido_ms=transcurrido, restante_ms=0,
                           total_ms=600_000 if fase != "IDLE" else 0)
        r = contador.actualizar(EstadoMundo(ts_ms=ts, fase=fase, reloj=reloj, cubos=cubos), ts)
        return next(z for z in r.zonas if z.color == "green")

    print("\n  BLOQUE 3 — a qué altura del cronómetro entró cada cubo")
    print("  " + "-" * 74)
    print("  {:<50} {:>10} {:>10}  {}".format("caso", "esperado", "obtenido", "estado"))
    print("  " + "-" * 74)

    c = ContadorAcopio(cfg)
    # (nombre, fase, transcurrido_ms, ts_ms, posición, marca esperada)
    guion = (
        ("entra a 0:05 de ronda", "RUNNING", 5_000, 5_000, adentro, 5_000),
        ("sigue adentro: la marca no se mueve", "RUNNING", 5_500, 5_500, adentro, 5_000),
        ("ya contado: la marca sigue siendo la de entrada", "RUNNING",
         5_000 + permanencia, 5_000 + permanencia, adentro, 5_000),
        ("sale: la marca se borra", "RUNNING", 20_000, 20_000, afuera, None),
        ("vuelve a entrar a 0:30: marca nueva", "RUNNING", 30_000, 30_000, adentro, 30_000),
        ("deja de verse: se borra", "RUNNING", 40_000, 40_000, None, None),
        ("reaparece adentro a 0:45: marca nueva", "RUNNING", 45_000, 45_000, adentro, 45_000),
        ("la ronda termina: la marca queda", "FINISHED", 50_000, 50_000, adentro, 45_000),
        ("se prepara otra ronda: la marca se vacía", "READY", 0, 60_000, adentro, None),
        ("ya estaba al arrancar: sin marca", "RUNNING", 1_000, 61_000, adentro, None),
        ("sale y vuelve en la ronda nueva: marca nueva", "RUNNING", 2_000, 62_000, afuera, None),
        ("…y vuelve a 0:03", "RUNNING", 3_000, 63_000, adentro, 3_000),
        ("en IDLE no hay ronda: sin marca", "IDLE", 0, 70_000, adentro, None),
    )
    for nombre, fase, transcurrido, ts, pos, esperado in guion:
        z = paso(c, fase, transcurrido, ts, pos)
        obtenido = z.entro_en_ronda_ms
        ok = obtenido == esperado
        print("  {:<50} {:>10} {:>10}  {}".format(
            nombre, str(esperado), str(obtenido), "OK" if ok else "FALLA"))
        if not ok:
            problemas.append("{}: se esperaba {} y dio {}".format(nombre, esperado, obtenido))
    return problemas


# --------------------------------------------------------------------------
# Bloque 4 — el sistema entero, sobre imágenes sintéticas
# --------------------------------------------------------------------------


def _hacia_adentro(lado: str) -> tuple[float, float]:
    """Vector unitario que apunta desde el borde hacia adentro de la cancha."""
    return {
        schema.LADO_ARRIBA: (0.0, 1.0),
        schema.LADO_ABAJO: (0.0, -1.0),
        schema.LADO_IZQUIERDA: (1.0, 0.0),
        schema.LADO_DERECHA: (-1.0, 0.0),
    }[lado]


def _a_lo_largo(lado: str) -> tuple[float, float]:
    """Vector unitario paralelo al borde donde apoya la zona."""
    return (1.0, 0.0) if lado in (schema.LADO_ARRIBA, schema.LADO_ABAJO) else (0.0, 1.0)


def escenarios(cfg, holgura_celdas: float):
    """`(nombre, esperado, cómo correr cada cubo, giro)`.

    El desplazamiento se expresa como una función de la geometría de la zona, y
    no como una celda concreta, porque cada zona está en un lado distinto: "un
    poco hacia adentro" es +row para la de arriba y −col para la de la derecha.
    """
    def centro(geo):
        return (0.0, 0.0)

    def fondo(factor):
        def mover(geo):
            ventana = geo.ventana_row if geo.lado in (
                schema.LADO_ARRIBA, schema.LADO_ABAJO) else geo.ventana_col
            dc, dr = _hacia_adentro(geo.lado)
            paso = ventana + factor * holgura_celdas
            return (dc * paso, dr * paso)
        return mover

    def largo(factor):
        def mover(geo):
            ventana = geo.ventana_col if geo.lado in (
                schema.LADO_ARRIBA, schema.LADO_ABAJO) else geo.ventana_row
            dc, dr = _a_lo_largo(geo.lado)
            paso = ventana + factor * holgura_celdas
            return (dc * paso, dr * paso)
        return mover

    return [
        ("en el centro de la zona", True, centro, 0.0),
        ("justo adentro, sobre el fondo", True, fondo(-1.0), 0.0),
        ("justo afuera, sin terminar de empujar", False, fondo(+1.0), 0.0),
        ("justo adentro, a lo largo", True, largo(-1.0), 0.0),
        ("justo afuera, a lo largo", False, largo(+1.0), 0.0),
        ("en el centro, girado 45°", True, centro, 45.0),
        ("justo adentro sobre el fondo, girado 45°", True, fondo(-1.0), 45.0),
        ("justo afuera sobre el fondo, girado 45°", False, fondo(+1.0), 45.0),
    ]


def correr_modo(cfg, con_perspectiva: bool, holgura_mm: float) -> bool:
    cell = cfg.tablero.cell_mm
    lado_celdas = cfg.elementos.cubos.lado_mm / cell
    holgura_celdas = holgura_mm / cell
    geometrias = geometrias_deposito(cfg)
    persp = Perspectiva(activa=con_perspectiva,
                        inclinacion_grados=cfg.sintetico.perspectiva.inclinacion_grados)
    permanencia = cfg.conteo_acopio.permanencia_minima_ms

    titulo = ("CON perspectiva (cámara inclinada {:.1f}°)".format(persp.inclinacion_grados)
              if con_perspectiva else "SIN perspectiva (cenital perfecta)")
    print("\n" + "=" * 78)
    print("BLOQUE 4 — el sistema entero · MODO: {}".format(titulo))
    print("=" * 78)
    print("  {:<42} {:>9} {:>10} {:>10}  {}".format(
        "escenario", "esperado", "contados", "peor falta", "estado"))
    print("  " + "-" * 88)

    todo_bien = True
    for nombre, esperado, mover, giro in escenarios(cfg, holgura_celdas):
        cubos = []
        for color, geo in sorted(geometrias.items()):
            dc, dr = mover(geo)
            cubos.append(CuboDemo(color=color, col=geo.col + dc, row=geo.row + dr, theta=giro))
        cubos = tuple(cubos)

        imagen, verdad = generar(cfg, rovers=(), cubos=cubos, perspectiva=persp)
        detectados = detectar_marcadores(imagen, cfg.marcadores_esquina.nombre_diccionario,
                                         cfg.deteccion_marcadores.refinamiento_esquinas)
        try:
            sistema = construir_sistema(imagen, cfg, detectados)
        except ErrorGeometria as exc:
            print("  {:<42} ERROR DE GEOMETRÍA: {}".format(nombre, exc))
            todo_bien = False
            continue
        pose = pose_camara(sistema, verdad.camara.matriz)

        seguidor = Seguidor(cfg)
        contador = ContadorAcopio(cfg)
        estado = seguidor.actualizar(
            ts_ms=0, fase="RUNNING",
            rovers=detectar_rovers(detectados, sistema, cfg, pose),
            cubos=detectar_cubos(imagen, sistema, cfg, pose))
        contador.actualizar(estado, 0)
        # El segundo cuadro es el mismo, ya pasada la permanencia mínima: lo que
        # se prueba acá es el criterio, no el antirrebote, que tiene su propia
        # verificación con estados escritos a mano.
        resultado = contador.actualizar(estado, permanencia)

        fallas = []
        peor_falta = 0.0
        for z in resultado.zonas:
            peor_falta = max(peor_falta, 0.0 if math.isinf(z.falta_celdas) else z.falta_celdas)
            if z.contado != esperado:
                fallas.append("{}: se esperaba {} y dio {} (falta {:.3f} celdas)".format(
                    z.color, "contado" if esperado else "NO contado",
                    "contado" if z.contado else "NO contado", z.falta_celdas))
            # Un veredicto positivo tiene que ser CIERTO contra la verdad del
            # generador, no solo coherente con el dato detectado.
            if z.contado:
                real = next((c for c in verdad.cubos if c.color == z.color), None)
                if real is not None and not esquinas_adentro(
                        geometrias[z.color], real.col, real.row, lado_celdas, real.theta_grados):
                    fallas.append("{}: se dio por entregado y el cubo REAL sobresale "
                                  "de la zona".format(z.color))

        contados = "{} de {}".format(resultado.en_posicion, resultado.total)
        print("  {:<42} {:>9} {:>10} {:>10}  {}".format(
            nombre, "adentro" if esperado else "afuera", contados,
            "{:.2f} mm".format(peor_falta * cell), "OK" if not fallas else "FALLA"))
        for falla in fallas:
            print("      ✗ {}".format(falla))
        todo_bien = todo_bien and not fallas

    print("\n  holgura usada: {:.1f} mm a cada lado del límite del criterio".format(holgura_mm))
    print("  resultado: {}".format("TODO OK" if todo_bien else "HAY ESCENARIOS QUE FALLAN"))
    return todo_bien


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verifica el conteo de cubos en posición contra la verdad conocida."
    )
    parser.add_argument("--config", default=None)
    parser.add_argument("--modo", choices=("ambos", "cenital", "perspectiva"), default="ambos")
    parser.add_argument("--holgura-mm", type=float, default=3.0,
                        help="cuánto adentro o afuera del límite se ponen los cubos")
    args = parser.parse_args(argv)

    cfg = cargar_config(args.config) if args.config else cargar_config()

    print("=" * 78)
    print("VERIFICACIÓN DEL ACOPIO — ¿el cubo está completamente dentro de su zona?")
    print("=" * 78)

    problemas = verificar_matematica(cfg)
    problemas += verificar_recorrido(cfg)
    problemas += verificar_hora_de_entrada(cfg)
    modos = {"ambos": (False, True), "cenital": (False,), "perspectiva": (True,)}[args.modo]
    resultados = [correr_modo(cfg, con_persp, args.holgura_mm) for con_persp in modos]

    print("\n" + "=" * 78)
    if problemas:
        print("PROBLEMAS EN EL CRITERIO:")
        for p in problemas:
            print("  ✗ {}".format(p))
    bien = not problemas and all(resultados)
    print("RESULTADO GENERAL: {}".format("TODO OK" if bien else "HAY FALLAS"))
    print("=" * 78)
    return 0 if bien else 1


if __name__ == "__main__":
    sys.exit(main())
