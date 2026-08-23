"""Publicación de telemetría: el consumidor que le habla a los equipos.

Qué hace
--------
Toma el **estado del mundo** que producen los detectores y lo emite por TCP en
formato NDJSON, en el puerto 2026, a todos los equipos conectados.

Es un **consumidor** de los del CLAUDE.md: solo LEE el estado del mundo, nunca
lo modifica.

El transporte no está acá
-------------------------
Abrir el puerto, aceptar clientes y la política de "el último valor gana" viven
en `contrato/publicador.py`, **compartidos con el simulador**. El contrato les
promete a los equipos que pasan del simulador a la cancha sin tocar su código, y
eso incluye cómo se comporta la conexión. Con dos implementaciones podrían
divergir sin que nadie lo note.

Lo que sí está acá es lo que este lado tiene de propio: el **reloj de
publicación**, el **contador de secuencia** y la **casilla del último estado
bueno**.

Los dos relojes, y por qué no se esperan
----------------------------------------
El procesamiento corre a la velocidad de la cámara. La publicación corre por
**temporizador propio**. Entre los dos hay una sola casilla con el último estado
producido.

Si un cuadro tarda de más en procesarse, la publicación no se frena: vuelve a
mandar el último estado bueno, con su `ts_ms` de captura ya viejo. El equipo lo
ve envejecer y decide. Y si un equipo tiene la red lenta, el procesamiento ni se
entera: la lentitud queda encerrada en el hilo de ese cliente.

Falla abierto
-------------
La casilla conserva el último estado bueno. Si el procesamiento tira una
excepción y deja de actualizarla, **la publicación sigue emitiendo**: un dato de
hace 300 milisegundos, marcado como viejo, le sirve mucho más a un equipo que un
silencio repentino. El sistema no se calla a mitad de una ronda.

Antes del primer cuadro bueno se publica igual, con las listas vacías y la fase
que corresponda. Que no haya nada detectado todavía es información, no un motivo
para no hablar.
"""

from __future__ import annotations

import threading
import time
from typing import Callable

try:  # como paquete
    from ..configuracion import ConfigVision
    from ..mundo import EstadoMundo, a_mensaje
except ImportError:  # como script suelto
    from vision.configuracion import ConfigVision  # type: ignore[no-redef]
    from vision.mundo import EstadoMundo, a_mensaje  # type: ignore[no-redef]

from contrato import schema  # noqa: E402  (`mundo` ya dejó `contrato/` en el camino)
from contrato.publicador import Publicador  # noqa: E402


class PublicadorTelemetria:
    """Emite el estado del mundo por TCP, por temporizador propio.

    Se usa así:

        pub = PublicadorTelemetria(cfg)
        pub.arrancar()
        ...
        pub.actualizar(estado)   # desde el hilo de proceso, cada cuadro
        ...
        pub.detener()

    `actualizar` **nunca bloquea**: deja el estado en una casilla y vuelve. Eso
    es lo que garantiza que la red no pueda frenar al procesamiento.
    """

    def __init__(self, cfg: ConfigVision, host: str = "0.0.0.0",
                 avisar: Callable[[str], None] = print):
        self._cfg = cfg
        self._avisar = avisar
        self._publicador = Publicador(host, cfg.publicacion.puerto, avisar=avisar)
        self._hz = cfg.publicacion.hz
        # La casilla del último estado bueno. Es lo único que cruza entre el
        # hilo de proceso y el de publicación, y por eso el estado del mundo es
        # inmutable: acá se reemplaza la referencia entera, nunca se edita.
        self._estado: EstadoMundo | None = None
        self._lock = threading.Lock()
        self._seq = 0
        self._parar = threading.Event()
        self._hilo: threading.Thread | None = None
        self.emitidos = 0

    # -- lado del productor ------------------------------------------------

    def actualizar(self, estado: EstadoMundo) -> None:
        """Deja un estado nuevo en la casilla. No bloquea, no espera a nadie."""
        with self._lock:
            self._estado = estado

    # -- ciclo de vida -----------------------------------------------------

    def arrancar(self) -> None:
        self._publicador.arrancar()
        self._hilo = threading.Thread(target=self._ciclo, name="publicacion", daemon=True)
        self._hilo.start()
        self._avisar("[publicacion] escuchando en el puerto {} a {:.0f} Hz".format(
            self._cfg.publicacion.puerto, self._hz))

    def detener(self, timeout: float = 3.0) -> None:
        self._parar.set()
        if self._hilo is not None:
            self._hilo.join(timeout)
        self._publicador.detener(timeout)

    # -- lado del consumidor -----------------------------------------------

    def _ciclo(self) -> None:
        """El reloj de publicación. Corre pase lo que pase del otro lado."""
        periodo = 1.0 / self._hz
        proximo = time.monotonic()
        while not self._parar.is_set():
            proximo += periodo
            espera = proximo - time.monotonic()
            if espera > 0:
                self._parar.wait(espera)
            else:
                # Se llegó tarde: se saltea en vez de acumular deuda. Perseguir
                # un cronograma atrasado solo produce ráfagas.
                proximo = time.monotonic()
            if self._parar.is_set():
                break
            self._emitir_una()

    def _emitir_una(self) -> None:
        with self._lock:
            estado = self._estado
        if estado is None:
            estado = EstadoMundo(ts_ms=schema.ahora_ms(), fase=schema.FASE_IDLE)

        self._seq += 1
        mensaje = a_mensaje(estado, self._cfg, self._seq)
        self._publicador.emitir(schema.codificar_ndjson(mensaje.a_dict()))
        self.emitidos += 1

    # -- estado, para el panel y el diagnóstico ----------------------------

    @property
    def clientes(self) -> int:
        return self._publicador.cantidad_clientes()

    @property
    def pisados(self) -> int:
        """Mensajes descartados porque un cliente no drenó a tiempo.

        No es un error: es la política de último-valor-gana funcionando. Que
        suba mucho significa que hay un cliente lento, no que se rompió algo.
        """
        return self._publicador.total_pisados()

    def edad_del_estado_ms(self) -> int | None:
        """Cuánto hace que el procesamiento no deja un estado nuevo.

        Es el termómetro del falla-abierto: si sube y la publicación sigue,
        significa que se está emitiendo el último estado bueno mientras algo
        anda mal del otro lado. `None` si todavía no llegó ninguno.
        """
        with self._lock:
            estado = self._estado
        return None if estado is None else schema.ahora_ms() - estado.ts_ms
