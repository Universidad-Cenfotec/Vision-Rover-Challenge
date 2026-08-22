"""Fuente de imágenes de la webcam USB real.

Cumple la misma interfaz que el generador sintético (ver `fuente.py`), así que
el resto del sistema puede usar cualquiera de las dos sin enterarse.

Por qué hay un hilo lector
--------------------------
`VideoCapture.read()` **bloquea** hasta que hay un cuadro. Si el procesamiento
lo llamara directamente, iría siempre al ritmo de la cámara y cualquier demora
propia se sumaría a la de ella.

Acá un hilo lee sin parar y deja el último cuadro en una **ranura de un solo
lugar**: si llega uno nuevo antes de que lo consuman, **pisa** al anterior. Es la
misma política del publicador —el último valor gana— por la misma razón: un
cuadro viejo no sirve para nada, y así el procesamiento nunca espera a la cámara.

Por qué los ajustes se verifican por efecto
-------------------------------------------
`cap.set()` devuelve un booleano y `cap.get()` devuelve un número, pero **los dos
mienten** en muchas cámaras: aceptan el valor, lo reportan de vuelta y siguen
haciendo lo que quieren. La única prueba confiable es mirar si **la imagen
cambió**: se toman dos valores muy distintos y se compara el resultado. Eso es lo
que hace `verificar_por_efecto`.

Esto importa por el problema del robot negro: con la exposición en automático, la
cámara sube la ganancia para "compensar" el robot oscuro y quema los marcadores
blancos. Saber si se puede fijar la exposición no es un detalle.
"""

from __future__ import annotations

import sys
import threading
import time
from collections import deque
from dataclasses import dataclass

import cv2
import numpy as np

try:  # como paquete
    from ..configuracion import Camara
    from .fuente import Cuadro, ahora_ms
except ImportError:  # como script suelto
    from vision.configuracion import Camara  # type: ignore[no-redef]
    from vision.sources.fuente import Cuadro, ahora_ms  # type: ignore[no-redef]


class ErrorCamara(Exception):
    """No se pudo abrir la cámara o dejó de entregar imágenes."""


_BACKENDS = {
    "avfoundation": cv2.CAP_AVFOUNDATION,
    "dshow": cv2.CAP_DSHOW,
    "msmf": cv2.CAP_MSMF,
    "v4l2": cv2.CAP_V4L2,
    "any": cv2.CAP_ANY,
}

#: Qué número significa "manual" en CAP_PROP_AUTO_EXPOSICION, por backend.
#: No hay una convención única y equivocarse deja la cámara en automático
#: creyendo que quedó en manual, que es el peor de los dos errores.
_MANUAL_AUTOEXP = {
    cv2.CAP_DSHOW: 0.25,
    cv2.CAP_MSMF: 0.25,
    cv2.CAP_AVFOUNDATION: 0.25,
    cv2.CAP_V4L2: 1.0,
    cv2.CAP_ANY: 0.25,
}


def backend_para(nombre: str) -> int:
    """Traduce el nombre del backend al número de OpenCV.

    `auto` elige el que corresponde al sistema operativo. En Windows se elige
    DSHOW y no MSMF porque expone mejor los controles de exposición y enfoque.
    """
    if nombre != "auto":
        return _BACKENDS[nombre]
    if sys.platform == "darwin":
        return cv2.CAP_AVFOUNDATION
    if sys.platform.startswith("win"):
        return cv2.CAP_DSHOW
    if sys.platform.startswith("linux"):
        return cv2.CAP_V4L2
    return cv2.CAP_ANY


def nombre_backend(codigo: int) -> str:
    for nombre, valor in _BACKENDS.items():
        if valor == codigo:
            return nombre
    return "desconocido({})".format(codigo)


# --------------------------------------------------------------------------
# Informes
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class InformeAjuste:
    """Qué pasó al intentar fijar un control de la cámara.

    Separa deliberadamente "la cámara dice que lo aceptó" de "tuvo efecto real",
    porque no son lo mismo y confundirlos es la forma más fácil de creer que la
    exposición está fija cuando no lo está.
    """

    nombre: str
    soportado: bool  # ¿el backend expone siquiera este control?
    solicitado: float | None
    antes: float
    despues: float
    reporta_aceptado: bool  # ¿el valor leído después coincide con el pedido?
    detalle: str

    @property
    def veredicto(self) -> str:
        if not self.soportado:
            return "NO SOPORTADO"
        return "ACEPTADO" if self.reporta_aceptado else "IGNORADO"


