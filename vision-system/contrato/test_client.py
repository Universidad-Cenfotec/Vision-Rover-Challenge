"""Cliente de referencia del Vision-Rover-Challenge.

Hace tres cosas, y a propósito nada más:

1. Muestra a los equipos **cómo se consume el stream**: conectarse, leer línea
   por línea, parsear, y sacar los datos del mensaje sin suponer nada.
2. **Valida** cada mensaje contra el contrato, así sirve de autochequeo: si el
   productor (simulador o visión real) se sale del contrato, esto lo canta.
3. **Mide** latencia (`ahora - ts_ms`) y saltos de secuencia, que son las dos
   señales que le dicen a un equipo si sus datos sirven o están viejos.

    python -m contrato.test_client --host 127.0.0.1 --port 2026

Sale con código 0 si todos los mensajes cumplieron el contrato, y 1 si hubo
alguno inválido.
"""

from __future__ import annotations

import argparse
import socket
import sys
import time
from collections.abc import Iterator
from typing import Any

try:  # como paquete: python -m contrato.test_client
    from .schema import DEFAULT_PORT, ahora_ms, decodificar_ndjson, validate_message
except ImportError:  # como script suelto: python contrato/test_client.py
    from schema import (  # type: ignore[no-redef]
        DEFAULT_PORT, ahora_ms, decodificar_ndjson, validate_message,
    )


# --------------------------------------------------------------------------
# Lectura del stream
# --------------------------------------------------------------------------


def leer_lineas(conexion: socket.socket) -> Iterator[str]:
    """Devuelve una línea NDJSON completa por vez.

    ESTE ES EL ERROR CLÁSICO al consumir el stream: TCP no respeta los límites
    de los mensajes. Un `recv()` puede traer media línea, o dos líneas y media.
    Por eso hay que acumular en un buffer y cortar por `\\n`, nunca asumir que
    "lo que llegó" es un mensaje entero.

    Está escrito con un buffer explícito, en vez de `socket.makefile()`, porque
    esta es la versión que se puede traducir a CircuitPython casi tal cual.
    """
    buffer = b""
    while True:
        trozo = conexion.recv(65536)
        if not trozo:
            return  # el productor cerró la conexión
        buffer += trozo
        while b"\n" in buffer:
            linea, buffer = buffer.split(b"\n", 1)
            if linea.strip():
                yield linea.decode("utf-8")


# --------------------------------------------------------------------------
# Ejemplo de consumo — lo que un equipo haría de verdad
# --------------------------------------------------------------------------


def ejemplo_de_consumo(msg: dict[str, Any]) -> list[str]:
    """Saca del mensaje lo que le importaría a un rover, y explica el porqué.

    Se llama una sola vez (con el primer mensaje) porque es didáctico, no
    funcional. Fijate en dos cosas:

    - Se ITERA sobre las listas y se busca por identidad (`id` del rover,
      `color` del cubo). NUNCA se indexa por posición fija: la cantidad de
      objetos cambia entre cuadros, y `rovers[0]` hoy puede ser otro robot
      mañana.
    - Las dimensiones salen de `grid`, no de una constante. La cancha efectiva
      es el área entre los cuatro marcadores ArUco y puede no ser exactamente
      la nominal.
    """
    lineas = []
    grid = msg["grid"]
    lineas.append(
        "cancha: {}x{} celdas de {} mm  |  fase: {}".format(
            grid["cols"], grid["rows"], grid["cell_mm"], msg["phase"]
        )
    )

    # Mi rover es el del ID de MI marcador ArUco. Se busca, no se indexa.
    MI_ID = None
    for rover in msg["rovers"]:
        if MI_ID is None:
            MI_ID = rover["id"]  # en un equipo real, esto es una constante suya
        lineas.append(
            "rover id={}  col={:.2f} row={:.2f} theta={:.1f}°  age={} ms".format(
                rover["id"], rover["col"], rover["row"], rover["theta"], rover["age_ms"]
            )
        )

    # Cada cubo va al depot de SU color: se cruzan las dos listas por color.
    depots_por_color = {d["color"]: d for d in msg["depots"]}
    for cubo in msg["cubes"]:
        destino = depots_por_color[cubo["color"]]
        lineas.append(
            "cubo {:<5} en ({:.2f}, {:.2f}) -> depot ({:.2f}, {:.2f})  age={} ms".format(
                cubo["color"], cubo["col"], cubo["row"], destino["col"], destino["row"],
                cubo["age_ms"],
            )
        )

    for obst in msg["obstacles"]:
        lineas.append("obstáculo amarillo en ({:.2f}, {:.2f})".format(obst["col"], obst["row"]))

    lineas.append(
        "salida en ({:.2f}, {:.2f})".format(msg["start"]["col"], msg["start"]["row"])
    )
    return lineas


# --------------------------------------------------------------------------
# Estadísticas
# --------------------------------------------------------------------------


