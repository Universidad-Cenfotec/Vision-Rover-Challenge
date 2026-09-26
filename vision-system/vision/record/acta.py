"""El acta de una ronda: qué pasó, cuándo, y por qué terminó.

Por qué existe
--------------
Sin acta hay un cronómetro en pantalla y **nada que revisar**. Cuando un equipo
reclame —que el tiempo no fue ese, que el cubo sí estaba adentro, que la ronda
se cerró antes— la única respuesta posible sería la memoria de quien miraba, y
esa discusión no se gana.

Se escribe **una por ronda cerrada**, incluidas las abortadas. Una ronda que
alguien cortó durante la preparación también es información: dice que algo salió
mal, y a qué hora.

Qué guarda, y por qué cada cosa
-------------------------------
- **Cuándo**, en hora de pared. El cronómetro oficial es monótono, que sirve para
  medir pero no para fechar: nadie puede buscar "la ronda de las 14:32" en una
  cuenta de segundos desde que arrancó la máquina. Los dos relojes, cada uno en
  su trabajo.
- **Por qué terminó**: reto cumplido, tiempo agotado, la cerró el operador, o se
  abortó en preparación.
- **El tiempo final**, que en una ronda cumplida es el que se compara entre
  equipos.
- **Cuántos cubos quedaron en posición y cuáles**, con su veredicto y su
  distancia: "dos de tres" no alcanza para revisar nada; "el rojo a 4,2 mm de
  entrar" sí.
- **Las posiciones finales** de rovers y cubos, que es la foto de cómo quedó la
  cancha.
- **El arranque**: en qué estado estaban los tres cubos al empezar a jugar. Si
  alguno ya estaba dentro de su zona, queda escrito que el arranque fue
  **irregular**. Esto no lo decide el sistema: lo registra. Que alguien haya
  visto o no el aviso rojo en pantalla no puede ser lo que determine si una
  ronda vale, y con la constancia escrita se decide después y con datos.

No decide nada
--------------
Es un consumidor: **solo lee** el estado del mundo y lo escribe a disco. Que
falle no puede afectar a la ronda ni a la telemetría, así que quien la llama la
envuelve y sigue. Un disco lleno no tumba una competencia.
"""

from __future__ import annotations

import datetime
import json
import os
from typing import Any

try:  # como paquete
    from ..configuracion import ConfigVision
    from ..mundo import VERSION_PROTOCOLO
except ImportError:  # como script suelto
    from vision.configuracion import ConfigVision  # type: ignore[no-redef]
    from vision.mundo import VERSION_PROTOCOLO  # type: ignore[no-redef]

#: Dónde se guardan: `vision/actas/`, al lado del resto de lo que el sistema
#: produce en la máquina donde corre. Son datos de competencia y no parte del
#: sistema, así que el .gitignore las deja afuera del repositorio.
CARPETA = "actas"


