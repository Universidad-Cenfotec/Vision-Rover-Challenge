"""Detección de rovers a partir de su marcador ArUco.

Qué hace y qué no
-----------------
Recibe los marcadores que ya se detectaron en un cuadro y el sistema de
coordenadas de ese cuadro, y devuelve **dónde está y hacia dónde apunta cada
rover**. Nada más: no recuerda cuadros anteriores, no calcula edades, no decide
si un rover desapareció. Eso es seguimiento y va en `tracking/`.

Es un productor de los del CLAUDE.md: **detecta, no decide**.

Cómo se separan los rovers de las esquinas
------------------------------------------
No hay una lista de "IDs de rover". La regla es al revés: **es rover todo
marcador que no sea una esquina**, y las esquinas son las que declara
`marcadores_esquina.disposicion`. Una lista de rovers habría que mantenerla
sincronizada con los marcadores que se peguen de verdad, y el día que no lo
estuviera, un rover dejaría de existir sin que nada avisara. Con esta regla, un
marcador nuevo aparece solo.

La única excepción es `ids_ignorados`, que arranca vacío y existe para un caso
concreto: el marcador de la prueba de precisión, que es un objeto físico real y
podría quedar olvidado sobre la cancha.

Por qué todo se calcula en CELDAS y no en píxeles
--------------------------------------------------
Este es el punto que más importa. Bajo perspectiva **los ángulos no se
conservan**: dos rovers con la misma orientación real, uno en el centro y otro
en un borde, se ven en la imagen con inclinaciones distintas. Medir el ángulo
en píxeles daría un valor que cambia según dónde esté el rover, que es
exactamente lo que un consumidor no puede usar.

La homografía manda el plano del tablero a celdas de forma exacta, así que en
el espacio de celdas el marcador vuelve a ser un cuadrado y su ángulo vuelve a
significar lo que tiene que significar. Por eso las cuatro esquinas se convierten
a celdas **primero**, y todo lo demás se calcula ahí.

El paralaje mueve la posición y no toca la orientación
------------------------------------------------------
El marcador del rover está a 90 mm sobre el tablero, así que no está en el plano
que define la homografía y aparece corrido hacia afuera. Pero como el plano del
marcador es **paralelo** al tablero, esa deformación es una homotecia —un
agrandamiento alrededor del punto que está bajo la cámara—, y una homotecia
**conserva las direcciones**.

Consecuencia práctica, medida: la corrección de paralaje mueve la **posición**
—de hasta 41 mm a menos de 1— y deja la **orientación** igual.

La corrección se aplica pasándole `pose_de_camara` a `detectar_rovers`. Esa pose
se deduce de los mismos cuatro marcadores de esquina: nadie declara la altura ni
dónde está la cámara.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

try:  # como paquete
    from ..configuracion import ConfigVision, DeteccionRovers
    from ..geometry.coordenadas import PoseCamara, SistemaCoordenadas, centro_de
except ImportError:  # como script suelto
    from vision.configuracion import ConfigVision, DeteccionRovers  # type: ignore[no-redef]
    from vision.geometry.coordenadas import (  # type: ignore[no-redef]
        PoseCamara,
        SistemaCoordenadas,
        centro_de,
    )


# --------------------------------------------------------------------------
# Ángulos
# --------------------------------------------------------------------------


def normalizar_grados(angulo: float) -> float:
    """Lleva cualquier ángulo al rango `[0, 360)` que exige el contrato.

    El redondeo del final no es cosmético: `-1e-15 % 360` da `359.99999999999994`,
    que está dentro del rango pero **se lee como 360** al imprimirlo con dos
    decimales. Un cero que se muestra como 360 hace dudar de un resultado
    correcto, así que los valores a un pelo de la vuelta completa se llevan a
    cero, que es lo que son.
    """
    valor = float(angulo % 360.0)
    return 0.0 if abs(valor - 360.0) < 1e-9 else valor


def diferencia_angular(a: float, b: float) -> float:
    """Diferencia `a - b` en grados, con signo, en `(-180, 180]`.

    **Esta función es la que evita la trampa clásica de los ángulos.** Restar a
    secas diría que 359° y 1° difieren 358°, cuando difieren 2°: el círculo se
    cierra y la resta no lo sabe. Cualquier comparación de orientaciones —la
    verificación de hoy, el seguimiento entre cuadros de mañana— tiene que pasar
    por acá.

    El `+180 … -180` alrededor del módulo es lo que centra el resultado en cero
    en vez de dejarlo en `[0, 360)`, que es lo que hace que el signo sirva para
    saber para qué lado hay que girar.
    """
    return float((a - b + 180.0) % 360.0 - 180.0)


# --------------------------------------------------------------------------
# Lo que se detecta
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PoseMarcador:
    """Dónde está y cómo está girado el MARCADOR, en celdas y grados.

    Es la medición cruda, antes de aplicar ningún desfase. Se conserva aparte de
    la pose del robot por dos razones: es lo único que el sistema mide de verdad,
    y es lo que hace falta para **medir** los desfases haciendo girar el robot en
    el lugar. Sin ella, calibrar los desfases sería imposible desde afuera.
    """

    id: int
    col: float
    row: float
    theta_grados: float


@dataclass(frozen=True, slots=True)
class RoverDetectado:
    """Un rover visto en un cuadro: la pose del ROBOT, más la del marcador.

    `col`, `row` y `theta_grados` describen el **robot** —su centro de rotación
    y hacia dónde miran sus paletas—, que es lo que el contrato publica. Con los
    desfases en cero coinciden exactamente con los del marcador.

    Es inmutable, como todo lo que cruza hacia los consumidores: cada cuadro
    produce objetos nuevos en vez de reescribir los del cuadro anterior.
    """

    id: int
    col: float
    row: float
    theta_grados: float
    marcador: PoseMarcador


# --------------------------------------------------------------------------
# De marcador a pose
# --------------------------------------------------------------------------


def pose_de_marcador(
    id_aruco: int, esquinas_px: np.ndarray, sistema: SistemaCoordenadas
) -> PoseMarcador:
    """Convierte las cuatro esquinas detectadas en una pose, en celdas y grados.

    Las esquinas vienen en el orden que devuelve OpenCV —TL, TR, BR, BL— y lo
    primero que se hace es pasarlas a celdas, por lo que dice el encabezado del
    módulo: en píxeles el ángulo no significa nada estable.

    El centro sale de `centro_de`, la misma función que usan los marcadores de
    esquina: cruzar las diagonales en vez de promediar las cuatro esquinas. Una
    sola definición de "centro" en todo el sistema, sin dos que puedan discrepar.

    La dirección de "adelante" se toma como el vector que va del punto medio del
    borde inferior al del borde superior, que es la convención del generador
    sintético y la del contrato. Se calcula con las **cuatro** esquinas y no con
    dos, para repartir el ruido de detección en vez de arrastrar el de un lado.
    """
    celdas = sistema.a_celdas(np.asarray(esquinas_px, dtype=np.float64).reshape(4, 2))
    col, row = centro_de(celdas)

    # (TL + TR) - (BL + BR): el doble del vector que va del medio del borde
    # inferior al del borde superior. El factor 2 no molesta porque solo
    # interesa la dirección.
    adelante = (celdas[0] + celdas[1]) - (celdas[3] + celdas[2])

    # El menos en la componente de fila es porque `row` crece hacia ABAJO
    # mientras que theta se mide en sentido antihorario (CLAUDE.md, sección 5).
    theta = math.degrees(math.atan2(-adelante[1], adelante[0]))

    return PoseMarcador(
        id=int(id_aruco),
        col=float(col),
        row=float(row),
        theta_grados=normalizar_grados(theta),
    )


def aplicar_desfases(
    pose: PoseMarcador, ajustes: DeteccionRovers, cell_mm: float
) -> RoverDetectado:
    """Pasa de la pose del marcador a la pose del robot.

    Son dos cosas distintas: el marcador está pegado en algún lugar del robot,
    casi nunca sobre su centro de rotación, y casi nunca perfectamente alineado
    con el frente. Lo que se detecta es una; lo que el contrato publica es la
    otra.

    El desfase de posición está guardado en el marco del **robot** —adelante e
    izquierda—, así que hay que **rotarlo** por la orientación del robot antes de
    sumarlo. Ese es el motivo de que no se guarde como `(col, row)`: un vector
    fijo en coordenadas de la cancha solo sería correcto para una orientación, y
    el robot gira.

    Con los dos desfases en cero, esto es la identidad: la pose del robot es
    exactamente la del marcador. Es el estado de hoy, y está verificado.
    """
    theta_robot = normalizar_grados(pose.theta_grados + ajustes.desfase_angular_grados)

    desfase = ajustes.desfase_posicion
    if desfase.es_nulo:
        col, row = pose.col, pose.row
    else:
        rad = math.radians(theta_robot)
        # Vectores unitarios del robot, en celdas. El menos en las componentes de
        # fila es, otra vez, porque `row` crece hacia abajo.
        adelante = (math.cos(rad), -math.sin(rad))
        izquierda = (-math.sin(rad), -math.cos(rad))
        a = desfase.adelante_mm / cell_mm
        i = desfase.izquierda_mm / cell_mm
        col = pose.col + a * adelante[0] + i * izquierda[0]
        row = pose.row + a * adelante[1] + i * izquierda[1]

    return RoverDetectado(
        id=pose.id,
        col=float(col),
        row=float(row),
        theta_grados=theta_robot,
        marcador=pose,
    )


def detectar_rovers(
    detectados: dict[int, np.ndarray],
    sistema: SistemaCoordenadas,
    cfg: ConfigVision,
    pose_de_camara: "PoseCamara | None" = None,
) -> tuple[RoverDetectado, ...]:
    """Encuentra los rovers entre los marcadores ya detectados de un cuadro.

    Recibe la detección hecha —no la imagen— para que el bucle de proceso corra
    el detector de ArUco **una sola vez** por cuadro y use el mismo resultado
    para armar las coordenadas y para encontrar los rovers.

    `pose_de_camara` habilita la **corrección de paralaje**. El marcador está a
    90 mm sobre el tablero, así que no está en el plano que define la homografía
    y se ve corrido hacia afuera: hasta 41 mm con la cámara inclinada, contra un
    criterio de aceptación de 10. Con la pose —que se deduce de los mismos
    cuatro marcadores de esquina, sin declarar nada— el corrimiento baja a menos
    de 1 mm.

    Es opcional y no obligatorio porque hay un caso legítimo sin pose: mirar la
    pose **cruda** del marcador, que es lo que necesita la calibración de los
    desfases. Sin pose, las posiciones salen corridas y hay que saberlo.

    La corrección misma vive en `geometry/` (`PoseCamara.a_ras`), no acá: esto
    es un detector y su trabajo es decir qué ve, no rehacer geometría.

    Devuelve la tupla ordenada por ID, para que dos corridas iguales den lo
    mismo. Eso **no** habilita a indexar por posición: la cantidad de rovers
    cambia entre cuadros y hay que buscarlos por `id` (CLAUDE.md, sección 7).
    """
    esquinas = cfg.marcadores_esquina.ids_esperados
    ignorados = cfg.deteccion_rovers.ids_ignorados
    altura = cfg.paralaje.altura_marcador_rover_mm

    rovers = []
    for id_aruco in sorted(detectados):
        if id_aruco in esquinas or id_aruco in ignorados:
            continue
        pose = pose_de_marcador(id_aruco, detectados[id_aruco], sistema)
        if pose_de_camara is not None:
            # El ángulo NO se toca: el paralaje es una homotecia y una homotecia
            # conserva las direcciones. Solo se mueve la posición.
            corregida = pose_de_camara.a_ras(
                np.array([[pose.col, pose.row]], dtype=np.float64), altura)[0]
            pose = PoseMarcador(id=pose.id, col=float(corregida[0]),
                                row=float(corregida[1]), theta_grados=pose.theta_grados)
        rovers.append(aplicar_desfases(pose, cfg.deteccion_rovers, cfg.tablero.cell_mm))
    return tuple(rovers)