class Estadisticas:
    """Acumula lo que un equipo necesita mirar para saber si confía en sus datos."""

    def __init__(self) -> None:
        self.recibidos = 0
        self.invalidos = 0
        self.no_parseables = 0
        self.seq_anterior: int | None = None
        self.saltos = 0
        self.mensajes_perdidos = 0
        self.lat_min = float("inf")
        self.lat_max = float("-inf")
        self.lat_suma = 0.0
        self.edad_max = 0
        self.primeros_errores: list[str] = []

    def registrar(self, msg: dict[str, Any], latencia_ms: float) -> None:
        self.recibidos += 1
        self.lat_min = min(self.lat_min, latencia_ms)
        self.lat_max = max(self.lat_max, latencia_ms)
        self.lat_suma += latencia_ms

        seq = msg["seq"]
        if self.seq_anterior is not None and seq != self.seq_anterior + 1:
            # Un salto NO es un error del productor: es telemetría vieja que se
            # pisó porque este cliente no drenó a tiempo. Es la política de
            # "el último valor gana" funcionando. Que sea normal no quiere
            # decir que no haya que medirlo: muchos saltos = cliente lento.
            self.saltos += 1
            self.mensajes_perdidos += max(0, seq - self.seq_anterior - 1)
        self.seq_anterior = seq

        for lista in ("rovers", "cubes", "obstacles"):
            for obj in msg[lista]:
                self.edad_max = max(self.edad_max, obj["age_ms"])

    def registrar_error(self, texto: str) -> None:
        if len(self.primeros_errores) < 5:
            self.primeros_errores.append(texto)

    @property
    def lat_prom(self) -> float:
        return self.lat_suma / self.recibidos if self.recibidos else 0.0

    def linea_resumen(self) -> str:
        if not self.recibidos:
            return "sin mensajes todavía"
        return (
            "recibidos={} invalidos={} saltos={} (perdidos={})  "
            "latencia min/prom/max = {:.0f}/{:.0f}/{:.0f} ms  age_max={} ms".format(
                self.recibidos,
                self.invalidos,
                self.saltos,
                self.mensajes_perdidos,
                self.lat_min,
                self.lat_prom,
                self.lat_max,
                self.edad_max,
            )
        )


# --------------------------------------------------------------------------
# Programa principal
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Cliente de referencia: consume, valida y mide el stream de visión."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--duracion", type=float, default=0.0, help="segundos a escuchar (0 = hasta Ctrl-C)"
    )
    parser.add_argument(
        "--resumen-cada", type=float, default=2.0, help="segundos entre líneas de resumen"
    )
    parser.add_argument("--silencioso", action="store_true", help="solo el resumen final")
    args = parser.parse_args(argv)

    stats = Estadisticas()
    print("Conectando a {}:{} ...".format(args.host, args.port))
    try:
        conexion = socket.create_connection((args.host, args.port), timeout=5.0)
    except OSError as exc:
        print("No se pudo conectar: {}".format(exc), file=sys.stderr)
        return 2
    conexion.settimeout(5.0)
    print("Conectado. Ctrl-C para cortar.\n")

    inicio = time.monotonic()
    ultimo_resumen = inicio
    primero = True

    try:
        for linea in leer_lineas(conexion):
            recepcion = ahora_ms()

            # Parsear y validar son dos pasos distintos, y los dos pueden
            # fallar por motivos distintos. Un mensaje malo se DESCARTA y se
            # sigue: nunca se corta el consumo por un mensaje suelto.
            try:
                msg = decodificar_ndjson(linea)
            except ValueError as exc:
                stats.no_parseables += 1
                stats.registrar_error("JSON inválido: {}".format(exc))
                continue

            error = validate_message(msg)
            if error is not None:
                stats.invalidos += 1
                stats.registrar_error(error)
                if not args.silencioso:
                    print("  [CONTRATO VIOLADO] {}".format(error))
                continue

            stats.registrar(msg, recepcion - msg["ts_ms"])

            if primero:
                primero = False
                if not args.silencioso:
                    print("--- primer mensaje: ejemplo de consumo -------------------------")
                    for texto in ejemplo_de_consumo(msg):
                        print("  " + texto)
                    print("---------------------------------------------------------------\n")

            ahora = time.monotonic()
            if not args.silencioso and ahora - ultimo_resumen >= args.resumen_cada:
                ultimo_resumen = ahora
                print("[{:5.1f}s] {}".format(ahora - inicio, stats.linea_resumen()))
            if args.duracion > 0 and ahora - inicio >= args.duracion:
                break
    except KeyboardInterrupt:
        pass
    except socket.timeout:
        print("Se cortó el flujo: 5 s sin recibir nada.", file=sys.stderr)
    except OSError as exc:
        print("Error de red: {}".format(exc), file=sys.stderr)
    finally:
        conexion.close()

    print("\n=== resumen final =============================================")
    print("  " + stats.linea_resumen())
    print("  no parseables: {}".format(stats.no_parseables))
    if stats.primeros_errores:
        print("  primeros errores:")
        for texto in stats.primeros_errores:
            print("    - {}".format(texto))
    fallo = stats.invalidos > 0 or stats.no_parseables > 0
    print("  contrato: {}".format("CON ERRORES" if fallo else "OK, sin errores"))
    print("===============================================================")
    return 1 if fallo else 0


if __name__ == "__main__":
    sys.exit(main())