def mmss(ms: int | None) -> str:
    """Milisegundos a `m:ss`, para que el acta se lea sin calculadora."""
    if ms is None:
        return "—"
    segundos = ms // 1000
    return "{}:{:02d}".format(segundos // 60, segundos % 60)


def _cubos(acopio) -> list[dict[str, Any]]:
    """El detalle por color: veredicto, cuánto le faltaba y sobre qué dato."""
    if acopio is None:
        return []
    salida = []
    for z in acopio.zonas:
        salida.append({
            "color": z.color,
            "contado": z.contado,
            "adentro": z.adentro,
            "presente": z.presente,
            # `inf` no es JSON válido, y un cubo que no está no tiene distancia.
            "falta_celdas": (round(z.falta_celdas, 4)
                             if z.presente and z.falta_celdas != float("inf") else None),
            "adentro_hace_ms": z.adentro_hace_ms,
            # A qué altura del cronómetro entró el cubo en esta estadía, o
            # `None` si entró fuera de la ronda o ya estaba puesto al arrancar.
            "entro_en_ronda_ms": z.entro_en_ronda_ms,
            "entro_en_ronda": mmss(z.entro_en_ronda_ms),
            # La edad dice si el veredicto se apoya en una observación fresca o
            # en una posición conservada. Quien revise el acta tiene que poder
            # saberlo sin preguntar.
            "edad_cubo_ms": z.edad_cubo_ms,
        })
    return salida


def _posiciones(estado) -> dict[str, Any]:
    if estado is None:
        return {"rovers": [], "cubos": []}
    return {
        "rovers": [
            {"id": r.id, "col": round(r.col, 3), "row": round(r.row, 3),
             "theta": round(r.theta_grados, 2), "age_ms": r.age_ms}
            for r in estado.rovers
        ],
        "cubos": [
            {"color": c.color, "col": round(c.col, 3), "row": round(c.row, 3),
             "age_ms": c.age_ms}
            for c in estado.cubos
        ],
    }


def escribir_acta(
    cfg: ConfigVision,
    *,
    motivo: str,
    tiempo_final_ms: int | None,
    tuvo_geometria: bool,
    acopio=None,
    estado=None,
    arranque: tuple[str, ...] = (),
    sintetico: bool = False,
    perfil: dict | None = None,
    perdidas_geometria: int = 0,
    peor_ceguera_ms: int = 0,
    carpeta: str | None = None,
) -> str:
    """Escribe el acta y devuelve la ruta. Lanza si no puede; el que llama decide.

    `arranque` son los colores que **ya estaban dentro de su zona** al empezar a
    jugar. Vacío es lo normal; con algo adentro, el acta marca el arranque como
    irregular.

    `tuvo_geometria` es una condición, no un dato: **sin coordenadas no hay
    acta**, en ninguna circunstancia. La guarda vive acá adentro y no solo en
    quien llama, porque es la clase de regla que un llamador futuro saltearía sin
    darse cuenta. Una ronda que el árbitro no pudo ver no produce un documento
    que parezca válido.
    """
    if not tuvo_geometria:
        raise ValueError(
            "no se escribe acta de una ronda sin geometría: el sistema nunca tuvo "
            "coordenadas, así que no vio la cancha y no hay nada que certificar"
        )
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    destino = carpeta if carpeta is not None else os.path.join(base, CARPETA)
    os.makedirs(destino, exist_ok=True)

    ahora = datetime.datetime.now()
    ruta = os.path.join(destino, "acta_{}.json".format(ahora.strftime("%Y%m%d_%H%M%S")))

    en_posicion = sum(1 for c in _cubos(acopio) if c["contado"])
    datos = {
        "cuando": ahora.isoformat(timespec="seconds"),
        "protocolo": VERSION_PROTOCOLO,
        # Arriba de todo y con nombre inequívoco: un acta de datos generados
        # tiene exactamente la misma forma que una de verdad, y esa es justo la
        # clase de documento que parece válido y no lo es. Enterrar el dato en
        # una nota interna sería confiar en que alguien la lea.
        "NO_ES_UNA_RONDA_REAL": sintetico,
        "motivo": motivo,
        "tiempo_final_ms": tiempo_final_ms,
        "tiempo_final": mmss(tiempo_final_ms),
        "ronda_configurada": {
            "preparacion_ms": cfg.ronda.preparacion_ms,
            "duracion_ms": cfg.ronda.duracion_ms,
        },
        "cubos_en_posicion": en_posicion,
        "cubos": _cubos(acopio),
        "perfil_camara": perfil or {"camara": None, "nivel": None, "motivo": "",
                                    "_nota": "ronda sin cámara real (datos sintéticos)"},
        "geometria": {
            "perdidas": perdidas_geometria,
            "peor_perdida_ms": peor_ceguera_ms,
            "_nota": (
                "Cuántas veces el sistema se quedó sin coordenadas durante la ronda y "
                "cuánto duró la más larga. Cero es lo normal. Se anota aunque la ronda "
                "termine bien: una ronda con tres apagones de 1,8 s es una que el árbitro "
                "vio a medias, y eso tiene que poder verse sin que cambie el veredicto. "
                "Pasado el umbral de ronda.geometria_perdida_ms, la ronda se cierra con "
                "motivo `geometria_perdida`."
            ),
        },
        "posiciones_finales": _posiciones(estado),
        "arranque": {
            "irregular": bool(arranque),
            "cubos_ya_en_zona": list(arranque),
            "_nota": (
                "Los cubos que ya estaban dentro de su zona al pasar a RUNNING. Vacío "
                "es lo normal. Si hay alguno, la ronda arrancó con parte del reto ya "
                "hecho: el sistema NO la invalida ni la cierra por eso —el cierre por "
                "reto cumplido exige pasar de incompleto a completo durante la ronda—, "
                "pero queda la constancia para decidirlo después."
            ),
        },
        "_QUE_ES_ESTO": (
            "Acta de una ronda, escrita por la visión al cerrarla. El tiempo final sale "
            "del cronómetro MONÓTONO, que ningún ajuste de hora puede mover; la fecha "
            "sale del reloj de pared, porque un tiempo monótono no sirve para fechar. "
            "En una ronda cumplida, el tiempo es el de la ENTRADA del último cubo, no "
            "el del cumplimiento de la permanencia mínima del contador."
        ),
    }

    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=1, ensure_ascii=False)
    return ruta