@dataclass(frozen=True, slots=True)
class InformeEfecto:
    """Si el ajuste realmente cambió la imagen. Esta es la prueba que vale."""

    nombre: str
    magnitud: str  # qué se midió: brillo, nitidez, color
    valor_a: float
    valor_b: float
    diferencia: float
    umbral: float
    confirmado: bool

    @property
    def veredicto(self) -> str:
        return "CONFIRMADO" if self.confirmado else "SIN EFECTO"


# --------------------------------------------------------------------------
# Medidas sobre la imagen
# --------------------------------------------------------------------------


def brillo_medio(imagen: np.ndarray) -> float:
    """Nivel de gris promedio (0-255). Sube o baja con la exposición."""
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY) if imagen.ndim == 3 else imagen
    return float(gris.mean())


def nitidez(imagen: np.ndarray) -> float:
    """Varianza del laplaciano: cuánto contraste de borde hay.

    Una imagen enfocada tiene bordes marcados y varianza alta; una desenfocada
    los tiene suaves y varianza baja.
    """
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY) if imagen.ndim == 3 else imagen
    return float(cv2.Laplacian(gris, cv2.CV_64F).var())


def relacion_azul_rojo(imagen: np.ndarray) -> float:
    """Cuánto azul hay respecto del rojo. Se mueve con el balance de blancos."""
    if imagen.ndim != 3:
        return 1.0
    azul = float(imagen[:, :, 0].mean())
    rojo = float(imagen[:, :, 2].mean())
    return azul / rojo if rojo > 1e-6 else 1.0


# --------------------------------------------------------------------------
# La fuente
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CamaraDetectada:
    """Una cámara conocida, con lo que se sepa de ella para reconocerla.

    `responde` es `None` cuando no se la sondeó. Se distingue de `False` a
    propósito: "no la probé" y "la probé y no contestó" son cosas distintas, y
    mezclarlas fue justamente lo que hizo que el sistema eligiera sola la cámara
    equivocada.
    """

    indice: int
    nombre: str
    detalle: str
    integrada: bool
    ancho: int = 0
    alto: int = 0
    responde: bool | None = None

    def linea(self) -> str:
        tipo = "integrada" if self.integrada else "USB / externa"
        if self.responde is None:
            estado = ""
        elif self.responde:
            estado = "   {}x{}".format(self.ancho, self.alto)
        else:
            estado = "   (no respondió al sondeo)"
        detalle = "  ·  {}".format(self.detalle) if self.detalle else ""
        return "  [{}]  {:<24}  {:<14}{}{}".format(
            self.indice, self.nombre[:24], tipo, estado, detalle)


#: Palabras que delatan una cámara integrada. Sirven para sugerir la correcta:
#: en este proyecto la que interesa es siempre la USB que mira el tablero.
_PISTAS_INTEGRADA = ("macbook", "facetime", "integrated", "built-in", "internal", "isight")


def nombres_del_sistema() -> list[tuple[str, str]]:
    """Pide al sistema operativo los nombres de las cámaras, en orden.

    OpenCV **no expone nombres de dispositivo** por ninguna de sus APIs: solo
    índices. Sin nombre, elegir entre dos cámaras es adivinar. Así que se le
    pregunta al sistema.

    La correspondencia entre esta lista y los índices de OpenCV es **por
    posición**, que es lo que se observa en la práctica pero no está garantizado
    por ninguna documentación. Por eso el menú además muestra la resolución y
    pide confirmación visual: el nombre orienta, los ojos deciden.

    Si algo falla devuelve una lista vacía y el resto sigue funcionando sin
    nombres.
    """
    import json
    import subprocess

    try:
        if sys.platform == "darwin":
            salida = subprocess.run(
                ["system_profiler", "-json", "SPCameraDataType"],
                capture_output=True, text=True, timeout=10, check=False).stdout
            datos = json.loads(salida).get("SPCameraDataType", [])
            return [(c.get("_name", "?"), c.get("spcamera_model-id", "")) for c in datos]

        if sys.platform.startswith("win"):
            orden = ("Get-CimInstance Win32_PnPEntity | "
                     "Where-Object {$_.PNPClass -eq 'Camera' -or $_.PNPClass -eq 'Image'} | "
                     "Select-Object -ExpandProperty Name")
            salida = subprocess.run(["powershell", "-NoProfile", "-Command", orden],
                                    capture_output=True, text=True, timeout=10, check=False).stdout
            return [(l.strip(), "") for l in salida.splitlines() if l.strip()]

        if sys.platform.startswith("linux"):
            import glob
            nombres = []
            for ruta in sorted(glob.glob("/sys/class/video4linux/video*/name")):
                with open(ruta, encoding="utf-8", errors="replace") as f:
                    nombres.append((f.read().strip(), ruta.split("/")[4]))
            return nombres
    except Exception:  # noqa: BLE001 — sin nombres se sigue igual, con menos ayuda
        return []
    return []


