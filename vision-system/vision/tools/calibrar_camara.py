"""Calibra la distorsión del lente con un patrón de ajedrez, y la verifica.

    python -m vision.tools.calibrar_camara               # capturar y calibrar
    python -m vision.tools.calibrar_camara --verificar   # ver el antes y después

Por qué la captura es guiada y no "sacá 15 fotos"
-------------------------------------------------
Quince vistas todas de frente y en el centro calibran **peor** que diez bien
repartidas. La distorsión es más fuerte en los bordes: si el patrón nunca pasa
por ahí, el lente queda mal medido justo donde más importa. Y sin vistas
inclinadas, la distancia focal y la distancia al patrón se confunden entre sí y
la solución queda mal determinada.

Por eso la herramienta lleva la cuenta de **zonas del cuadro, distancias e
inclinaciones**, y solo da por suficiente cuando hay variedad de verdad.

Por qué se verifica también con los ojos
----------------------------------------
El error de reproyección puede salir bajo y la calibración estar mal: si el
patrón se imprimió escalado, el ajuste es coherente consigo mismo y el número no
lo delata. Mirar líneas que uno **sabe** que son rectas —las del tablero de la
cancha— y ver que quedaron rectas, comprueba algo que el número no puede.
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys
import time

import cv2
import numpy as np

try:  # como paquete
    from ..configuracion import CONFIG_POR_DEFECTO, cargar_config
    from ..geometry.distorsion import (
        ErrorCalibracion,
        PerfilCamara,
        Rectificador,
        comparar_con_camara,
        elegir_perfil,
        guardar_perfil,
        nombre_archivo,
        perfiles_disponibles,
    )
    from ..sources.camara import ErrorCamara, FuenteCamara
    from .panel import AMBAR, BLANCO, GRIS, Panel, Tipografia, escala_para
    from .panel import ROJO as ROJO_P, VERDE as VERDE_P
except ImportError:  # como script suelto
    from vision.configuracion import CONFIG_POR_DEFECTO, cargar_config  # type: ignore[no-redef]
    from vision.geometry.distorsion import (  # type: ignore[no-redef]
        ErrorCalibracion, PerfilCamara, Rectificador, comparar_con_camara, elegir_perfil,
        guardar_perfil, nombre_archivo, perfiles_disponibles,
    )
    from vision.sources.camara import ErrorCamara, FuenteCamara  # type: ignore[no-redef]
    from vision.tools.panel import (  # type: ignore[no-redef]
        AMBAR, BLANCO, GRIS, Panel, Tipografia, escala_para,
        ROJO as ROJO_P, VERDE as VERDE_P,
    )

BASE_VISION = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Colores en BGR para lo que se dibuja con OpenCV sobre el video. El panel usa
# los de `panel.py`, que van en RGB: son espacios distintos y mezclarlos pinta
# los avisos de un color equivocado.
VERDE = (60, 200, 60)
ROJO = (60, 60, 235)
AMARILLO = (40, 200, 240)
_BLANCO_BGR = (245, 245, 245)
_GRIS_BGR = (150, 150, 150)


# --------------------------------------------------------------------------
# Detección del patrón y medidas de la vista
# --------------------------------------------------------------------------


def detectar_patron(imagen: np.ndarray, tamano: tuple[int, int]):
    """Busca el ajedrezado. Devuelve las esquinas con precisión subpíxel o None.

    Se usa `findChessboardCornersSB` porque es más robusto con luz despareja y
    ya trae el refinamiento subpíxel; si no lo encuentra, se cae al detector
    clásico más `cornerSubPix`, que a veces resuelve casos difíciles.
    """
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY) if imagen.ndim == 3 else imagen
    ok, esquinas = cv2.findChessboardCornersSB(gris, tamano, cv2.CALIB_CB_EXHAUSTIVE)
    if ok:
        return esquinas
    ok, esquinas = cv2.findChessboardCorners(
        gris, tamano,
        cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE | cv2.CALIB_CB_FAST_CHECK,
    )
    if not ok:
        return None
    criterio = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    return cv2.cornerSubPix(gris, esquinas, (11, 11), (-1, -1), criterio)


def _esquinas_exteriores(esquinas: np.ndarray, tamano: tuple[int, int]) -> np.ndarray:
    """Las cuatro puntas del ajedrezado, en orden."""
    cols, filas = tamano
    p = esquinas.reshape(filas, cols, 2)
    return np.array([p[0, 0], p[0, -1], p[-1, -1], p[-1, 0]], dtype=np.float64)


def inclinacion_de(esquinas: np.ndarray, tamano: tuple[int, int]) -> float:
    """Cuán oblicua es la vista, entre 0 (de frente) y ~1.

    Se mide por la deformación del contorno: visto de frente, los lados opuestos
    miden lo mismo y las diagonales también. Cuanto más se aparta de eso, más
    inclinado está el patrón.
    """
    q = _esquinas_exteriores(esquinas, tamano)
    lados = [np.linalg.norm(q[(i + 1) % 4] - q[i]) for i in range(4)]
    diagonales = [np.linalg.norm(q[2] - q[0]), np.linalg.norm(q[3] - q[1])]
    def desvio(a, b):
        return abs(a - b) / max(a, b, 1e-9)
    return float(max(desvio(lados[0], lados[2]), desvio(lados[1], lados[3]),
                     desvio(diagonales[0], diagonales[1])))


def zona_de(esquinas: np.ndarray, ancho: int, alto: int) -> tuple[int, int]:
    """En cuál de las 9 zonas del cuadro está el centro del patrón."""
    centro = esquinas.reshape(-1, 2).mean(axis=0)
    col = min(2, max(0, int(centro[0] / (ancho / 3.0))))
    fila = min(2, max(0, int(centro[1] / (alto / 3.0))))
    return (fila, col)


def tramo_distancia(esquinas: np.ndarray, ancho: int, alto: int) -> str:
    """Cerca, media o lejos, según cuánto del cuadro ocupa el patrón."""
    q = _esquinas_exteriores(esquinas, (2, 2)) if esquinas.shape[0] == 4 else esquinas.reshape(-1, 2)
    x0, y0 = q.min(axis=0)
    x1, y1 = q.max(axis=0)
    fraccion = ((x1 - x0) * (y1 - y0)) / float(ancho * alto)
    if fraccion > 0.28:
        return "cerca"
    if fraccion > 0.10:
        return "media"
    return "lejos"


# --------------------------------------------------------------------------
# Progreso de la captura
# --------------------------------------------------------------------------


class Cobertura:
    """Lleva la cuenta de qué variedad de vistas se juntó.

    Existe porque el número de capturas no dice nada por sí solo: lo que decide
    si la calibración va a salir bien es que las vistas sean distintas entre sí.
    """

    def __init__(self, cal):
        self.cal = cal
        self.zonas: set[tuple[int, int]] = set()
        self.distancias: set[str] = set()
        self.inclinadas = 0
        self.total = 0

    def registrar(self, zona, distancia, inclinacion) -> None:
        self.zonas.add(zona)
        self.distancias.add(distancia)
        if inclinacion >= self.cal.inclinacion_min:
            self.inclinadas += 1
        self.total += 1

    def aporta(self, zona, distancia, inclinacion) -> bool:
        """¿Esta vista agrega algo que todavía falta?"""
        if zona not in self.zonas or distancia not in self.distancias:
            return True
        if inclinacion >= self.cal.inclinacion_min and self.inclinadas < 4:
            return True
        return self.total < self.cal.vistas_objetivo and self.total % 2 == 0

    @property
    def suficiente(self) -> bool:
        return (
            self.total >= self.cal.vistas_minimas
            and len(self.zonas) >= 8
            and len(self.distancias) >= 2
            and self.inclinadas >= 4
        )

    def que_falta(self) -> str:
        faltan = []
        if self.total < self.cal.vistas_minimas:
            faltan.append("{} capturas mas".format(self.cal.vistas_minimas - self.total))
        if len(self.zonas) < 8:
            faltan.append("mover el patron a las zonas vacias")
        if len(self.distancias) < 2:
            faltan.append("acercarlo y alejarlo")
        if self.inclinadas < 4:
            faltan.append("inclinarlo mas ({} de 4)".format(self.inclinadas))
        return " · ".join(faltan) if faltan else "ya alcanza: apreta C para calibrar"

    def mapa(self) -> list[str]:
        return ["".join("#" if (f, c) in self.zonas else "." for c in range(3)) for f in range(3)]


# --------------------------------------------------------------------------
# Cálculo
# --------------------------------------------------------------------------


def puntos_del_patron(tamano: tuple[int, int], lado_mm: float) -> np.ndarray:
    """Las coordenadas reales de las esquinas, en milímetros.

    El patrón se define plano (z = 0). Es lo que le da escala al resultado: si
    `lado_mm` no es el tamaño real impreso, todo queda escalado en silencio.
    """
    cols, filas = tamano
    puntos = np.zeros((cols * filas, 3), np.float32)
    puntos[:, :2] = np.mgrid[0:cols, 0:filas].T.reshape(-1, 2)
    return puntos * float(lado_mm)


def calibrar(vistas, tamano, lado_mm, resolucion, modelo):
    """Corre la calibración y devuelve `(rms, matriz, coeficientes, error por vista)`."""
    objeto = [puntos_del_patron(tamano, lado_mm) for _ in vistas]
    banderas = cv2.CALIB_RATIONAL_MODEL if modelo == "racional" else 0
    rms, matriz, coefs, rot, tras = cv2.calibrateCamera(
        objeto, list(vistas), resolucion, None, None, flags=banderas
    )
    errores = []
    for i, esquinas in enumerate(vistas):
        proyectadas, _ = cv2.projectPoints(objeto[i], rot[i], tras[i], matriz, coefs)
        dif = esquinas.reshape(-1, 2) - proyectadas.reshape(-1, 2)
        errores.append(float(np.sqrt((dif ** 2).sum(axis=1).mean())))
    return float(rms), matriz, coefs, errores


def semaforo(rms: float, cal) -> tuple[str, tuple[int, int, int], list[str]]:
    """Traduce el error de reproyección a un veredicto y a qué hacer.

    Un número suelto no le dice nada a nadie: lo que importa es si la calibración
    sirve y, si no sirve, qué hay que cambiar.
    """
    if rms < cal.excelente_px:
        return ("EXCELENTE", VERDE, [
            "La calibracion es muy buena. Se puede usar tal cual.",
        ])
    if rms < cal.bueno_px:
        return ("BUENA", VERDE, [
            "Cumple el objetivo (por debajo de {:.2f} px). Se puede usar.".format(cal.bueno_px),
        ])
    if rms < cal.aceptable_px:
        return ("ACEPTABLE", AMARILLO, [
            "Usable, pero conviene repetirla para ganar precision.",
            "Que probar: mas vistas inclinadas, patron mejor iluminado y sin reflejos,",
            "y sobre todo que el patron este PERFECTAMENTE plano.",
        ])
    return ("MALA — HAY QUE REPETIRLA", ROJO, [
        "Por encima de {:.2f} px la correccion no es confiable.".format(cal.aceptable_px),
        "Causas mas frecuentes, en orden:",
        "  1. El patron no esta plano (combado, pegado solo por los bordes).",
        "  2. Fotos movidas: mantener el patron quieto en cada captura.",
        "  3. Falta variedad: todas las vistas parecidas o solo en el centro.",
        "  4. El lado_mm de la configuracion no coincide con el impreso.",
        "  5. Si el lente distorsiona mucho, probar modelo 'racional'.",
    ])


# --------------------------------------------------------------------------
# Dibujo
# --------------------------------------------------------------------------


def _panel(lienzo, lineas, ancho=560):
    alto_linea = 24
    alto = alto_linea * len(lineas) + 16
    capa = lienzo.copy()
    cv2.rectangle(capa, (10, 10), (10 + ancho, 10 + alto), (25, 25, 25), -1)
    cv2.addWeighted(capa, 0.72, lienzo, 0.28, 0, lienzo)
    for i, (texto, color) in enumerate(lineas):
        cv2.putText(lienzo, texto, (22, 34 + i * alto_linea),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1, cv2.LINE_AA)


def _rejilla(lienzo, paso=80, color=(0, 165, 255)):
    """Rejilla de líneas perfectamente rectas, para comparar contra la imagen.

    Es la referencia que hace visible la curvatura: si las líneas del mundo real
    se apartan de estas, hay distorsión.
    """
    alto, ancho = lienzo.shape[:2]
    for x in range(0, ancho, paso):
        cv2.line(lienzo, (x, 0), (x, alto), color, 1, cv2.LINE_AA)
    for y in range(0, alto, paso):
        cv2.line(lienzo, (0, y), (ancho, y), color, 1, cv2.LINE_AA)


def desviacion_de_recta(esquinas: np.ndarray, tamano: tuple[int, int]) -> float:
    """Cuánto se aparta de una recta la fila más larga de esquinas, en píxeles.

    Es la versión numérica de "mirá si quedó recto": las esquinas de una fila del
    ajedrezado están sobre una recta en el mundo real, así que cualquier
    curvatura que se mida es distorsión del lente.
    """
    cols, filas = tamano
    p = esquinas.reshape(filas, cols, 2)
    peor = 0.0
    for fila in (0, filas // 2, filas - 1):
        puntos = p[fila]
        a, b = puntos[0], puntos[-1]
        direccion = b - a
        largo = np.linalg.norm(direccion)
        if largo < 1e-6:
            continue
        normal = np.array([-direccion[1], direccion[0]]) / largo
        peor = max(peor, float(np.abs((puntos - a) @ normal).max()))
    return peor


# --------------------------------------------------------------------------
# Modo captura + cálculo
# --------------------------------------------------------------------------


def preguntar_nombre_camara(resolucion) -> str:
    """Pide el nombre de la cámara que se está calibrando.

    El nombre define en qué archivo se guarda el perfil, así que es lo que
    impide que una calibración pise a otra. Se pregunta en vez de suponer:
    OpenCV no expone el nombre del dispositivo, y usar uno fijo fue exactamente
    lo que hizo que la C270 terminara con el perfil de la CAM40.
    """
    sugerido = "camara_{}x{}".format(*resolucion) if resolucion else "camara"
    if not (sys.stdin and sys.stdin.isatty()):
        return sugerido  # sin nadie a quién preguntar; el nombre feo se nota
    print("\n  ¿Qué cámara estás calibrando? El nombre define el archivo del perfil,")
    print("  así que dos cámaras con nombres distintos no se pisan.")
    print("  Ejemplos: ArgomTech CAM40  ·  Logitech C270  ·  ArgomTech CAM20")
    try:
        respuesta = input("\n  Nombre de la cámara [Enter = {}]: ".format(sugerido)).strip()
    except (EOFError, KeyboardInterrupt):
        return sugerido
    return respuesta or sugerido


def confirmar_sobrescritura(ruta: str) -> bool:
    """Si ya hay un perfil en ese archivo, avisa qué es antes de pisarlo.

    Es la salvaguarda concreta para no perder una calibración buena por
    reutilizar un nombre sin darse cuenta.
    """
    if not os.path.exists(ruta):
        return True
    try:
        from vision.geometry.distorsion import cargar_perfil as _cargar
        viejo = _cargar(ruta)
        detalle = "{} · {} · error {:.3f} px · {} vistas".format(
            viejo.camara, viejo.huella, viejo.rms_px, viejo.vistas)
    except Exception:  # noqa: BLE001
        detalle = "(no se pudo leer)"
    print("\n  ⚠  YA EXISTE un perfil en {}".format(os.path.basename(ruta)))
    print("     {}".format(detalle))
    if not (sys.stdin and sys.stdin.isatty()):
        print("     Sin terminal para confirmar: NO se sobrescribe.")
        return False
    try:
        return input("\n     ¿Sobrescribirlo? [s/N]: ").strip().lower() in ("s", "si", "sí")
    except (EOFError, KeyboardInterrupt):
        return False


def modo_calibrar(cfg, args) -> int:
    cal = cfg.calibracion
    tamano = cal.tamano_patron

    print("=" * 72)
    print("CALIBRACIÓN DE DISTORSIÓN")
    print("=" * 72)
    print("  patrón: {} x {} esquinas internas, cuadros de {:.1f} mm".format(
        tamano[0], tamano[1], cal.lado_mm))
    print("  ¡Confirmá que ese lado de {:.1f} mm es el que MEDISTE con la regla".format(cal.lado_mm))
    print("  sobre el patrón impreso! Si no coincide, todo queda escalado.")
    print("  modelo: {} · perfiles en: {}".format(cal.modelo, cal.carpeta(BASE_VISION)))
    print()

    try:
        fuente = FuenteCamara(cfg.camara, indice=args.indice)
    except ErrorCamara as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        return 2
    if fuente.aviso:
        print("⚠ {}\n".format(fuente.aviso))

    cobertura = Cobertura(cal)
    vistas: list[np.ndarray] = []
    anteriores: np.ndarray | None = None
    ultima_captura = 0.0
    resolucion = None
    ventana = "Calibracion — mové el patron por todo el cuadro"

    try:
        while True:
            cuadro = fuente.leer()
            if cuadro is None:
                time.sleep(0.01)
                continue
            imagen = cuadro.imagen
            alto, ancho = imagen.shape[:2]
            resolucion = (ancho, alto)
            lienzo = imagen.copy() if imagen.ndim == 3 else cv2.cvtColor(imagen, cv2.COLOR_GRAY2BGR)

            esquinas = detectar_patron(imagen, tamano)
            estable = False
            if esquinas is not None:
                cv2.drawChessboardCorners(lienzo, tamano, esquinas, True)
                if anteriores is not None and anteriores.shape == esquinas.shape:
                    movimiento = float(np.linalg.norm(
                        esquinas.reshape(-1, 2) - anteriores.reshape(-1, 2), axis=1).mean())
                    estable = movimiento < cal.estabilidad_px
                anteriores = esquinas

                zona = zona_de(esquinas, ancho, alto)
                distancia = tramo_distancia(esquinas, ancho, alto)
                incl = inclinacion_de(esquinas, tamano)

                # Captura automática: detectado + quieto + aporta algo nuevo.
                # Guardar fotos movidas es la forma más común de arruinar el
                # promedio sin darse cuenta.
                if (estable and not args.manual
                        and time.monotonic() - ultima_captura > cal.pausa_s
                        and cobertura.aporta(zona, distancia, incl)):
                    vistas.append(esquinas)
                    cobertura.registrar(zona, distancia, incl)
                    ultima_captura = time.monotonic()
                    print("  captura {:>2}  zona {} · {} · inclinación {:.2f}".format(
                        len(vistas), zona, distancia, incl))
            else:
                anteriores = None

            mapa = cobertura.mapa()
            lineas = [
                ("PATRON: {}".format("DETECTADO" if esquinas is not None else "no se ve"),
                 VERDE if esquinas is not None else ROJO),
                ("quieto: {}".format("si" if estable else "no  (mantenelo firme)"),
                 VERDE if estable else AMARILLO),
                ("", _BLANCO_BGR),
                ("CAPTURAS: {} de {}".format(cobertura.total, cal.vistas_objetivo),
                 VERDE if cobertura.suficiente else BLANCO),
                ("zonas {}   distancias {}/3   inclinadas {}/4".format(
                    mapa[0], len(cobertura.distancias), cobertura.inclinadas), BLANCO),
                ("      {}".format(mapa[1]), _BLANCO_BGR),
                ("      {}".format(mapa[2]), BLANCO),
                ("", _BLANCO_BGR),
                ("> {}".format(cobertura.que_falta()),
                 VERDE if cobertura.suficiente else AMARILLO),
                ("", _BLANCO_BGR),
                ("[C] calibrar   [espacio] capturar   [D] borrar ultima   [Q] salir", _GRIS_BGR),
            ]
            _panel(lienzo, lineas)

            try:
                cv2.imshow(ventana, lienzo)
            except cv2.error as exc:
                print("No se pudo abrir la ventana: {}".format(exc), file=sys.stderr)
                return 2
            tecla = cv2.waitKey(1) & 0xFF
            if tecla in (ord("q"), 27):
                print("\nCancelado sin calibrar.")
                return 1
            if tecla == ord(" ") and esquinas is not None:
                vistas.append(esquinas)
                cobertura.registrar(zona_de(esquinas, ancho, alto),
                                    tramo_distancia(esquinas, ancho, alto),
                                    inclinacion_de(esquinas, tamano))
                ultima_captura = time.monotonic()
                print("  captura manual {}".format(len(vistas)))
            if tecla == ord("d") and vistas:
                vistas.pop()
                cobertura.total -= 1
                print("  borrada la última (quedan {})".format(len(vistas)))
            if tecla == ord("c"):
                if len(vistas) < cal.vistas_minimas:
                    print("  hacen falta al menos {} vistas (hay {})".format(
                        cal.vistas_minimas, len(vistas)))
                    continue
                break
    finally:
        cv2.destroyAllWindows()

    # --- cálculo ----------------------------------------------------------
    print("\nCalculando con {} vistas...".format(len(vistas)))
    rms, matriz, coefs, errores = calibrar(
        vistas, tamano, cal.lado_mm, resolucion, cal.modelo)

    # Una sola vista movida puede arruinar el promedio. Se muestran las peores y
    # se ofrece rehacer el cálculo sin ellas, en vez de descartar en silencio.
    mediana = float(np.median(errores))
    malas = [i for i, e in enumerate(errores) if e > max(2.0 * mediana, mediana + 0.3)]
    if malas and len(vistas) - len(malas) >= cal.vistas_minimas:
        print("  hay {} vista(s) con error muy por encima del resto: {}".format(
            len(malas), ["{}: {:.3f} px".format(i + 1, errores[i]) for i in malas]))
        limpias = [v for i, v in enumerate(vistas) if i not in malas]
        rms2, matriz2, coefs2, errores2 = calibrar(
            limpias, tamano, cal.lado_mm, resolucion, cal.modelo)
        print("  sin ellas el error baja de {:.3f} a {:.3f} px".format(rms, rms2))
        if rms2 < rms:
            rms, matriz, coefs, errores, vistas = rms2, matriz2, coefs2, errores2, limpias
            print("  -> se usa la calibración sin esas vistas")

    veredicto, _, consejos = semaforo(rms, cal)

    # El nombre de la cámara sale de lo que indique el usuario, no de una
    # constante en el código. Es lo que hace que cada calibración vaya a su
    # propio archivo en vez de pisar a la anterior.
    nombre_camara = args.camara or preguntar_nombre_camara(resolucion)
    ruta_perfil = cal.ruta_de(nombre_archivo(nombre_camara), BASE_VISION)

    perfil = PerfilCamara(
        nombre=nombre_archivo(nombre_camara),
        camara=nombre_camara,
        fecha=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        ancho=resolucion[0], alto=resolucion[1],
        modelo=cal.modelo,
        matriz=matriz, coeficientes=coefs,
        rms_px=rms, vistas=len(vistas),
        patron_columnas=tamano[0], patron_filas=tamano[1], patron_lado_mm=cal.lado_mm,
    )

    print()
    print("=" * 72)
    print("RESULTADO:  error de reproyección {:.3f} px   ->   {}".format(rms, veredicto))
    print("=" * 72)
    for linea in consejos:
        print("  " + linea)
    print()
    print("  " + perfil.resumen.replace("\n", "\n  "))
    print()
    print("  error por vista: min {:.3f} · mediana {:.3f} · max {:.3f} px".format(
        min(errores), float(np.median(errores)), max(errores)))

    if rms >= cal.aceptable_px and not args.guardar_igual:
        print("\n  NO se guardó el perfil porque la calibración no es confiable.")
        print("  Repetila, o usá --guardar-igual si querés conservarla de todos modos.")
        fuente.cerrar()
        return 1

    if not confirmar_sobrescritura(ruta_perfil):
        print("\n  No se guardó nada: el perfil existente quedó intacto.")
        print("  Volvé a calibrar con otro nombre: --camara \"OTRO NOMBRE\"")
        fuente.cerrar()
        return 1

    guardar_perfil(perfil, ruta_perfil)
    print("\n  perfil de \"{}\" guardado en: {}".format(nombre_camara, ruta_perfil))
    print("  huella del aparato: {}".format(perfil.huella))
    print("\n  Verificalo con tus ojos:")
    print("    python -m vision.tools.calibrar_camara --verificar --camara \"{}\"".format(
        nombre_camara))
    fuente.cerrar()
    return 0


# --------------------------------------------------------------------------
# Modo verificación visual
# --------------------------------------------------------------------------


def modo_verificar(cfg, args) -> int:
    cal = cfg.calibracion

    # La cámara se abre PRIMERO: sin saber qué resolución entrega no se puede
    # elegir el perfil que le corresponde ni comprobar si el elegido calza.
    try:
        fuente = FuenteCamara(cfg.camara, indice=args.indice)
    except ErrorCamara as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        return 2

    primero = None
    limite = time.monotonic() + 10.0
    while primero is None and time.monotonic() < limite:
        primero = fuente.leer()
        time.sleep(0.01)
    if primero is None:
        print("ERROR: la cámara no entregó ninguna imagen.", file=sys.stderr)
        fuente.cerrar()
        return 2
    alto_cam, ancho_cam = primero.imagen.shape[:2]

    interactivo = bool(sys.stdin and sys.stdin.isatty())
    try:
        perfil = elegir_perfil(cal, BASE_VISION, ancho_cam, alto_cam,
                               nombre=args.camara, interactivo=interactivo)
    except ErrorCalibracion as exc:
        print("\nERROR: {}".format(exc), file=sys.stderr)
        fuente.cerrar()
        return 2

    compat = comparar_con_camara(perfil, ancho_cam, alto_cam)
    print("\nPerfil cargado:")
    print("  " + perfil.resumen.replace("\n", "\n  "))
    print(compat.mensaje())
    print("Apuntá la cámara a algo que sepas que es RECTO: el borde del tablero,")
    print("las líneas de la cancha, el marco de una puerta. A la izquierda vas a ver")
    print("la imagen cruda y a la derecha la corregida.\n")

    rectificador = None
    mostrar_rejilla = True
    alpha = cal.alpha
    veredicto_curvatura = None  # lo llena la medición sobre el patrón
    tipografia = Tipografia(escala_para(alto_cam))
    ventana = "Antes (izq) y despues (der) de corregir la distorsion"

    try:
        while True:
            cuadro = fuente.leer()
            if cuadro is None:
                time.sleep(0.01)
                continue
            imagen = cuadro.imagen
            alto, ancho = imagen.shape[:2]
            if rectificador is None or rectificador.alpha != alpha:
                rectificador = Rectificador(perfil, alpha=alpha, tamano=(ancho, alto))
                if rectificador.aviso:
                    print("⚠ {}".format(rectificador.aviso))

            corregida = rectificador.rectificar(imagen)
            izq = imagen.copy() if imagen.ndim == 3 else cv2.cvtColor(imagen, cv2.COLOR_GRAY2BGR)
            der = corregida.copy() if corregida.ndim == 3 else cv2.cvtColor(corregida, cv2.COLOR_GRAY2BGR)

            # Medida numérica de "quedó recto", cuando el patrón está a la vista.
            #
            # Esta es la comprobación que decide de verdad si el perfil
            # corresponde a esta cámara: la huella (resolución y campo de visión)
            # solo permite sospechar, pero si la corrección EMPEORA unas líneas
            # que sabemos rectas, no hay nada que discutir. Es el mismo principio
            # que ya usamos con los ajustes de cámara: verificar por efecto y no
            # por lo que dice la etiqueta.
            texto_recta = ""
            e_antes = detectar_patron(imagen, cal.tamano_patron)
            if e_antes is not None:
                d_antes = desviacion_de_recta(e_antes, cal.tamano_patron)
                e_despues = detectar_patron(corregida, cal.tamano_patron)
                if e_despues is not None:
                    d_despues = desviacion_de_recta(e_despues, cal.tamano_patron)
                    texto_recta = "curvatura de las filas: {:.2f} px → {:.2f} px".format(
                        d_antes, d_despues)
                    if d_despues > d_antes * 1.15:
                        veredicto_curvatura = ("empeora", d_antes, d_despues)
                    elif d_despues < d_antes * 0.85:
                        veredicto_curvatura = ("corrige", d_antes, d_despues)
                cv2.drawChessboardCorners(izq, cal.tamano_patron, e_antes, True)

            if mostrar_rejilla:
                _rejilla(izq)
                _rejilla(der)

            cv2.putText(izq, "ORIGINAL (con distorsion)", (20, alto - 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, ROJO, 2, cv2.LINE_AA)
            cv2.putText(der, "CORREGIDA", (20, alto - 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, VERDE, 2, cv2.LINE_AA)

            par = np.hstack([izq, der])
            escala = min(1.0, 1600.0 / par.shape[1])
            if escala < 1.0:
                par = cv2.resize(par, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)

            # El estado del perfil va como fila PERMANENTE del panel, no como un
            # mensaje de consola que pasó hace un minuto y ya no está a la vista.
            panel = Panel(tipografia)
            panel.titulo("Verificación de la corrección de distorsión")
            if veredicto_curvatura and veredicto_curvatura[0] == "empeora":
                panel.destacado("EL PERFIL NO CORRESPONDE", ROJO_P,
                                "la corrección EMPEORA líneas que son rectas")
            elif compat.nivel == "incompatible":
                panel.destacado("EL PERFIL NO CORRESPONDE", ROJO_P, compat.motivo[:70])
            elif veredicto_curvatura and veredicto_curvatura[0] == "corrige":
                panel.destacado("El perfil CORRIGE", VERDE_P,
                                "las líneas rectas quedan rectas")
            else:
                panel.destacado("Perfil: {}".format(perfil.camara), BLANCO,
                                "error {:.3f} px · {}".format(perfil.rms_px, perfil.huella))
            panel.separador()
            panel.estado("Perfil", "{} · {}".format(perfil.camara, perfil.huella),
                         VERDE_P if compat.nivel == "compatible" else
                         (AMBAR if compat.nivel == "sospechoso" else ROJO_P))
            panel.estado("Cámara conectada", "{}x{}".format(ancho, alto), GRIS)
            panel.estado("Compatibilidad", compat.etiqueta,
                         VERDE_P if compat.nivel == "compatible" else
                         (AMBAR if compat.nivel == "sospechoso" else ROJO_P))
            if texto_recta:
                color_c = VERDE_P
                if veredicto_curvatura and veredicto_curvatura[0] == "empeora":
                    color_c = ROJO_P
                panel.estado("Rectitud", texto_recta, color_c)
            panel.separador()
            panel.datos("recorte alpha = {:.2f}".format(alpha), GRIS)
            panel.pie("Las líneas naranjas son PERFECTAMENTE rectas: compará contra ellas.")
            panel.pie("r rejilla  ·  a recorte  ·  g guardar  ·  q salir")
            panel.dibujar(par)

            try:
                cv2.imshow(ventana, par)
            except cv2.error as exc:
                print("No se pudo abrir la ventana: {}".format(exc), file=sys.stderr)
                return 2
            tecla = cv2.waitKey(1) & 0xFF
            if tecla in (ord("q"), 27):
                break
            if tecla == ord("r"):
                mostrar_rejilla = not mostrar_rejilla
            if tecla == ord("a"):
                alpha = 0.0 if alpha > 0.5 else 1.0
                print("  recorte alpha = {:.2f}".format(alpha))
            if tecla == ord("g"):
                nombre = "verificacion_distorsion_{}.png".format(int(time.time()))
                cv2.imwrite(nombre, par)
                print("  guardado: {}".format(nombre))
    finally:
        cv2.destroyAllWindows()
        fuente.cerrar()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Calibra la distorsión del lente y permite verificarla a ojo.")
    parser.add_argument("--config", default=CONFIG_POR_DEFECTO)
    parser.add_argument("--indice", type=int, default=None, help="qué cámara usar")
    parser.add_argument("--verificar", action="store_true",
                        help="ver el antes y después con una calibración ya hecha")
    parser.add_argument("--manual", action="store_true",
                        help="solo capturar con la barra espaciadora")
    parser.add_argument("--camara", default=None,
                        help="nombre de la cámara: define el archivo del perfil "
                             "al calibrar, y cuál cargar al verificar")
    parser.add_argument("--guardar-igual", action="store_true",
                        help="guardar el perfil aunque el error sea alto")
    args = parser.parse_args(argv)

    cfg = cargar_config(args.config)
    return modo_verificar(cfg, args) if args.verificar else modo_calibrar(cfg, args)


if __name__ == "__main__":
    sys.exit(main())
