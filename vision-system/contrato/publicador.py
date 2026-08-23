"""Publicación TCP/NDJSON — el último valor gana.

Por qué esto vive en `contrato/` y no en cada programa
------------------------------------------------------
Hay **dos** programas que publican telemetría en el puerto 2026: el simulador
de esta carpeta y el sistema de visión real. El contrato les promete a los
equipos que pasan de uno al otro **sin tocar su código**, y esa promesa no es
solo sobre el formato del mensaje: también es sobre **cómo se comporta la
conexión**.

Cuánto se espera antes de descartar un mensaje que el cliente no leyó, si a un
cliente recién conectado se le manda enseguida o se espera al siguiente ciclo,
qué pasa cuando uno se cae — todo eso es contractual, está descrito en las
secciones 6.3 y 8 de `CONTRATO.md`, y con dos implementaciones separadas podría
divergir sin que nadie lo note. Un equipo probaría contra el simulador, le
funcionaría, y el día de la competencia se toparía con algo apenas distinto.

Así que hay **una sola implementación** y la usan los dos.

Sigue siendo biblioteca estándar pura —`socket` y `threading`—, así que
`contrato/` se sigue entregando suelto y sin instalar nada.

La política: el último valor gana
---------------------------------
Cada cliente tiene un buffer de **un mensaje**. Si llega telemetría nueva y
todavía no drenó la anterior, la anterior **se pisa**. Nunca se encola.

En telemetría de posición un dato viejo no vale nada: al equipo le sirve saber
dónde está el rover AHORA, no dónde estuvo hace medio segundo. Con una cola, un
cliente lento quedaría cada vez más atrás sin recuperarse jamás, navegando con
información cada vez más falsa.

Por eso los equipos ven saltos en el número de secuencia, y **eso es normal**:
es la política funcionando.

Un hilo por cliente
-------------------
Así lo único que puede bloquearse esperando a un socket lento es el hilo de ese
cliente. Ni el publicador ni —mucho menos— el proceso que produce la telemetría
esperan por la red. Es la regla de los relojes desacoplados.
"""

from __future__ import annotations

import socket
import threading
from typing import Callable


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
    """Servidor TCP que emite NDJSON a todos los clientes conectados.

    `avisar` es a dónde van los mensajes de conexión y desconexión. Por defecto
    a la consola, que es lo que quiere el simulador; el sistema de visión le
    pasa el suyo para que salgan por su panel en vez de ensuciar la pantalla.
    Es lo único que se agregó al extraer esta clase, y existe porque una pieza
    compartida no puede decidir por sus dos usuarios dónde se imprimen las cosas.
    """

    def __init__(self, host: str, port: int, avisar: Callable[[str], None] = print):
        self.host = host
        self.port = port
        self._avisar = avisar
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
            self._avisar("[cliente] conectado {}:{}".format(*direccion))
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
            pass  # el cliente se fue; no es un error de quien publica
        finally:
            ranura.cerrar()
            with self._lock:
                if ranura in self._ranuras:
                    self._ranuras.remove(ranura)
            try:
                conexion.close()
            except OSError:
                pass
            self._avisar(
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