def camaras_del_sistema() -> list[CamaraDetectada]:
    """Las cámaras que el sistema operativo declara, SIN abrir ninguna.

    Es la lista que se usa para el menú, y a propósito **no sondea**: abrir cada
    cámara para ver si contesta es lento y poco confiable —una webcam puede no
    responder en el primer intento y sí en el segundo—, y usar ese resultado
    para decidir qué mostrar termina ocultando la cámara correcta.

    Para elegir alcanza con el nombre. Si la elegida después no abre, el error
    de apertura ya explica qué revisar.
    """
    camaras = []
    for indice, (nombre, detalle) in enumerate(nombres_del_sistema()):
        texto = "{} {}".format(nombre, detalle).lower()
        camaras.append(
            CamaraDetectada(
                indice=indice, nombre=nombre, detalle=detalle,
                integrada=any(p in texto for p in _PISTAS_INTEGRADA),
            )
        )
    return camaras


def describir_camaras(backend: str = "auto", segundos: float = 3.0) -> list[CamaraDetectada]:
    """Encuentra las cámaras que responden y les pone nombre y resolución.

    Si el sistema operativo dice cuántas cámaras hay, **no se sondea más allá de
    esa cantidad**. Sondear índices inexistentes no aporta nada y ensucia la
    pantalla con los "out device of bound" que OpenCV escribe directamente por su
    cuenta, sin pasar por su sistema de mensajes: no hay forma de silenciarlos
    desde Python, así que la solución es no provocarlos.
    """
    conocidas = camaras_del_sistema()
    cuantos = len(conocidas) if conocidas else 6
    respuestas = {i: (a, al) for i, a, al in camaras_disponibles(
        maximo=cuantos, backend=backend, segundos=segundos)}

    if not conocidas:  # el sistema no dio nombres: se arma con lo que se sondeó
        return [
            CamaraDetectada(indice=i, nombre="cámara {}".format(i), detalle="",
                            integrada=False, ancho=a, alto=al, responde=True)
            for i, (a, al) in sorted(respuestas.items())
        ]

    return [
        CamaraDetectada(
            indice=c.indice, nombre=c.nombre, detalle=c.detalle, integrada=c.integrada,
            ancho=respuestas.get(c.indice, (0, 0))[0],
            alto=respuestas.get(c.indice, (0, 0))[1],
            responde=c.indice in respuestas,
        )
        for c in conocidas
    ]


def menu_camara(camaras: list[CamaraDetectada], por_defecto: int = 0) -> int | None:
    """Muestra qué cámaras hay y deja elegir el índice. Devuelve el índice o None.

    Se pregunta en vez de adivinar porque **adivinar no funciona**: con una
    cámara integrada y una USB, "la primera que responde" es una moneda al aire,
    y equivocarse se manifiesta como una calibración hecha con la cámara
    equivocada, que no da ningún error.

    Por qué los nombres se listan APARTE de los índices
    ---------------------------------------------------
    El orden en que el sistema operativo lista las cámaras **no coincide
    necesariamente** con el orden de los índices de OpenCV. En un MacBook con una
    webcam USB se comprobó que están **invertidos**: macOS lista primero la
    integrada, y OpenCV le da el índice 0 a la USB.

    Mostrar el nombre pegado al índice sería mentir con seguridad, que es peor
    que no informar. Así que los nombres se dan como referencia de qué hay
    conectado, y la confirmación la hace el ojo al ver la imagen.
    """
    indices = sorted({c.indice for c in camaras})
    print()
    if camaras:
        print("  CÁMARAS CONECTADAS  (nombres según el sistema; el orden NO es el índice)")
        print("  " + "-" * 70)
        for camara in camaras:
            tipo = "integrada" if camara.integrada else "USB / externa"
            detalle = "  ·  {}".format(camara.detalle) if camara.detalle else ""
            print("    ·  {:<24}  {:<14}{}".format(camara.nombre[:24], tipo, detalle))
        print("  " + "-" * 70)
    print()
    print("  ⚠  El nombre es ORIENTATIVO. El orden del sistema no siempre coincide")
    print("     con el índice; en algunos equipos están invertidos. La forma segura")
    print("     de saberlo es mirar la imagen: si no es la que querías, salí con q")
    print("     y volvé a correr eligiendo el otro índice.")
    print()
    print("  Índices disponibles: {}".format(", ".join(str(i) for i in indices)))

    while True:
        try:
            respuesta = input(
                "\n  Elegí el índice de la cámara que mira el tablero "
                "[Enter = {}, q = salir]: ".format(por_defecto)).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if respuesta in ("q", "salir"):
            return None
        if respuesta == "":
            return por_defecto
        if respuesta.isdigit() and int(respuesta) in indices:
            return int(respuesta)
        print("  Valor inválido. Opciones: {}".format(indices))


