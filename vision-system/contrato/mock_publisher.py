"""Simulador de telemetría del Vision-Rover-Challenge.

Publica por TCP, en formato NDJSON, exactamente el mismo mensaje que publicará
el sistema de visión real. Sirve para que los equipos desarrollen y prueben su
lógica de rover SIN cámara y sin cancha.

Corre con Python puro: solo biblioteca estándar más `schema.py`.

    python -m contrato.mock_publisher            # config por defecto
    python -m contrato.mock_publisher --port 2026

Comandos por teclado, mientras corre: `ready`, `start`, `stop`, `quit`.

Por qué el simulador reproduce las patologías a propósito
---------------------------------------------------------
Un simulador que entrega datos perfectos es una trampa: el equipo escribe
código que anda hermoso contra el simulador y se rompe en la cancha. Acá el
ruido, las oclusiones y las pérdidas de detección están puestas de intento,
para que el código del equipo nazca tolerándolas.

Arquitectura (la misma del sistema real, en chiquito)
-----------------------------------------------------
Tres relojes desacoplados, comunicados por un estado del mundo INMUTABLE:

    hilo de simulación  --(estado nuevo)-->  [último estado]  --> hilo publicador
                                                                      |
                                                              (una ranura por cliente)
                                                                      v
                                                              hilo por cliente --> socket

El publicador nunca espera a la simulación, la simulación nunca espera a la
red, y un cliente lento no frena a nadie: su ranura de UN mensaje se pisa.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import os
import random
import socket
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any

try:  # como paquete: python -m contrato.mock_publisher
    from .schema import (
        CUBE_COLORS,
        PROTOCOL_VERSION,
        Cube,
        Depot,
        Grid,
        Mensaje,
        Obstacle,
        Rover,
        Start,
        ahora_ms,
        codificar_ndjson,
    )
except ImportError:  # como script suelto: python contrato/mock_publisher.py
    from schema import (  # type: ignore[no-redef]
        CUBE_COLORS,
        PROTOCOL_VERSION,
        Cube,
        Depot,
        Grid,
        Mensaje,
        Obstacle,
        Rover,
        Start,
        ahora_ms,
        codificar_ndjson,
    )


CONFIG_POR_DEFECTO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_simulador.json")


# --------------------------------------------------------------------------
# Estado del mundo (inmutable)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class EstadoMundo:
    """Lo que la simulación produce en cada paso: una foto ya "observada".

    Las posiciones que trae ya pasaron por ruido y oclusión — es lo que la
    cámara CREE ver, no la verdad interna del simulador. `ts_ms` es el instante
    de captura, y viaja con el estado hasta el mensaje: el publicador no lo
    reescribe, porque si lo hiciera el cliente mediría latencia cero y no se
    enteraría nunca de que está atrasado.
    """

    ts_ms: int
    phase: str
    rovers: tuple[Rover, ...]
    cubes: tuple[Cube, ...]
    obstacles: tuple[Obstacle, ...]


# --------------------------------------------------------------------------
# Configuración
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Config:
    """Configuración del simulador. Todo dato, nada incrustado en el código."""

    host: str
    port: int
    grid: Grid
    start: Start
    depots: tuple[Depot, ...]
    rovers_iniciales: tuple[dict[str, Any], ...]
    cubes_iniciales: tuple[dict[str, Any], ...]
    obstacles_iniciales: tuple[dict[str, Any], ...]
    pub_hz: float
    sim_hz: float
    velocidad_celdas_s: float
    giro_grados_s: float
    pos_sigma: float
    theta_sigma: float
    radio_oclusion: float
    prob_perdida_rover: float
    radio_empuje: float
    semilla: int | None


def cargar_config(ruta: str) -> Config:
    """Lee el archivo de configuración.

    Las claves que empiezan con `_` son notas para quien edita el archivo (JSON
    no tiene comentarios) y se ignoran solas, porque acá se leen las claves por
    nombre en vez de barrer el diccionario.
    """
    with open(ruta, "r", encoding="utf-8") as f:
        d = json.load(f)

    red = d["red"]
    grid = d["grid"]
    tasas = d["tasas"]
    ruido = d["ruido"]
    pat = d["patologias"]

    return Config(
        host=red["host"],
        port=int(red["port"]),
        grid=Grid(cols=int(grid["cols"]), rows=int(grid["rows"]), cell_mm=float(grid["cell_mm"])),
        start=Start(col=float(d["start"]["col"]), row=float(d["start"]["row"])),
        depots=tuple(
            Depot(color=x["color"], col=float(x["col"]), row=float(x["row"])) for x in d["depots"]
        ),
        rovers_iniciales=tuple(d["rovers"]),
        cubes_iniciales=tuple(d["cubes"]),
        obstacles_iniciales=tuple(d["obstacles"]),
        pub_hz=float(tasas["pub_hz"]),
        sim_hz=float(tasas["sim_hz"]),
        velocidad_celdas_s=float(d["velocidad_rover_celdas_s"]),
        giro_grados_s=float(d["giro_rover_grados_s"]),
        pos_sigma=float(ruido["pos_sigma_celdas"]),
        theta_sigma=float(ruido["theta_sigma_grados"]),
        radio_oclusion=float(pat["radio_oclusion_celdas"]),
        prob_perdida_rover=float(pat["prob_perdida_rover"]),
        radio_empuje=float(pat["radio_empuje_celdas"]),
        semilla=d.get("semilla_aleatoria"),
    )


def revisar_config(cfg: Config) -> str | None:
    """Revisa la configuración antes de arrancar.

    Vale la pena fallar acá con un mensaje claro: si la config es incoherente,
    el simulador publicaría mensajes que violan el contrato y el equipo creería
    que el problema es suyo.
    """
    colores_cubo = [c["color"] for c in cfg.cubes_iniciales]
    for color in colores_cubo:
        if color not in CUBE_COLORS:
            return "config: color de cubo fuera del contrato: {!r}".format(color)
    if len(set(colores_cubo)) != len(colores_cubo):
        return "config: hay cubos con color repetido; el color es la identidad del cubo"
    colores_depot = [x.color for x in cfg.depots]
    if len(set(colores_depot)) != len(colores_depot):
        return "config: hay más de un depot del mismo color"
    faltantes = sorted(set(colores_cubo) - set(colores_depot))
    if faltantes:
        return "config: hay cubos sin depot de su color: {}".format(faltantes)
    ids = [int(r["id"]) for r in cfg.rovers_iniciales]
    if len(set(ids)) != len(ids):
        return "config: hay rovers con el mismo id de marcador ArUco"
    if cfg.pub_hz <= 0 or cfg.sim_hz <= 0:
        return "config: pub_hz y sim_hz deben ser > 0"
    return None


# --------------------------------------------------------------------------
# Simulación
# --------------------------------------------------------------------------


class _RoverSim:
    """Estado interno (mutable) de un rover dentro de la simulación.

    Es mutable a propósito y NO sale de acá: hacia afuera solo viajan
    `EstadoMundo` inmutables. La verdad interna (`col`, `row`) es distinta de lo
    último reportado (`rep_*`), que es lo que la "cámara" alcanzó a ver.
    """

    def __init__(self, id_aruco: int, col: float, row: float, theta: float, ts_ms: int):
        self.id = id_aruco
        self.col = col
        self.row = row
        self.theta = theta % 360.0
        self.rep_col = col
        self.rep_row = row
        self.rep_theta = self.theta
        self.visto_ms = ts_ms


class _CuboSim:
    """Estado interno (mutable) de un cubo. Solo se mueve si lo empujan."""

    def __init__(self, color: str, col: float, row: float, ts_ms: int):
        self.color = color
        self.col = col
        self.row = row
        self.rep_col = col
        self.rep_row = row
        self.visto_ms = ts_ms


class Simulador:
    """Genera estados del mundo sintéticos pero realistas.

    OJO con el alcance: el movimiento de los rovers es deambulación con rebote,
    no navegación. Este proyecto NO implementa la inteligencia de los rovers;
    acá los robots se mueven solamente para que haya algo que mirar.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.rng = random.Random(cfg.semilla)
        t0 = ahora_ms()
        self.rovers = [
            _RoverSim(int(r["id"]), float(r["col"]), float(r["row"]), float(r["theta"]), t0)
            for r in cfg.rovers_iniciales
        ]
        self.cubes = [
            _CuboSim(c["color"], float(c["col"]), float(c["row"]), t0) for c in cfg.cubes_iniciales
        ]
        # Los obstáculos son fijos: no tienen estado que evolucione.
        self.obstacles = [(float(o["col"]), float(o["row"])) for o in cfg.obstacles_iniciales]

    # -- helpers ----------------------------------------------------------

    def _dentro(self, col: float, row: float) -> bool:
        """Deja un margen de media celda para que el robot no se pegue al borde."""
        margen = 1.0
        return (
            margen <= col <= self.cfg.grid.cols - margen
            and margen <= row <= self.cfg.grid.rows - margen
        )

    def _choca_obstaculo(self, col: float, row: float) -> bool:
        for ocol, orow in self.obstacles:
            if math.hypot(col - ocol, row - orow) < 2.5:
                return True
        return False

    def _ruido_pos(self) -> float:
        return self.rng.gauss(0.0, self.cfg.pos_sigma)

    # -- paso de simulación ------------------------------------------------

    def paso(self, dt_s: float, phase: str) -> EstadoMundo:
        """Avanza el mundo `dt_s` segundos y devuelve la foto observada.

        Solo se mueve en `RUNNING`. En las otras fases el mundo queda quieto,
        pero se sigue observando y publicando: el sistema nunca deja de emitir.
        """
        t = ahora_ms()

        if phase == "RUNNING":
            self._mover_rovers(dt_s)

        rovers = self._observar_rovers(t)
        cubes = self._observar_cubes(t)
        obstacles = self._observar_obstacles()

        return EstadoMundo(
            ts_ms=t, phase=phase, rovers=rovers, cubes=cubes, obstacles=obstacles
        )

    def _mover_rovers(self, dt_s: float) -> None:
        paso = self.cfg.velocidad_celdas_s * dt_s
        for rv in self.rovers:
            # Deriva suave del rumbo para que la trayectoria no sea una recta
            # aburrida y el equipo vea theta cambiando de verdad.
            rv.theta = (rv.theta + self.rng.gauss(0.0, self.cfg.giro_grados_s * dt_s * 0.3)) % 360.0

            rad = math.radians(rv.theta)
            # row crece hacia ABAJO y theta es antihorario, de ahí el signo
            # negativo en el avance sobre row.
            dcol = math.cos(rad) * paso
            drow = -math.sin(rad) * paso
            ncol, nrow = rv.col + dcol, rv.row + drow

            if not self._dentro(ncol, nrow) or self._choca_obstaculo(ncol, nrow):
                # Rebote: da media vuelta con algo de azar y se queda donde está
                # este cuadro. Simple y suficiente; no es planificación.
                rv.theta = (rv.theta + 180.0 + self.rng.uniform(-60.0, 60.0)) % 360.0
                continue

            rv.col, rv.row = ncol, nrow
            self._empujar_cubos(rv, dcol, drow)

    def _empujar_cubos(self, rv: _RoverSim, dcol: float, drow: float) -> None:
        """Un rover que pasa cerca de un cubo lo arrastra en su dirección.

        Los equipos tienen que ver cubos que se mueven solos: si asumen que un
        cubo está donde estaba hace diez segundos, se equivocan.
        """
        for cb in self.cubes:
            if math.hypot(rv.col - cb.col, rv.row - cb.row) < self.cfg.radio_empuje:
                ncol = cb.col + dcol * 0.8
                nrow = cb.row + drow * 0.8
                if self._dentro(ncol, nrow):
                    cb.col, cb.row = ncol, nrow

    def _observar_rovers(self, t: int) -> tuple[Rover, ...]:
        """Observa los rovers, con ruido y con pérdidas ocasionales.

        Cuando la detección falla, el rover NO desaparece de la lista: se
        reporta con su última posición conocida y `age_ms` creciendo. Un objeto
        que parpadea entre existir y no existir vuelve loco al consumidor.
        """
        salida = []
        for rv in self.rovers:
            if self.rng.random() >= self.cfg.prob_perdida_rover:
                rv.rep_col = rv.col + self._ruido_pos()
                rv.rep_row = rv.row + self._ruido_pos()
                rv.rep_theta = (rv.theta + self.rng.gauss(0.0, self.cfg.theta_sigma)) % 360.0
                rv.visto_ms = t
            salida.append(
                Rover(
                    id=rv.id,
                    col=round(rv.rep_col, 3),
                    row=round(rv.rep_row, 3),
                    theta=round(rv.rep_theta, 2),
                    age_ms=t - rv.visto_ms,
                )
            )
        return tuple(salida)

    def _observar_cubes(self, t: int) -> tuple[Cube, ...]:
        """Observa los cubos. Un rover encima de un cubo lo tapa (oclusión).

        Mismo criterio que con los rovers: el cubo ocluido sigue en la lista,
        con su última posición y la edad creciendo. Que `age_ms` sea grande es
        justamente la señal de "no confíes tanto en este dato".
        """
        salida = []
        for cb in self.cubes:
            ocluido = any(
                math.hypot(rv.col - cb.col, rv.row - cb.row) < self.cfg.radio_oclusion
                for rv in self.rovers
            )
            if not ocluido:
                cb.rep_col = cb.col + self._ruido_pos()
                cb.rep_row = cb.row + self._ruido_pos()
                cb.visto_ms = t
            salida.append(
                Cube(
                    color=cb.color,
                    col=round(cb.rep_col, 3),
                    row=round(cb.rep_row, 3),
                    age_ms=t - cb.visto_ms,
                )
            )
        return tuple(salida)

    def _observar_obstacles(self) -> tuple[Obstacle, ...]:
        """Los obstáculos son grandes, fijos y muy amarillos: siempre se ven.

        Igual llevan ruido, porque su centro detectado también tiembla.
        """
        return tuple(
            Obstacle(
                col=round(col + self._ruido_pos(), 3),
                row=round(row + self._ruido_pos(), 3),
                age_ms=0,
            )
            for col, row in self.obstacles
        )


