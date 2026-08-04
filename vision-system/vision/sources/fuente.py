"""Interfaz común de las fuentes de imagen.

Por qué existe
--------------
El sistema tiene que poder trabajar igual con la **cámara real** y con el
**generador sintético**. Si el resto del código supiera cuál de las dos le tocó,
habría dos caminos distintos que mantener y probar, y el sintético dejaría de
servir para verificar el real.

Con esta interfaz, quien consume imágenes recibe una `FuenteImagen` y no
pregunta más. Cambiar de una a otra es cambiar qué objeto se construye, nada más.

Por qué cada cuadro lleva su marca de tiempo
--------------------------------------------
Porque el instante que importa es el de **captura**, no el de uso. Ese valor
viaja después hasta el mensaje que reciben los equipos (`ts_ms` del contrato) y
es lo que les permite medir cuán viejo es el dato con el que están navegando. Si
se sellara al usarlo, la latencia mediría siempre casi cero y nadie se enteraría
de estar atrasado.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np


def ahora_ms() -> int:
    """Reloj de pared en milisegundos desde época.

    De pared y no monótono a propósito: es el mismo origen de tiempo que usa el
    contrato, así el consumidor final puede comparar contra su propio reloj.
    """
    return int(time.time() * 1000.0)


@dataclass(frozen=True, slots=True, eq=False)
class Cuadro:
    """Una imagen con el instante en que se capturó.

    Inmutable, como el resto de lo que cruza entre etapas: cada captura produce
    un objeto nuevo en vez de reescribir el anterior.

    `eq=False` porque contiene un arreglo de NumPy y compararlo con `==` no
    daría un booleano claro.
    """

    imagen: np.ndarray
    ts_ms: int
    indice: int  # número de cuadro; sirve para saber si llegó uno nuevo

    def edad_ms(self, referencia: int | None = None) -> int:
        """Cuántos milisegundos pasaron desde que se capturó.

        Es la medida de si el dato sirve para navegar o ya está viejo.
        """
        return (ahora_ms() if referencia is None else referencia) - self.ts_ms


@runtime_checkable
class FuenteImagen(Protocol):
    """Lo mínimo que tiene que saber hacer una fuente de imágenes."""

    def leer(self) -> Cuadro | None:
        """Devuelve el último cuadro disponible, o `None` si todavía no hay.

        **No bloquea.** Si no hay un cuadro nuevo devuelve el anterior o `None`:
        el procesamiento nunca queda esperando a la cámara. Para saber si llegó
        uno nuevo se compara el campo `indice` con el del cuadro anterior.
        """
        ...

    def cerrar(self) -> None:
        """Libera la cámara o los recursos que corresponda. Idempotente."""
        ...