def _responde(indice: int, backend: int, segundos: float) -> bool:
    """¿Este índice entrega al menos un cuadro si se le da tiempo?"""
    cap = cv2.VideoCapture(indice, backend)
    try:
        if not cap.isOpened():
            return False
        limite = time.monotonic() + segundos
        while time.monotonic() < limite:
            ok, imagen = cap.read()
            if ok and imagen is not None:
                return True
            time.sleep(0.05)
        return False
    finally:
        cap.release()


def elegir_camara(cfg: Camara, indice_pedido: int | str | None = None) -> tuple[int, str | None]:
    """Decide qué índice de cámara usar. Devuelve `(indice, aviso)`.

    Por qué no se confía en un número fijo
    --------------------------------------
    El índice de una webcam USB **no es estable**: depende de qué se enchufó
    primero, de si hay una cámara integrada y de si el sistema se reinició. Un
    número escrito en la configuración funciona hoy y falla mañana, con un error
    que parece de permisos o de cámara rota y no lo es.

    Por eso: si el índice pedido no responde, se prueban los demás y se usa el
    primero que entregue imágenes, avisando cuál se eligió. Es preferible
    funcionar con un aviso a fallar por un número desactualizado.
    """
    pedido = cfg.indice if indice_pedido is None else indice_pedido
    backend = backend_para(cfg.backend)
    espera = max(2.0, cfg.segundos_arranque / 2.0)

    # Un número explícito manda, si responde. Es el camino rápido: no se buscan
    # las demás cámaras ni se molesta al usuario.
    if isinstance(pedido, int):
        if _responde(pedido, backend, espera):
            return pedido, None
        motivo = "el índice {} no entregó imágenes".format(pedido)
    else:
        motivo = ""

    modo = str(pedido).lower() if not isinstance(pedido, int) else ""
    interactivo = sys.stdin is not None and sys.stdin.isatty()

    # --- el menú, cuando hay alguien para contestar -----------------------
    # Se arma con la lista del sistema operativo y NO con el resultado de
    # sondear. Sondear es lento y poco confiable, y usarlo para decidir qué
    # mostrar fue exactamente lo que hizo que se eligiera sola la cámara
    # equivocada: si la del tablero no contestaba en ese intento, desaparecía
    # del menú y quedaba la integrada como única opción.
    if modo == "menu" and interactivo:
        conocidas = camaras_del_sistema()
        if len(conocidas) > 1:
            elegido = menu_camara(conocidas, por_defecto=0)
            if elegido is None:
                raise ErrorCamara("elección de cámara cancelada.")
            print("  Usando el índice {}. Para no elegir cada vez, poné "
                  "\"indice\": {} en vision/config_vision.json.\n".format(elegido, elegido))
            return elegido, None
        if len(conocidas) == 1:
            return conocidas[0].indice, None  # una sola: preguntar sería puro trámite

    # --- sin nadie a quién preguntar: hay que sondear y decidir -----------
    print("\n  Buscando cámaras (hasta {:.0f} s cada una)...".format(espera))
    camaras = [c for c in describir_camaras(backend=cfg.backend, segundos=espera) if c.responde]
    if not camaras:
        # Que falle más adelante, con el diagnóstico completo de `_calentar`.
        return (pedido if isinstance(pedido, int) else 0), None

    elegido = camaras[0].indice
    nombre = "índice {}".format(elegido)
    aviso = None
    if isinstance(pedido, int) and elegido != pedido:
        aviso = (
            "{}; se usa el índice {} ({}), que sí responde. Si es la cámara "
            "equivocada, pasá --indice N o corregí 'camara.indice'.".format(
                motivo, elegido, nombre)
        )
    elif len(camaras) > 1:
        aviso = (
            "hay {} cámaras y se eligió sola la {} ({}). Si no es la del tablero, "
            "pasá --indice N.".format(len(camaras), elegido, nombre)
        )
    return elegido, aviso