# --------------------------------------------------------------------------
# Publicación TCP/NDJSON — el último valor gana
# --------------------------------------------------------------------------


class RanuraCliente:
    """Buffer de UN mensaje para un cliente.

    Esta clase es la política de "el último valor gana" hecha código: si llega
    telemetría nueva y el cliente todavía no drenó la anterior, la anterior se
    PISA. Nunca se encola.

    ¿Por qué? Porque en telemetría de posición un dato viejo no vale nada: al
    equipo le sirve saber dónde está el rover AHORA, no dónde estuvo hace medio
    segundo. Una cola haría que un cliente lento fuera quedando cada vez más
    atrás, sin recuperarse jamás.
    """

    def __init__(self, direccion: tuple[str, int]):
        self.direccion = direccion
        self._cond = threading.Condition()
        self._pendiente: str | None = None
        self._cerrada = False
        self.pisados = 0
        self.enviados = 0

    def ofrecer(self, linea: str) -> None:
        with self._cond:
            if self._cerrada:
                return
            if self._pendiente is not None:
                self.pisados += 1  # el cliente no drenó a tiempo: se descarta
            self._pendiente = linea
            self._cond.notify()

    def tomar(self, timeout: float = 0.5) -> str | None:
        """Devuelve el mensaje pendiente, o None si venció el timeout o cerró."""
        with self._cond:
            if self._pendiente is None and not self._cerrada:
                self._cond.wait(timeout)
            if self._cerrada:
                return None
            linea, self._pendiente = self._pendiente, None
            return linea

    def cerrar(self) -> None:
        with self._cond:
            self._cerrada = True
            self._pendiente = None
            self._cond.notify_all()


