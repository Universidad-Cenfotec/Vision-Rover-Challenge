"""Cuántos cubos están en posición. La regla de entrega del reto.

Qué hace y qué NO hace
----------------------
Toma el **estado del mundo** —dónde está cada cubo— y le aplica la regla del
reglamento: un cubo está entregado cuando queda **completamente dentro** de la
zona de acopio de su color. Devuelve la cuenta y el detalle por color.

**No dibuja**: eso es de `vista.py`. **No publica**: el conteo no viaja en el
mensaje. **No cierra la ronda**: cuando están los tres, se lo informa al árbitro
—que es quien decide y quien lleva el cronómetro— y él cierra. Acá se cuenta y
se dice desde cuándo; la ronda la termina una sola voz.

El instante que importa es el de la ENTRADA
-------------------------------------------
Por eso se guardan **dos** marcas por color. La permanencia se mide en tiempo de
**captura**, porque mide cuándo pasaron las cosas y no cuándo se las miró. Pero
el tiempo oficial de la ronda tiene que ser **monótono**, para que un ajuste de
hora del sistema no altere un tiempo de competencia, así que junto a la marca de
captura se guarda una monótona del mismo cuadro.

Lo que se le informa al árbitro es la monótona de **cuando el cubo entró**, no la
de cuando se cumplió la permanencia. El contador exige un segundo sostenido para
no titilar; tomar el tiempo oficial ahí le costaría ese segundo a todos los
equipos por igual, que es lo mismo que decir que el cronómetro está mal
calibrado.

A qué altura de la ronda entró cada cubo
----------------------------------------
Además de cuánto hace que está adentro, se recuerda **en qué instante del
cronómetro oficial entró**: es el dato que quien mira la pantalla quiere saber
—"el verde entró a 1:23"— y el que un equipo pregunta después. Es la misma
marca que se usa para fechar el cierre, pero contada sobre el reloj de la
ronda, que es el que todos ven.

La marca vive **solo mientras el cubo sigue adentro**. Si sale, por el motivo
que sea —un rover lo saca, o titila en el borde—, se borra y vuelve a cero; al
volver a entrar se toma de nuevo, con la hora de esa nueva entrada. No hay
"primera entrada" que sobreviva a una salida: lo que vale es la entrada de la
estadía actual.

Solo se anota si el cubo entró **durante la ronda** (`RUNNING`). Un cubo que ya
estaba adentro al arrancar no entró a ninguna hora de esa ronda, y uno que entra
en `IDLE` o `READY` tampoco: en esos casos la marca queda vacía. Y al prepararse
una ronda nueva, las marcas de la anterior se vacían, para que un cubo que quedó
puesto no muestre la hora de la vuelta pasada.

El veredicto no se calcula acá
------------------------------
Sale de `contrato/schema.py`, igual que el que calcula el equipo en su rover. Si
esta pieza escribiera su propia versión de la cuenta, un cubo podría estar
"adentro" en nuestra pantalla y "afuera" en el código del equipo, y no habría
forma de decidir quién tiene razón. Acá solo vive la **memoria entre cuadros**,
que es lo que el contrato no puede tener porque no ve la secuencia.

Por qué hay una permanencia mínima
----------------------------------
El conteo es **en vivo**: cuenta los que están adentro **ahora**, y si un rover
saca un cubo, la cuenta baja. Pero un cubo dejado **justo en el borde del
criterio** entra y sale del veredicto con el puro jitter de la detección, y sin
permanencia el número saltaría entre 2 y 3 varias veces por segundo, que en
pantalla se lee como un sistema roto.

No es hipotético: con el fondo de zona de 100 mm que tuvo la primera versión de
la v2, la ventana medía 15,2 mm sobre ese eje y en la cancha real un cubo bien
puesto oscilaba entre 5 y 10 mm afuera del límite, cuadro a cuadro.

La permanencia solo demora **entrar**, nunca **salir**. Demorar la salida sería
peor que el titileo: diría que un cubo está entregado cuando un rover ya se lo
llevó.

Un cubo tapado sigue contando
-----------------------------
Y es deliberado. El seguimiento conserva la última posición buena de un objeto
ocluido —es la promesa del contrato—, así que un cubo que ya estaba adentro y
queda tapado por el rover que acaba de entregarlo **sigue contado**. Lo
contrario sería que el contador se cayera justo en el momento de la entrega, que
es exactamente cuando hay un rover encima.

Como el veredicto se sostiene sobre una posición conservada y no sobre una
observación fresca, el detalle expone la **edad** del cubo, y la vista la
muestra cuando pasa a ser vieja. Quien mira la pantalla tiene que poder saber
sobre qué se apoya lo que está viendo.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

try:  # como paquete
    from ..configuracion import ConfigVision, geometrias_deposito
    from ..mundo import EstadoMundo
except ImportError:  # como script suelto
    from vision.configuracion import ConfigVision, geometrias_deposito  # type: ignore[no-redef]
    from vision.mundo import EstadoMundo  # type: ignore[no-redef]

# Importar `configuracion` deja `contrato/` en el camino de búsqueda, así que
# esto va después y no antes.
from contrato import schema  # noqa: E402


@dataclass(frozen=True, slots=True)
class EstadoZona:
    """Cómo está una zona de acopio en este instante.

    `adentro` es el veredicto **instantáneo** y `contado` es ese veredicto ya
    sostenido durante la permanencia mínima. Se exponen los dos porque son
    preguntas distintas: el primero dice si el cubo está bien puesto, el segundo
    si el sistema ya lo da por entregado. En el borde del criterio pueden
    discrepar por un rato, y esconderlo haría parecer que la pantalla no
    reacciona.

    `falta_celdas` es cuánto hay que mover el cubo para que entre; vale `inf`
    cuando no hay ningún cubo de ese color en el estado del mundo.

    `entro_en_ronda_ms` es el cronómetro oficial —el transcurrido de la ronda—
    en el instante en que el cubo entró en su zona **esta vez**. Vale `None`
    cuando el cubo no está adentro, cuando entró fuera de `RUNNING` o cuando ya
    estaba puesto al arrancar la ronda. Se borra apenas el cubo sale y se toma
    de nuevo si vuelve a entrar.
    """

    color: str
    presente: bool
    adentro: bool
    contado: bool
    falta_celdas: float
    adentro_hace_ms: int
    edad_cubo_ms: int
    entro_en_ronda_ms: int | None = None


@dataclass(frozen=True, slots=True)
class ResultadoAcopio:
    """La cuenta y el detalle, en un instante. Inmutable, como el estado."""

    zonas: tuple[EstadoZona, ...]
    #: Tiempo MONÓTONO de la entrada del último cubo que falta para completar el
    #: reto, o `None` si el reto no está completo. Es lo que el árbitro usa para
    #: fechar el cierre: el instante en que el cubo entró, no aquel en que se
    #: cumplió la permanencia un segundo más tarde.
    instante_completo: float | None = None

    @property
    def en_posicion(self) -> int:
        return sum(1 for z in self.zonas if z.contado)

    @property
    def total(self) -> int:
        return len(self.zonas)

    @property
    def completo(self) -> bool:
        """Los tres cubos en su zona. Anuncia el reto cumplido; no lo cierra."""
        return self.total > 0 and self.en_posicion == self.total


class ContadorAcopio:
    """Lleva la memoria de cuánto hace que cada cubo está dentro de su zona.

    Es la única pieza con memoria de este paquete, al estilo de
    `tracking/seguimiento.py`, y por el mismo motivo: la regla necesita saber
    qué pasó antes y un estado del mundo solo cuenta el ahora.

    No es seguro para usar desde varios hilos, y no hace falta que lo sea: vive
    en el hilo de proceso, que es el único que lo toca.
    """

    def __init__(self, cfg: ConfigVision):
        self._cfg = cfg
        # Las geometrías se arman UNA vez: son lugares declarados que no cambian
        # entre cuadros, y rehacerlas veinte veces por segundo sería trabajo
        # perdido. Si la configuración fuera incoherente, esto lanza acá, al
        # construir, y no en medio de la ronda.
        self._geometrias = geometrias_deposito(cfg)
        self._permanencia_ms = cfg.conteo_acopio.permanencia_minima_ms
        #: Desde cuándo cada color está adentro sin interrupción, en tiempo de
        #: captura. Se borra la entrada apenas sale: la permanencia se vuelve a
        #: contar desde cero, porque lo que se quiere medir es que se quede.
        self._desde_ms: dict[str, int] = {}
        #: La misma entrada, en tiempo MONÓTONO. Va en paralelo y no en
        #: reemplazo: la permanencia se mide en tiempo de captura, que es cuándo
        #: pasaron las cosas; el tiempo oficial de la ronda se mide con un reloj
        #: que ningún ajuste de hora puede mover.
        self._desde_mono: dict[str, float] = {}
        #: El cronómetro de la ronda cuando cada color entró, o `None` si entró
        #: fuera de `RUNNING`. Se borra junto con las otras dos marcas: es la
        #: hora de ESTA estadía, no de la primera vez que el cubo pisó la zona.
        self._entro_ronda: dict[str, int | None] = {}

    @property
    def geometrias(self) -> dict[str, schema.GeometriaDepot]:
        """Las zonas, para que la vista las dibuje sin recalcularlas."""
        return self._geometrias

    def actualizar(
        self, estado: EstadoMundo, ts_ms: int, mono: float | None = None
    ) -> ResultadoAcopio:
        """Evalúa el estado del mundo y devuelve la cuenta.

        `ts_ms` es el instante de **captura** del cuadro, el mismo con el que el
        seguimiento mide la edad. No se usa el reloj de pared: si el
        procesamiento se atrasa, la permanencia tiene que medirse sobre el
        tiempo en que las cosas pasaron, no sobre el tiempo en que se las miró.

        `mono` es el instante **monótono** del mismo cuadro, y se guarda en
        paralelo para poder fechar el cierre de la ronda con un reloj que ningún
        ajuste de hora pueda mover. Se puede inyectar para verificar sin
        depender del reloj de la máquina.
        """
        ahora_mono = time.monotonic() if mono is None else mono
        cubos = {c.color: c for c in estado.cubos}  # el color ES la identidad
        en_ronda = estado.fase == "RUNNING"
        if estado.fase in ("IDLE", "READY"):
            # Se está preparando otra ronda, o no hay ninguna: la hora de
            # entrada de la ronda anterior ya no describe nada. El cubo sigue
            # adentro y sigue contando; lo que se vacía es a qué altura de qué
            # ronda entró.
            self._entro_ronda = {color: None for color in self._entro_ronda}

        zonas = []
        for color in sorted(self._geometrias):
            cubo = cubos.get(color)
            if cubo is None:
                # Sin cubo no hay nada que sostener: se olvida el conteo para
                # que, si vuelve, tenga que ganarse la permanencia de nuevo.
                self._desde_ms.pop(color, None)
                self._desde_mono.pop(color, None)
                self._entro_ronda.pop(color, None)
                zonas.append(EstadoZona(
                    color=color, presente=False, adentro=False, contado=False,
                    falta_celdas=float("inf"), adentro_hace_ms=0, edad_cubo_ms=0,
                ))
                continue

            veredicto = schema.cubo_en_depot(
                col=cubo.col, row=cubo.row, geometria=self._geometrias[color])

            if not veredicto.adentro:
                # Salió, por el motivo que sea: las tres marcas se van juntas.
                # Si vuelve a entrar, se toman de nuevo, con la hora de entonces.
                self._desde_ms.pop(color, None)
                self._desde_mono.pop(color, None)
                self._entro_ronda.pop(color, None)
                adentro_hace_ms = 0
            else:
                desde = self._desde_ms.setdefault(color, ts_ms)
                self._desde_mono.setdefault(color, ahora_mono)
                self._entro_ronda.setdefault(
                    color, estado.reloj.transcurrido_ms if en_ronda else None)
                if ts_ms < desde:  # el reloj retrocedió: se reancla, no se resta mal
                    desde = ts_ms
                    self._desde_ms[color] = desde
                    self._desde_mono[color] = ahora_mono
                adentro_hace_ms = ts_ms - desde

            zonas.append(EstadoZona(
                color=color,
                presente=True,
                adentro=veredicto.adentro,
                contado=veredicto.adentro and adentro_hace_ms >= self._permanencia_ms,
                falta_celdas=veredicto.falta_celdas,
                adentro_hace_ms=adentro_hace_ms,
                edad_cubo_ms=cubo.age_ms,
                entro_en_ronda_ms=self._entro_ronda.get(color),
            ))

        # El instante del reto es el del ÚLTIMO cubo en entrar: los otros ya
        # estaban, así que el reto se completó cuando entró ese. Solo tiene
        # sentido si están los tres contados.
        completo = bool(zonas) and all(z.contado for z in zonas)
        instante = max(self._desde_mono[z.color] for z in zonas) if completo else None
        return ResultadoAcopio(zonas=tuple(zonas), instante_completo=instante)
