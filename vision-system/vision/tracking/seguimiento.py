"""Seguimiento entre cuadros: memoria, oclusión y edad.

Acá NO hay problema de asociación
---------------------------------
Vale la pena decirlo primero, porque cambia por completo el tamaño del problema:
**cada objeto de este reto trae su propia identidad**. El rover la trae en el ID
de su marcador ArUco; el cubo, en su color, y no hay dos del mismo.

O sea que no hay que adivinar **qué detección de este cuadro corresponde a cuál
del anterior** —que es el problema difícil de todo seguimiento, el que obliga a
predicciones, filtros y algoritmos de asignación— porque la respuesta viene
escrita en el objeto.

Lo que queda es mucho más simple, y por eso mucho más confiable: **recordar la
última observación buena de cada identidad y decir cuánto hace que fue**.

La regla que no se negocia
--------------------------
Un objeto tapado **mantiene su última posición** y su **edad crece**. Nunca
parpadea entre existir y no existir.

Un objeto que aparece y desaparece vuelve loco al consumidor: el código del
equipo tendría que distinguir "se lo llevaron" de "no lo veo ahora mismo", y no
puede. Es preferible un dato viejo **marcado como viejo** que un agujero.

Qué cuenta como "verlo de verdad"
---------------------------------
Un rover: que se haya detectado su marcador. La detección de ArUco es binaria —
lo encuentra o no lo encuentra.

Un cubo: que se haya detectado **y que el ajuste sea confiable**. Una detección
no confiable dice "el cubo está por acá" pero no "el cubo está acá", y por eso
**no refresca la posición ni la edad**. Es justo el caso del rover empujando un
cubo y tapándole casi todo: se conserva la última posición buena y la edad crece,
que es exactamente lo que el contrato promete para un objeto ocluido. Refrescar
con esa detección sería publicar una posición que el propio sistema considera
dudosa, y encima presentarla como fresca.

La edad se mide en tiempo de captura
------------------------------------
`edad = ts_ms de este cuadro − ts_ms del cuadro donde se lo vio por última vez`.
Los dos son instantes de **captura**, así que la edad no depende de cuánto tardó
el procesamiento ni de cuándo se publicó. Es la edad real del dato, que es lo que
el equipo necesita para decidir si frenar.
"""

from __future__ import annotations

from dataclasses import dataclass

try:  # como paquete
    from ..configuracion import ConfigVision
    from ..detectors.cubos import CuboDetectado
    from ..detectors.rovers import RoverDetectado
    from ..mundo import CuboEnMundo, EstadoMundo, RoverEnMundo
except ImportError:  # como script suelto
    from vision.configuracion import ConfigVision  # type: ignore[no-redef]
    from vision.detectors.cubos import CuboDetectado  # type: ignore[no-redef]
    from vision.detectors.rovers import RoverDetectado  # type: ignore[no-redef]
    from vision.mundo import (  # type: ignore[no-redef]
        CuboEnMundo, EstadoMundo, RoverEnMundo,
    )


@dataclass(slots=True)
class _Recuerdo:
    """La última observación buena de un objeto, y cuándo fue.

    Es mutable a propósito, y es lo único que lo es en todo este camino: la
    memoria del seguidor vive del lado de los productores y nunca cruza. Lo que
    cruza es el estado del mundo, que se produce nuevo en cada cuadro.
    """

    col: float
    row: float
    theta_grados: float
    ts_ms: int


class Seguidor:
    """Memoria de los objetos vistos, cuadro a cuadro.

    Es el único que convierte detecciones en estado del mundo, y lo hace
    **recordando**. Sin memoria, todo se publicaría con edad cero y un objeto
    tapado desaparecería de la lista, que es justo lo que el contrato promete
    que no pasa.

    No es seguro para usar desde varios hilos, y no hace falta que lo sea: vive
    en el hilo de proceso, que es el único que lo toca.
    """

    def __init__(self, cfg: ConfigVision):
        self._cfg = cfg
        self._rovers: dict[int, _Recuerdo] = {}
        self._cubos: dict[str, _Recuerdo] = {}
        # Contadores para el diagnóstico: cuántas veces se conservó una posición
        # porque no se vio el objeto. Es la medida de cuánta oclusión hubo.
        self.conservados_rover = 0
        self.conservados_cubo = 0
        self.barridos = 0

    def actualizar(
        self,
        ts_ms: int,
        fase: str,
        rovers: tuple[RoverDetectado, ...],
        cubos: tuple[CuboDetectado, ...],
    ) -> EstadoMundo:
        """Incorpora las detecciones de un cuadro y produce el estado del mundo."""
        vistos_rover = {r.id for r in rovers}
        for r in rovers:
            self._rovers[r.id] = _Recuerdo(r.col, r.row, r.theta_grados, ts_ms)

        refrescar_dudosos = self._cfg.seguimiento.refrescar_con_cubos_no_confiables
        vistos_cubo = set()
        for c in cubos:
            if c.confiable or refrescar_dudosos:
                self._cubos[c.color] = _Recuerdo(c.col, c.row, 0.0, ts_ms)
                vistos_cubo.add(c.color)

        self.conservados_rover += len(set(self._rovers) - vistos_rover)
        self.conservados_cubo += len(set(self._cubos) - vistos_cubo)
        self._barrer(ts_ms)

        return EstadoMundo(
            ts_ms=ts_ms,
            fase=fase,
            rovers=tuple(
                RoverEnMundo(id=id_rover, col=r.col, row=r.row,
                             theta_grados=r.theta_grados, age_ms=max(0, ts_ms - r.ts_ms))
                for id_rover, r in sorted(self._rovers.items())
            ),
            cubos=tuple(
                CuboEnMundo(color=color, col=c.col, row=c.row,
                            age_ms=max(0, ts_ms - c.ts_ms))
                for color, c in sorted(self._cubos.items())
            ),
        )

    def _barrer(self, ts_ms: int) -> None:
        """Saca los objetos que hace demasiado que no se ven.

        No es para oclusiones: para eso está la edad, y el contrato promete que
        un objeto tapado no desaparece. Esto barre **fantasmas** —una detección
        espuria que nunca se repitió, o un objeto que de verdad se fue de la
        cancha— y el límite es generoso a propósito para que una oclusión
        legítima nunca lo alcance.
        """
        limite = self._cfg.seguimiento.edad_maxima_ms
        for memoria in (self._rovers, self._cubos):
            viejos = [k for k, v in memoria.items() if ts_ms - v.ts_ms > limite]
            for k in viejos:
                del memoria[k]
                self.barridos += 1

    @property
    def edades_ms(self) -> dict[str, int]:
        """Las edades actuales, para el diagnóstico. No se publica desde acá."""
        ultimo = max(
            [r.ts_ms for r in self._rovers.values()] + [c.ts_ms for c in self._cubos.values()],
            default=0,
        )
        salida = {"rover {}".format(k): ultimo - v.ts_ms for k, v in self._rovers.items()}
        salida.update({c: ultimo - v.ts_ms for c, v in self._cubos.items()})
        return salida