class Publicador:
    """Servidor TCP que emite NDJSON a todos los clientes conectados."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._ranuras: list[RanuraCliente] = []
        self._lock = threading.Lock()
        self._servidor: socket.socket | None = None
        self._parar = threading.Event()
        # Se guardan los hilos para poder ESPERARLOS al apagar. Son daemon para
        # que un cliente colgado no impida salir, pero un daemon que sigue vivo
        # cuando el intérprete se apaga puede quedar a mitad de un `print()` y
        # hacer abortar el proceso ("could not acquire lock for <stdout> at
        # interpreter shutdown"). La salida ordenada los espera; el ser daemon
        # queda solo como red de seguridad.
        self._hilo_aceptar: threading.Thread | None = None
        self._hilos_cliente: list[threading.Thread] = []

    def arrancar(self) -> None:
        self._servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._servidor.bind((self.host, self.port))
        self._servidor.listen(8)
        self._servidor.settimeout(0.5)
        self._hilo_aceptar = threading.Thread(target=self._aceptar, name="aceptar", daemon=True)
        self._hilo_aceptar.start()

    def _aceptar(self) -> None:
        while not self._parar.is_set():
            try:
                conexion, direccion = self._servidor.accept()  # type: ignore[union-attr]
            except socket.timeout:
                continue
            except OSError:
                break
            # TCP_NODELAY: sin él, Nagle junta mensajitos y agrega latencia
            # justo donde más molesta.
            conexion.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            ranura = RanuraCliente(direccion)
            hilo = threading.Thread(
                target=self._atender, args=(conexion, ranura), name="cliente", daemon=True
            )
            with self._lock:
                self._ranuras.append(ranura)
                self._hilos_cliente.append(hilo)
            print("[cliente] conectado {}:{}".format(*direccion))
            hilo.start()

    def _atender(self, conexion: socket.socket, ranura: RanuraCliente) -> None:
        """Un hilo por cliente: lo único que puede bloquearse es él mismo."""
        try:
            while not self._parar.is_set():
                linea = ranura.tomar()
                if linea is None:
                    continue
                conexion.sendall(linea.encode("utf-8"))
                ranura.enviados += 1
        except OSError:
            pass  # el cliente se fue; no es un error del simulador
        finally:
            ranura.cerrar()
            with self._lock:
                if ranura in self._ranuras:
                    self._ranuras.remove(ranura)
            try:
                conexion.close()
            except OSError:
                pass
            print(
                "[cliente] desconectado {}:{} (enviados={} pisados={})".format(
                    ranura.direccion[0], ranura.direccion[1], ranura.enviados, ranura.pisados
                )
            )

    def emitir(self, linea: str) -> None:
        with self._lock:
            ranuras = list(self._ranuras)
        for ranura in ranuras:
            ranura.ofrecer(linea)

    def cantidad_clientes(self) -> int:
        with self._lock:
            return len(self._ranuras)

    def total_pisados(self) -> int:
        with self._lock:
            return sum(r.pisados for r in self._ranuras)

    def detener(self, timeout: float = 3.0) -> None:
        """Apaga el servidor y ESPERA a que sus hilos terminen.

        Esperar no es un lujo: los hilos de cliente imprimen su línea de
        despedida en el `finally`. Si el proceso terminara sin esperarlos, uno
        podría quedar a mitad de ese `print()` justo cuando el intérprete se
        apaga, y Python aborta con un error fatal de bloqueo de `stdout`. Un
        `join` de tres segundos lo vuelve imposible.
        """
        self._parar.set()
        with self._lock:
            for ranura in self._ranuras:
                ranura.cerrar()
            hilos = list(self._hilos_cliente)
        # Cerrar el socket de escucha desbloquea el `accept()` del hilo aceptador.
        if self._servidor is not None:
            try:
                self._servidor.close()
            except OSError:
                pass
        # Los `join` van FUERA del lock: el `finally` de cada hilo de cliente lo
        # necesita para desregistrarse, y esperarlos con el lock tomado sería un
        # abrazo mortal.
        if self._hilo_aceptar is not None:
            self._hilo_aceptar.join(timeout)
        for hilo in hilos:
            hilo.join(timeout)


# --------------------------------------------------------------------------
# Máquina de fases
# --------------------------------------------------------------------------


class Fase:
    """Fase de la ronda, con las transiciones válidas.

    La visión es árbitro: la fase la decide ella y los equipos la obedecen. Acá
    la decide el teclado, que hace de árbitro humano.
    """

    _TRANSICIONES = {
        "ready": (("IDLE", "FINISHED"), "READY"),
        "start": (("READY",), "RUNNING"),
        "stop": (("RUNNING", "READY"), "FINISHED"),
    }

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._valor = "IDLE"

    @property
    def valor(self) -> str:
        with self._lock:
            return self._valor

    def aplicar(self, comando: str) -> str:
        """Aplica un comando. Devuelve un texto para mostrarle al operador."""
        with self._lock:
            if comando not in self._TRANSICIONES:
                return "comando desconocido: {!r} (usá ready, start, stop, quit)".format(comando)
            desde, hacia = self._TRANSICIONES[comando]
            if self._valor not in desde:
                return "'{}' no es válido desde {} (se puede desde {})".format(
                    comando, self._valor, list(desde)
                )
            anterior, self._valor = self._valor, hacia
            return "fase: {} -> {}".format(anterior, self._valor)


# --------------------------------------------------------------------------
# Programa principal
# --------------------------------------------------------------------------


def _hilo_teclado(fase: Fase, salir: threading.Event) -> None:
    """Lee comandos de la entrada estándar. Sin dependencias de terminal."""
    for linea in sys.stdin:
        comando = linea.strip().lower()
        if not comando:
            continue
        if comando in ("quit", "q", "exit"):
            salir.set()
            return
        print("[fase] " + fase.aplicar(comando))
    salir.set()  # EOF (por ejemplo, entrada redirigida que se terminó)


def _hilo_simulacion(
    sim: Simulador, fase: Fase, estado: list[EstadoMundo | None], salir: threading.Event
) -> None:
    """Corre al ritmo de la "cámara" y deja el último estado en `estado[0]`.

    Falla abierto: si un paso revienta, se conserva el último estado bueno y se
    sigue. El simulador no se cae a mitad de ronda, igual que el sistema real.
    """
    periodo = 1.0 / sim.cfg.sim_hz
    anterior = time.monotonic()
    while not salir.is_set():
        time.sleep(periodo)
        ahora = time.monotonic()
        dt_s, anterior = ahora - anterior, ahora
        try:
            estado[0] = sim.paso(dt_s, fase.valor)
        except Exception as exc:  # noqa: BLE001 — fail-open a propósito
            print("[sim] error en el paso (se conserva el último estado): {}".format(exc))


def _hilo_publicacion(
    pub: Publicador,
    cfg: Config,
    estado: list[EstadoMundo | None],
    salir: threading.Event,
    contador: list[int],
) -> None:
    """Corre por temporizador, independiente de la simulación.

    Si la simulación se atrasó, se republica el último estado bueno con un
    `seq` nuevo y el `ts_ms` VIEJO: así el cliente ve, por la latencia, que el
    dato está añejo, en vez de creer que todo va bien.
    """
    periodo = 1.0 / cfg.pub_hz
    while not salir.is_set():
        time.sleep(periodo)
        mundo = estado[0]
        if mundo is None:
            continue
        try:
            contador[0] += 1
            mensaje = Mensaje(
                v=PROTOCOL_VERSION,
                seq=contador[0],
                ts_ms=mundo.ts_ms,
                phase=mundo.phase,
                grid=cfg.grid,
                start=cfg.start,
                depots=cfg.depots,
                rovers=mundo.rovers,
                cubes=mundo.cubes,
                obstacles=mundo.obstacles,
            )
            pub.emitir(codificar_ndjson(mensaje))
        except Exception as exc:  # noqa: BLE001 — fail-open a propósito
            print("[pub] error al publicar (se sigue): {}".format(exc))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Simulador de telemetría del Vision-Rover-Challenge (TCP/NDJSON)."
    )
    parser.add_argument("--config", default=CONFIG_POR_DEFECTO, help="archivo de configuración")
    parser.add_argument("--host", default=None, help="sobrescribe el host de la configuración")
    parser.add_argument("--port", type=int, default=None, help="sobrescribe el puerto")
    args = parser.parse_args(argv)

    cfg = cargar_config(args.config)
    if args.host is not None or args.port is not None:
        # `replace` en vez de mutar: la config también es inmutable.
        cfg = dataclasses.replace(
            cfg,
            host=args.host if args.host is not None else cfg.host,
            port=args.port if args.port is not None else cfg.port,
        )

    error = revisar_config(cfg)
    if error is not None:
        print("ERROR de configuración: {}".format(error), file=sys.stderr)
        return 2

    sim = Simulador(cfg)
    fase = Fase()
    pub = Publicador(cfg.host, cfg.port)
    salir = threading.Event()
    estado: list[EstadoMundo | None] = [sim.paso(0.0, fase.valor)]
    contador = [0]

    pub.arrancar()
    print("=" * 66)
    print("Simulador del Vision-Rover-Challenge — protocolo v{}".format(PROTOCOL_VERSION))
    print("Publicando NDJSON en {}:{} a {:.0f} Hz".format(cfg.host, cfg.port, cfg.pub_hz))
    print("Cancha: {}x{} celdas de {:.0f} mm".format(cfg.grid.cols, cfg.grid.rows, cfg.grid.cell_mm))
    print("Comandos: ready | start | stop | quit")
    print("=" * 66)

    hilo_sim = threading.Thread(
        target=_hilo_simulacion, args=(sim, fase, estado, salir), name="sim", daemon=True
    )
    hilo_pub = threading.Thread(
        target=_hilo_publicacion,
        args=(pub, cfg, estado, salir, contador),
        name="pub",
        daemon=True,
    )
    hilo_sim.start()
    hilo_pub.start()
    # El hilo de teclado NO se espera al salir: queda bloqueado leyendo la
    # entrada estándar y no hay forma portable de desbloquearlo. Es seguro
    # dejarlo, porque estando bloqueado en la lectura no puede estar imprimiendo.
    threading.Thread(target=_hilo_teclado, args=(fase, salir), name="teclado", daemon=True).start()

    try:
        ultimo_aviso = time.monotonic()
        while not salir.is_set():
            time.sleep(0.2)
            if time.monotonic() - ultimo_aviso >= 5.0:
                ultimo_aviso = time.monotonic()
                print(
                    "[estado] fase={} seq={} clientes={} pisados={}".format(
                        fase.valor, contador[0], pub.cantidad_clientes(), pub.total_pisados()
                    )
                )
    except KeyboardInterrupt:
        pass
    finally:
        # Apagado ordenado. El orden importa: primero se avisa a todos que paren,
        # después se espera a cada hilo que pueda estar escribiendo en pantalla, y
        # recién al final imprime el hilo principal. Así ningún hilo queda a mitad
        # de un `print()` cuando el intérprete se apaga.
        salir.set()
        hilo_sim.join(3.0)
        hilo_pub.join(3.0)
        pub.detener()
        print("\nSimulador detenido. Mensajes publicados: {}".format(contador[0]))
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
