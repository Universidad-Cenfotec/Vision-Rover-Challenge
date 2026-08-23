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
from dataclasses import dataclass

try:  # como paquete
    from .configuracion import ConfigVision
except ImportError:  # como script suelto
    from vision.configuracion import ConfigVision  # type: ignore[no-redef]

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
    última posición conocida. Lo hace crecer el seguidor de `tracking/`, que es
    el único que tiene memoria entre cuadros.
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
