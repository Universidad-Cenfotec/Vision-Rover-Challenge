"""El estado del mundo: la foto de la cancha en un instante.

Qué es y por qué está acá
-------------------------
Es **lo único que cruza** de los productores a los consumidores (CLAUDE.md,
sección 3). Los productores —cámara, geometría, detectores, seguimiento— lo
producen; los consumidores —publicación, grabación— lo leen. Nada más pasa de un
lado al otro.

Por eso este módulo no vive ni en `detectors/` ni en `publish/`: **no es de
ninguno de los dos lados**, es la frontera. Los dos dependen de él y él no
depende de ninguno.

Por qué es inmutable
--------------------
Porque productores y consumidores corren en **hilos distintos**. Si el estado se
modificara en el lugar, un consumidor podría estar leyendo la posición de un
rover justo mientras un productor la reescribe, y publicaría una mezcla de dos
instantes. La solución no es poner candados por todos lados: es **no modificar
nunca**. Cada cuadro produce un estado nuevo y el anterior queda intacto para
quien lo estuviera usando.

`ts_ms` es el instante de CAPTURA
---------------------------------
No el de detección ni el de envío: el instante en que la cámara tomó el cuadro,
que viene sellado desde `sources/`. El contrato lo promete así y los equipos lo
usan para medir latencia real y decidir si frenar. Si en algún eslabón alguien
lo reemplazara por "ahora", los equipos medirían siempre cero y navegarían a
ciegas creyendo que van al día.

Cómo se convierte al contrato
-----------------------------
Con `contrato/schema.py`, que es **la fuente de verdad compartida** entre el
simulador y el sistema de visión. No se arma el diccionario a mano: si el
simulador y la visión construyeran el mensaje por caminos distintos, tarde o
temprano dirían cosas distintas, y los equipos desarrollan contra uno para
correr contra el otro.

La dependencia va en un solo sentido —`vision/` puede usar `contrato/`, nunca al
revés— y esta es la única puerta por la que pasa.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

try:  # como paquete
    from .configuracion import ConfigVision
    from .detectors.cubos import CuboDetectado
    from .detectors.rovers import RoverDetectado
except ImportError:  # como script suelto
    from vision.configuracion import ConfigVision  # type: ignore[no-redef]
    from vision.detectors.cubos import CuboDetectado  # type: ignore[no-redef]
    from vision.detectors.rovers import RoverDetectado  # type: ignore[no-redef]

# `contrato/` es hermana de `vision/`, no está adentro. Se la agrega al camino de
# búsqueda para poder importarla sin instalar nada: el contrato se entrega suelto
# y no es un paquete instalable.
_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

from contrato import schema  # noqa: E402  (después de tocar sys.path, a propósito)


#: Las fases que puede tener una ronda. La visión es árbitro y esta es su voz.
FASES = ("IDLE", "READY", "RUNNING", "FINISHED")


@dataclass(frozen=True, slots=True)
class RoverEnMundo:
    """Un rover en el estado del mundo.

    `age_ms` es cuánto hace que no se lo ve **de verdad**. En cero significa que
    se lo acaba de detectar; creciendo, que está tapado y se está conservando su
    última posición conocida. Mientras no exista `tracking/` siempre vale cero,
    porque no hay memoria entre cuadros que pueda hacerlo crecer.
    """

    id: int
    col: float
    row: float
    theta_grados: float
    age_ms: int = 0


@dataclass(frozen=True, slots=True)
class CuboEnMundo:
    """Un cubo en el estado del mundo. El color es su identidad."""

    color: str
    col: float
    row: float
    age_ms: int = 0


@dataclass(frozen=True, slots=True)
class EstadoMundo:
    """La cancha en un instante. Inmutable, y lo único que cruza al otro lado.

    Los **lugares fijos** —salida y depósitos— no están acá adentro: se declaran
    en la configuración y no cambian entre cuadros, así que repetirlos en cada
    estado sería copiar lo mismo veinte veces por segundo. Se agregan al armar
    el mensaje.
    """

    ts_ms: int
    fase: str
    rovers: tuple[RoverEnMundo, ...] = ()
    cubos: tuple[CuboEnMundo, ...] = ()

    def __post_init__(self) -> None:
        if self.fase not in FASES:
            raise ValueError(
                "fase desconocida {!r}; las válidas son {}".format(self.fase, list(FASES))
            )


def desde_detecciones(
    ts_ms: int,
    fase: str,
    rovers: tuple[RoverDetectado, ...],
    cubos: tuple[CuboDetectado, ...],
) -> EstadoMundo:
    """Arma un estado del mundo con lo detectado en un cuadro.

    Es la frontera entre "lo que se vio" y "lo que se publica": acá se descarta
    todo lo que es asunto interno —el residuo del ajuste, la pose cruda del
    marcador, el área de la mancha— y queda solo lo que el contrato promete.

    **Los cubos no confiables no entran.** Cuando el ajuste no encaja —un rover
    tapando casi todo el cubo—, la posición puede errar más que no decir nada.
    Omitirlo acá es lo correcto: el seguimiento, cuando exista, va a conservar su
    última posición buena con la edad creciendo, que es lo que manda el contrato
    para un objeto ocluido. Publicar una posición inventada sería peor que las
    dos cosas.

    Todavía no hay memoria entre cuadros, así que las edades salen en cero. Eso
    es honesto: hoy todo lo que se publica es de este cuadro.
    """
    return EstadoMundo(
        ts_ms=int(ts_ms),
        fase=fase,
        rovers=tuple(
            RoverEnMundo(id=r.id, col=r.col, row=r.row, theta_grados=r.theta_grados)
            for r in rovers
        ),
        cubos=tuple(
            CuboEnMundo(color=c.color, col=c.col, row=c.row)
            for c in cubos if c.confiable
        ),
    )


def a_mensaje(estado: EstadoMundo, cfg: ConfigVision, seq: int) -> schema.Mensaje:
    """Convierte el estado del mundo al mensaje del contrato.

    `seq` lo pone el publicador y no el detector: cuenta **mensajes publicados**,
    no cuadros procesados. Los huecos que ve un cliente son mensajes que se le
    pisaron por la política de último-valor-gana, y eso es la política
    funcionando, no una falla.

    `obstacles` sale siempre como lista vacía: esta edición del reto no los usa.
    El campo sigue existiendo y sigue siendo una lista, así que **no es un cambio
    de contrato** y ningún equipo tiene que tocar nada.
    """
    return schema.Mensaje(
        seq=seq,
        ts_ms=estado.ts_ms,
        phase=estado.fase,
        grid=schema.Grid(cols=cfg.tablero.cols, rows=cfg.tablero.rows,
                         cell_mm=cfg.tablero.cell_mm),
        start=schema.Start(col=cfg.lugares.start_col, row=cfg.lugares.start_row),
        depots=tuple(
            schema.Depot(color=d.color, col=d.col, row=d.row) for d in cfg.lugares.depositos
        ),
        rovers=tuple(
            schema.Rover(id=r.id, col=round(r.col, 3), row=round(r.row, 3),
                         theta=round(r.theta_grados, 2), age_ms=r.age_ms)
            for r in estado.rovers
        ),
        cubes=tuple(
            schema.Cube(color=c.color, col=round(c.col, 3), row=round(c.row, 3),
                        age_ms=c.age_ms)
            for c in estado.cubos
        ),
        obstacles=(),
    )