class FuenteCamara:
    """Webcam USB con ajustes fijos y lectura que no bloquea."""

    def __init__(self, cfg: Camara, indice: int | str | None = None):
        self.cfg = cfg
        self.backend = backend_para(cfg.backend)
        self.indice_camara, aviso_indice = elegir_camara(cfg, indice)

        self._lock_cap = threading.Lock()  # VideoCapture no es seguro entre hilos
        self._cap = cv2.VideoCapture(self.indice_camara, self.backend)
        if not self._cap.isOpened():
            raise ErrorCamara(
                "no se pudo abrir la cámara {} con el backend {}. Revisar que esté "
                "conectada, que no la esté usando otra aplicación, y —en macOS— que "
                "la terminal tenga permiso de cámara.".format(
                    self.indice_camara, nombre_backend(self.backend)
                )
            )

        self._pedir_formato()
        self.aviso: str | None = aviso_indice
        self.formato_replegado = False
        self._calentar()
        self.informes: tuple[InformeAjuste, ...] = self._aplicar_ajustes()

        # --- ranura de un solo cuadro, el último gana ---
        self._slot: Cuadro | None = None
        self._consumido = True
        self._lock = threading.Lock()
        self._parar = threading.Event()
        self.leidos = 0
        self.pisados = 0
        self.fallos = 0
        self._marcas = deque(maxlen=90)  # para calcular fps reales

        self._hilo = threading.Thread(target=self._leer_sin_parar, name="camara", daemon=True)
        self._hilo.start()

    def _avisar(self, texto: str) -> None:
        """Suma un aviso sin pisar los anteriores.

        Puede haber más de uno a la vez —índice resuelto solo, repliegue de
        formato, cuadros negros— y perder uno deja al usuario sin la mitad de
        la explicación.
        """
        self.aviso = texto if not self.aviso else self.aviso + "\n" + texto

    # -- apertura ----------------------------------------------------------

    def _pedir_formato(self) -> None:
        """Pide resolución, fps y códec. La cámara puede dar otra cosa.

        El códec importa más de lo que parece: muchas webcams entregan 1080p a
        5 fps sin comprimir y a 30 fps en MJPG.
        """
        c = self.cfg
        if c.fourcc:
            self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*c.fourcc))
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, c.ancho)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, c.alto)
        self._cap.set(cv2.CAP_PROP_FPS, c.fps)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, c.buffersize)

    def _leer_con_paciencia(self, segundos: float, cuantos: int) -> list[np.ndarray]:
        """Lee cuadros dándole tiempo a la cámara a arrancar.

        Esperar por TIEMPO y no por cantidad de intentos es la diferencia entre
        que funcione y que no: una webcam USB en macOS puede tardar más de un
        segundo en entregar el primer cuadro después de que se le pide una
        resolución, y un puñado de `read()` inmediatos fallan todos antes de que
        el dispositivo haya arrancado siquiera.
        """
        imagenes: list[np.ndarray] = []
        limite = time.monotonic() + segundos
        while time.monotonic() < limite and len(imagenes) < cuantos:
            ok, imagen = self._cap.read()
            if ok and imagen is not None:
                imagenes.append(imagen)
            else:
                time.sleep(0.05)  # darle aire al dispositivo en vez de martillarlo
        return imagenes

    def _calentar(self) -> None:
        """Espera a que la cámara entregue imágenes, con repliegue de formato.

        Se descartan los primeros cuadros porque las cámaras arrancan en
        automático y tardan en estabilizarse.

        Si con el formato pedido no llega ni un cuadro, se reabre la cámara **sin
        pedir nada** y se vuelve a intentar: muchas webcams rechazan una
        combinación de resolución y códec que no soportan y directamente dejan de
        entregar imágenes, sin devolver ningún error. Es preferible trabajar a la
        resolución que la cámara quiera antes que no trabajar.

        Si macOS denegó el permiso, la captura "funciona" pero entrega cuadros
        negros o ninguno; eso también se detecta y se dice con todas las letras.
        """
        espera = max(2.0, float(getattr(self.cfg, "segundos_arranque", 6.0)))
        imagenes = self._leer_con_paciencia(espera, max(1, self.cfg.cuadros_calentamiento))

        if not imagenes:
            # Plan B: la cámara con su formato nativo, sin pedirle nada.
            with self._lock_cap:
                self._cap.release()
                self._cap = cv2.VideoCapture(self.indice_camara, self.backend)
                abierta = self._cap.isOpened()
            if abierta:
                imagenes = self._leer_con_paciencia(espera, max(1, self.cfg.cuadros_calentamiento))
            if imagenes:
                self.formato_replegado = True
                self._avisar(
                    "la cámara NO aceptó el formato pedido ({}x{} {}) y dejó de entregar "
                    "imágenes. Se replegó a su formato nativo ({}x{}). Para evitarlo, "
                    "ajustá 'camara.ancho', 'camara.alto' y 'camara.fourcc' en "
                    "config_vision.json a un modo que la cámara sí soporte.".format(
                        self.cfg.ancho, self.cfg.alto, self.cfg.fourcc or "sin códec",
                        int(self._get(cv2.CAP_PROP_FRAME_WIDTH)),
                        int(self._get(cv2.CAP_PROP_FRAME_HEIGHT)),
                    )
                )

        if not imagenes:
            raise ErrorCamara(
                "la cámara {} abrió pero no entregó ninguna imagen en {:.0f} segundos, "
                "ni con el formato pedido ni con el nativo.\n"
                "Causas posibles, en orden de probabilidad:\n"
                "  1. PERMISO DE CÁMARA. En macOS: Ajustes del Sistema → Privacidad y\n"
                "     seguridad → Cámara, habilitá la aplicación desde la que lanzás esto\n"
                "     (Visual Studio Code, iTerm, Terminal...) y REINICIALA por completo.\n"
                "     Si nunca apareció el diálogo de permiso, es casi seguro esto.\n"
                "  2. Otra aplicación la tiene tomada (Zoom, Teams, Photo Booth, una\n"
                "     pestaña del navegador, u otra ventana de esta misma herramienta).\n"
                "  3. Índice equivocado: probá 'python -m vision.tools.diagnostico_camara\n"
                "     --listar' para ver cuáles responden, y después --indice N.\n"
                "  4. El mediador de cámara de macOS quedó colgado:\n"
                "     sudo killall VDCAssistant\n"
                "  5. Desenchufar y volver a enchufar la cámara USB.".format(
                    self.indice_camara, espera)
            )

        if max(brillo_medio(i) for i in imagenes) < 2.0:
            self._avisar(
                "todos los cuadros llegan NEGROS. En macOS esto casi siempre es el "
                "permiso de cámara denegado: Ajustes del Sistema → Privacidad y "
                "seguridad → Cámara, y habilitá la aplicación desde la que lanzaste "
                "esto (por ejemplo, Visual Studio Code). Después hay que reiniciarla."
            )

    # -- acceso protegido a las propiedades --------------------------------

    def _get(self, prop: int) -> float:
        with self._lock_cap:
            return float(self._cap.get(prop))

    def _set(self, prop: int, valor: float) -> bool:
        with self._lock_cap:
            return bool(self._cap.set(prop, valor))

    # -- ajustes -----------------------------------------------------------

    def _aplicar_ajustes(self) -> tuple[InformeAjuste, ...]:
        c = self.cfg
        manual = (
            c.valor_manual_autoexposicion
            if c.valor_manual_autoexposicion is not None
            else _MANUAL_AUTOEXP.get(self.backend, 0.25)
        )
        informes = []
        if c.exposicion.fijar:
            informes.append(
                self._fijar("exposición", cv2.CAP_PROP_AUTO_EXPOSURE, manual,
                            cv2.CAP_PROP_EXPOSURE, c.exposicion.valor)
            )
        if c.enfoque.fijar:
            informes.append(
                self._fijar("enfoque", cv2.CAP_PROP_AUTOFOCUS, 0.0,
                            cv2.CAP_PROP_FOCUS, c.enfoque.valor)
            )
        if c.balance_blancos.fijar:
            informes.append(
                self._fijar("balance de blancos", cv2.CAP_PROP_AUTO_WB, 0.0,
                            cv2.CAP_PROP_WB_TEMPERATURE, c.balance_blancos.valor)
            )
        return tuple(informes)

    def _fijar(
        self, nombre: str, prop_auto: int, valor_manual: float, prop: int, valor: float
    ) -> InformeAjuste:
        """Pasa un control a manual y le fija un valor, y reporta qué pasó.

        Primero se apaga el automático y recién después se escribe el valor: al
        revés, muchas cámaras descartan el valor porque el automático lo pisa.
        """
        auto_antes = self._get(prop_auto)
        auto_ok = self._set(prop_auto, valor_manual)
        auto_despues = self._get(prop_auto)
        # Algunas cámaras necesitan un instante para aplicar el cambio de modo.
        time.sleep(0.05)

        antes = self._get(prop)
        soportado = antes != -1.0
        self._set(prop, valor)
        time.sleep(0.05)
        despues = self._get(prop)

        # "Aceptado" es que el valor leído se parezca al pedido. Se usa una
        # tolerancia porque las cámaras cuantizan: pedís -6 y te dan -6.0 o -5.
        tolerancia = max(0.5, abs(valor) * 0.05)
        reporta = soportado and abs(despues - valor) <= tolerancia

        detalle = "automático: {} -> {} ({})".format(
            _fmt(auto_antes), _fmt(auto_despues),
            "cambió" if auto_antes != auto_despues else ("aceptó" if auto_ok else "sin cambio"),
        )
        if not soportado:
            detalle = "el backend {} no expone este control. {}".format(
                nombre_backend(self.backend), detalle
            )
        elif not reporta and abs(antes - valor) <= tolerancia:
            detalle = "ya estaba en el valor pedido. " + detalle

        return InformeAjuste(
            nombre=nombre,
            soportado=soportado,
            solicitado=valor,
            antes=antes,
            despues=despues,
            reporta_aceptado=reporta,
            detalle=detalle,
        )

    # -- lectura -----------------------------------------------------------

    def _leer_sin_parar(self) -> None:
        """Hilo lector: consume la cámara sin descanso y deja el último cuadro.

        Falla abierto: un `read()` que falla no tumba el hilo; se cuenta y se
        sigue, porque una webcam USB puede perder un cuadro sin que eso sea una
        falla del sistema.
        """
        while not self._parar.is_set():
            try:
                with self._lock_cap:
                    ok, imagen = self._cap.read()
            except Exception:  # noqa: BLE001 — fail-open a propósito
                ok, imagen = False, None
            if not ok or imagen is None:
                self.fallos += 1
                time.sleep(0.01)
                continue
            with self._lock:
                if self._slot is not None and not self._consumido:
                    self.pisados += 1  # nadie lo usó: se descarta, no se encola
                self.leidos += 1
                self._slot = Cuadro(imagen=imagen, ts_ms=ahora_ms(), indice=self.leidos)
                self._consumido = False
                self._marcas.append(time.monotonic())

    def leer(self) -> Cuadro | None:
        """Último cuadro disponible. No bloquea."""
        with self._lock:
            self._consumido = True
            return self._slot

    def esperar_cuadro(self, timeout: float = 5.0) -> Cuadro:
        """Espera hasta que haya un cuadro nuevo. Solo para medir, no para el flujo.

        El flujo normal usa `leer()`, que nunca espera. Esta versión existe para
        las pruebas de efecto, donde sí hace falta asegurarse de estar mirando
        una imagen tomada DESPUÉS de cambiar un ajuste.
        """
        ultimo = self._slot.indice if self._slot else 0
        limite = time.monotonic() + timeout
        while time.monotonic() < limite:
            cuadro = self.leer()
            if cuadro is not None and cuadro.indice > ultimo:
                return cuadro
            time.sleep(0.005)
        raise ErrorCamara("la cámara dejó de entregar imágenes ({} s sin cuadros)".format(timeout))

    # -- estado ------------------------------------------------------------

    @property
    def fps_real(self) -> float:
        with self._lock:
            marcas = list(self._marcas)
        if len(marcas) < 2:
            return 0.0
        lapso = marcas[-1] - marcas[0]
        return (len(marcas) - 1) / lapso if lapso > 0 else 0.0

    def formato_negociado(self) -> dict[str, object]:
        """Lo que la cámara realmente entrega, que rara vez es lo pedido."""
        fourcc = int(self._get(cv2.CAP_PROP_FOURCC))
        letras = "".join(chr((fourcc >> (8 * i)) & 0xFF) for i in range(4)) if fourcc else "?"
        return {
            "ancho": int(self._get(cv2.CAP_PROP_FRAME_WIDTH)),
            "alto": int(self._get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "fps_declarado": self._get(cv2.CAP_PROP_FPS),
            "fourcc": letras.strip("\x00 ") or "?",
            "backend": nombre_backend(self.backend),
            "indice": self.indice_camara,
        }

    def cerrar(self) -> None:
        self._parar.set()
        if self._hilo.is_alive():
            self._hilo.join(2.0)
        with self._lock_cap:
            self._cap.release()

    def __enter__(self) -> "FuenteCamara":
        return self

    def __exit__(self, *_) -> None:
        self.cerrar()


# --------------------------------------------------------------------------
# Verificación por efecto — la prueba que vale
# --------------------------------------------------------------------------


def _promedio_de(fuente: FuenteCamara, medida, descartar: int = 6, promediar: int = 4) -> float:
    """Toma cuadros frescos y promedia una medida sobre ellos.

    Se descartan los primeros porque un cambio de ajuste tarda algunos cuadros en
    verse; se promedian varios porque una sola imagen tiene ruido.
    """
    for _ in range(descartar):
        fuente.esperar_cuadro()
    valores = [medida(fuente.esperar_cuadro().imagen) for _ in range(promediar)]
    return float(np.mean(valores))


def verificar_por_efecto(fuente: FuenteCamara) -> tuple[InformeEfecto, ...]:
    """Comprueba si los ajustes cambian la imagen de verdad.

    Para cada control se fijan dos valores muy distintos y se mide la imagen en
    cada uno. Si no cambia nada, la cámara ignoró el ajuste **por más que haya
    dicho que lo aceptaba**.

    Al terminar restaura los valores de la configuración, para dejar la cámara
    como estaba.
    """
    c = fuente.cfg
    u = c.umbrales
    informes = []

    pruebas = (
        ("exposición", "brillo medio", cv2.CAP_PROP_EXPOSURE, c.exposicion,
         brillo_medio, u.brillo_min, False),
        ("enfoque", "nitidez", cv2.CAP_PROP_FOCUS, c.enfoque,
         nitidez, u.nitidez_rel_min, True),
        ("balance de blancos", "relación azul/rojo", cv2.CAP_PROP_WB_TEMPERATURE,
         c.balance_blancos, relacion_azul_rojo, u.color_rel_min, True),
    )

    for nombre, magnitud, prop, ajuste, medida, umbral, relativo in pruebas:
        if not ajuste.fijar:
            continue
        fuente._set(prop, ajuste.prueba_a)
        valor_a = _promedio_de(fuente, medida)
        fuente._set(prop, ajuste.prueba_b)
        valor_b = _promedio_de(fuente, medida)
        fuente._set(prop, ajuste.valor)  # dejar la cámara como estaba

        bruta = abs(valor_a - valor_b)
        diferencia = bruta / max(abs(valor_a), abs(valor_b), 1e-9) if relativo else bruta
        informes.append(
            InformeEfecto(
                nombre=nombre,
                magnitud=magnitud,
                valor_a=valor_a,
                valor_b=valor_b,
                diferencia=diferencia,
                umbral=umbral,
                confirmado=diferencia >= umbral,
            )
        )
    return tuple(informes)


def camaras_disponibles(
    maximo: int = 6, backend: str = "auto", segundos: float = 3.0
) -> list[tuple[int, int, int]]:
    """Prueba índices de cámara y devuelve `(indice, ancho, alto)` de las que responden.

    Sirve cuando hay una cámara integrada y una USB y no se sabe cuál es cuál; la
    resolución que entrega cada una suele alcanzar para distinguirlas.

    Espera hasta `segundos` por cada índice. Una sola lectura inmediata —que es
    lo que hacía antes— descarta cámaras perfectamente buenas: una webcam USB
    puede tardar más de un segundo en entregar el primer cuadro, y ese falso
    negativo manda a buscar el problema donde no está.

    Corta al segundo índice seguido que ni siquiera abre, para no llenar la
    pantalla con los avisos de "out of bound" de OpenCV.
    """
    codigo = backend_para(backend)
    encontradas: list[tuple[int, int, int]] = []
    fallos_seguidos = 0
    for i in range(maximo):
        cap = cv2.VideoCapture(i, codigo)
        try:
            if not cap.isOpened():
                fallos_seguidos += 1
                if fallos_seguidos >= 2:
                    break
                continue
            fallos_seguidos = 0
            limite = time.monotonic() + segundos
            while time.monotonic() < limite:
                ok, imagen = cap.read()
                if ok and imagen is not None:
                    encontradas.append((i, imagen.shape[1], imagen.shape[0]))
                    break
                time.sleep(0.05)
        finally:
            cap.release()
    return encontradas


def _fmt(valor: float) -> str:
    return "n/d" if valor == -1.0 else "{:g}".format(valor)
