"""El sistema de visión: el programa que encadena todo y se enciende.

Cómo se corre:

    python -m vision.sistema                  # con la cámara real
    python -m vision.sistema --sintetico      # sin cámara, con imágenes generadas
    python -m vision.sistema --fase RUNNING   # arrancar ya en juego

Mientras corre, se escribe por teclado: `ready`, `start`, `stop`, `quit`.

Un solo sistema, y lo único que cambia es la entrada
-----------------------------------------------------
Este bucle es **el mismo** con la cámara real y con imágenes generadas. No hay
dos caminos ni dos programas: `FuenteCamara` y `FuenteSintetica` cumplen la
misma interfaz, así que todo lo que viene después no se entera de cuál le tocó.

**Lo sintético nunca arranca solo.** Sin argumentos se abre la cámara. Para
correr con imágenes generadas hay que pedirlo, y el sistema lo repite en pantalla
todo el tiempo: nadie tiene que poder confundir una demostración con una ronda.

Los dos relojes
---------------
Este bucle corre a la velocidad de la **cámara**. La publicación corre por su
**propio temporizador**, en otro hilo, y entre los dos hay una sola casilla con
el último estado bueno. Ninguno espera al otro (CLAUDE.md, sección 3).

Falla abierto
-------------
Cada cuadro se procesa dentro de un `try`. Si algo falla —se tapó un marcador de
esquina, la cámara devolvió basura, un detector se rompió— **no se actualiza la
casilla y se sigue**. La publicación continúa emitiendo el último estado bueno,
que envejece a la vista de todos.

El sistema **no se cae a mitad de una ronda**. Un dato de hace 300 milisegundos,
marcado como viejo, le sirve mucho más a un equipo que un silencio repentino.
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time

try:  # como paquete
    from .configuracion import CONFIG_POR_DEFECTO, ConfigVision, cargar_config
    from .detectors.cubos import detectar_cubos
    from .detectors.rovers import detectar_rovers
    from .geometry.coordenadas import (
        ErrorGeometria, construir_sistema, detectar_marcadores, pose_camara,
    )
    from .geometry.distorsion import (
        ErrorCalibracion, FuenteRectificada, Rectificador, comparar_con_camara, elegir_perfil,
    )
    from .mundo import FASES, desde_detecciones
    from .publish.telemetria import PublicadorTelemetria
    from .sources.camara import ErrorCamara, FuenteCamara
    from .sources.generador_sintetico import FuenteSintetica
except ImportError:  # como script suelto
    from vision.configuracion import (  # type: ignore[no-redef]
        CONFIG_POR_DEFECTO, ConfigVision, cargar_config,
    )
    from vision.detectors.cubos import detectar_cubos  # type: ignore[no-redef]
    from vision.detectors.rovers import detectar_rovers  # type: ignore[no-redef]
    from vision.geometry.coordenadas import (  # type: ignore[no-redef]
        ErrorGeometria, construir_sistema, detectar_marcadores, pose_camara,
    )
    from vision.geometry.distorsion import (  # type: ignore[no-redef]
        ErrorCalibracion, FuenteRectificada, Rectificador, comparar_con_camara, elegir_perfil,
    )
    from vision.mundo import FASES, desde_detecciones  # type: ignore[no-redef]
    from vision.publish.telemetria import PublicadorTelemetria  # type: ignore[no-redef]
    from vision.sources.camara import ErrorCamara, FuenteCamara  # type: ignore[no-redef]
    from vision.sources.generador_sintetico import FuenteSintetica  # type: ignore[no-redef]

BASE_VISION = os.path.dirname(os.path.abspath(__file__))

#: Transiciones válidas de la ronda. La visión es árbitro y esta es su voz.
_TRANSICIONES = {
    "ready": ("READY", ("IDLE", "FINISHED", "READY")),
    "start": ("RUNNING", ("READY",)),
    "stop": ("FINISHED", ("RUNNING",)),
}


class Arbitro:
    """La fase de la ronda. La visión es árbitro y tiene que ser una sola voz.

    Se protege con un candado porque la escribe el hilo del teclado y la lee el
    de proceso. Es un dato chiquito, pero un dato compartido igual.

    Las transiciones son explícitas y las inválidas se rechazan avisando, en vez
    de aceptarse en silencio: escribir `start` sin haber preparado la cancha es
    un error de quien opera, y merece enterarse.
    """

    def __init__(self, inicial: str = "IDLE"):
        self._fase = inicial
        self._lock = threading.Lock()

    @property
    def fase(self) -> str:
        with self._lock:
            return self._fase

    def intentar(self, comando: str) -> str:
        destino, desde = _TRANSICIONES[comando]
        with self._lock:
            if self._fase not in desde:
                return "'{}' no es válido desde {} (se puede desde {})".format(
                    comando, self._fase, list(desde))
            anterior, self._fase = self._fase, destino
            return "fase: {} -> {}".format(anterior, destino)


def abrir_fuente(cfg: ConfigVision, args):
    """Devuelve `(fuente, descripción)`. Cámara por defecto; sintético si se pide.

    La cámara real pasa además por `FuenteRectificada`, que le quita la
    distorsión del lente **antes** de que nadie la mire. Las imágenes generadas
    no la necesitan: representan el cuadro ya rectificado a propósito.
    """
    if args.sintetico:
        return FuenteSintetica(cfg), "IMÁGENES GENERADAS (sin cámara)"

    camara = FuenteCamara(cfg.camara, indice=args.indice)
    primero, limite = None, time.monotonic() + 10.0
    while primero is None and time.monotonic() < limite:
        primero = camara.leer()
        time.sleep(0.01)
    if primero is None:
        camara.cerrar()
        raise ErrorCamara("la cámara no entregó imágenes")
    alto, ancho = primero.imagen.shape[:2]

    perfil = elegir_perfil(cfg.calibracion, BASE_VISION, ancho, alto,
                           nombre=args.camara, interactivo=sys.stdin.isatty())
    print(comparar_con_camara(perfil, ancho, alto).mensaje())
    rectificador = Rectificador(perfil, alpha=cfg.calibracion.alpha, tamano=(ancho, alto))
    fuente = FuenteRectificada(camara, rectificador)
    fuente.matriz_camara = rectificador.matriz_nueva  # la que necesita la pose
    return fuente, "cámara {} ({}x{})".format(perfil.camara, ancho, alto)


def procesar(cuadro, cfg, matriz_camara, fase):
    """De un cuadro al estado del mundo. Lanza si la geometría no se puede armar.

    Una sola pasada del detector de ArUco por cuadro: el mismo resultado sirve
    para armar las coordenadas y para encontrar los rovers.
    """
    detectados = detectar_marcadores(cuadro.imagen, cfg.marcadores_esquina.nombre_diccionario)
    sistema = construir_sistema(cuadro.imagen, cfg, detectados)
    pose = pose_camara(sistema, matriz_camara)
    return desde_detecciones(
        ts_ms=cuadro.ts_ms,
        fase=fase,
        rovers=detectar_rovers(detectados, sistema, cfg, pose),
        cubos=detectar_cubos(cuadro.imagen, sistema, cfg, pose),
    )


def _hilo_teclado(arbitro: Arbitro, salir: threading.Event) -> None:
    """Lee comandos por consola. La visión es árbitro; esta es su boca."""
    for linea in sys.stdin:
        if salir.is_set():
            return
        comando = linea.strip().lower()
        if comando in ("quit", "salir"):
            salir.set()
            return
        if comando in _TRANSICIONES:
            print("[fase] " + arbitro.intentar(comando), flush=True)
        elif comando:
            print("[fase] comandos: ready | start | stop | quit", flush=True)
    salir.set()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sistema de visión del Vision-Rover-Challenge.")
    parser.add_argument("--config", default=CONFIG_POR_DEFECTO)
    parser.add_argument("--sintetico", action="store_true",
                        help="correr SIN cámara, con imágenes generadas (hay que pedirlo)")
    parser.add_argument("--indice", type=int, default=None, help="índice de cámara")
    parser.add_argument("--camara", default=None, help="nombre del perfil de calibración")
    parser.add_argument("--fase", choices=FASES, default="IDLE", help="fase inicial")
    parser.add_argument("--duracion", type=float, default=0.0,
                        help="segundos a correr; 0 = hasta 'quit' o Ctrl-C")
    args = parser.parse_args(argv)

    cfg = cargar_config(args.config)
    try:
        fuente, descripcion = abrir_fuente(cfg, args)
    except (ErrorCamara, ErrorCalibracion) as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        return 2

    matriz = getattr(fuente, "matriz_camara", None)
    if matriz is None:  # fuente sintética: la matriz es la de su propia cámara
        matriz = fuente.verdad.camara.matriz

    arbitro = Arbitro(args.fase)
    publicador = PublicadorTelemetria(cfg, avisar=lambda t: print(t, flush=True))
    salir = threading.Event()

    print("=" * 70)
    print("SISTEMA DE VISIÓN — Vision-Rover-Challenge · protocolo v1")
    print("Entrada: {}".format(descripcion))
    if args.sintetico:
        print("")
        print("  ##################################################################")
        print("  ##  DATOS SINTÉTICOS: ESTO NO ES LA CANCHA REAL                 ##")
        print("  ##  Las posiciones son inventadas. No usar para una ronda.      ##")
        print("  ##################################################################")
    print("Cancha: {}x{} celdas de {:.0f} mm".format(
        cfg.tablero.cols, cfg.tablero.rows, cfg.tablero.cell_mm))
    print("Comandos: ready | start | stop | quit")
    print("=" * 70)

    publicador.arrancar()
    if sys.stdin and sys.stdin.isatty():
        threading.Thread(target=_hilo_teclado, args=(arbitro, salir),
                         name="teclado", daemon=True).start()

    cuadros = fallos = 0
    ultimo_error = ""
    proximo_informe = time.monotonic() + 5.0
    fin = time.monotonic() + args.duracion if args.duracion > 0 else float("inf")

    try:
        while not salir.is_set() and time.monotonic() < fin:
            cuadro = fuente.leer()
            if cuadro is None:
                time.sleep(0.005)
                continue
            cuadros += 1
            # ---- falla abierto -------------------------------------------
            # Si un cuadro no se puede procesar, NO se toca la casilla y se
            # sigue. La publicación continúa emitiendo el último estado bueno,
            # que envejece a la vista de todos. El sistema no se calla nunca.
            try:
                publicador.actualizar(procesar(cuadro, cfg, matriz, arbitro.fase))
            except ErrorGeometria as exc:
                fallos += 1
                ultimo_error = str(exc).split(".")[0]
            except Exception as exc:  # noqa: BLE001 — a propósito: nada tumba la ronda
                fallos += 1
                ultimo_error = "{}: {}".format(type(exc).__name__, exc)

            if time.monotonic() >= proximo_informe:
                proximo_informe += 5.0
                edad = publicador.edad_del_estado_ms()
                print("[estado] fase={} cuadros={} fallos={} emitidos={} clientes={} "
                      "pisados={} fps={:.1f} edad={}".format(
                          arbitro.fase, cuadros, fallos, publicador.emitidos,
                          publicador.clientes, publicador.pisados, fuente.fps_real,
                          "{} ms".format(edad) if edad is not None else "sin estado"),
                      flush=True)
                if ultimo_error:
                    print("[aviso] último problema: {}".format(ultimo_error), flush=True)
                    ultimo_error = ""
    except KeyboardInterrupt:
        pass
    finally:
        publicador.detener()
        fuente.cerrar()
        print("\nSistema detenido. Cuadros={} fallos={} mensajes publicados={}".format(
            cuadros, fallos, publicador.emitidos))
    return 0


if __name__ == "__main__":
    sys.exit(main())
