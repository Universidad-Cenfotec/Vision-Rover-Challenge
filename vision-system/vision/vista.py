"""La vista en vivo: ver lo que la cámara ve y lo que el sistema deduce.

Qué resuelve
------------
El sistema funciona pero es invisible: publica números por un socket. Cuando algo
sale mal —un marcador que no se detecta, un cubo que se confunde, coordenadas
espejadas por un montaje al revés— desde afuera solo se ve telemetría rara, y
adivinar cuál de las siete etapas falló es lento y frustrante.

Esta vista pone las dos cosas juntas en una imagen: **lo que entró por la cámara**
y **lo que el sistema dedujo de eso**, dibujado encima. Si no coinciden, se ve.

Por qué es parte del sistema y no un programa aparte
-----------------------------------------------------
Un monitor separado tendría que abrir la cámara —y una webcam solo se puede abrir
una vez— o reimplementar la detección. En los dos casos mostraría **su**
interpretación, no la del sistema, y un monitor que puede discrepar de lo que se
publica es peor que no tener monitor.

Acá se dibuja el mismo estado del mundo que sale por el socket. Lo que se ve es
lo que los equipos reciben.

Es un **consumidor**, como `publish/`: solo LEE el estado del mundo. No lo
modifica ni participa de producirlo, y si se apaga, el sistema sigue igual.

Dibuja en su propio reloj
-------------------------
Dibujar cuesta milisegundos y el bucle de proceso corre a la velocidad de la
cámara. La vista se refresca a su propia tasa, más baja: mirar a 12 cuadros por
segundo se ve igual de fluido para un ojo humano y deja el procesamiento
tranquilo. Es el mismo principio de los dos relojes que ya rige entre el proceso
y la publicación.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

try:  # como paquete
    from .configuracion import ConfigVision
    from .tools.panel import (
        AMBAR, BLANCO, GRIS, ROJO, VERDE, Panel, Tipografia, escala_para, sin_acentos,
    )
except ImportError:  # como script suelto
    from vision.configuracion import ConfigVision  # type: ignore[no-redef]
    from vision.tools.panel import (  # type: ignore[no-redef]
        AMBAR, BLANCO, GRIS, ROJO, VERDE, Panel, Tipografia, escala_para, sin_acentos,
    )

#: Colores en BGR, que es lo que dibuja OpenCV directamente sobre la imagen.
#: Ojo: la paleta de `panel.py` va en RGB porque la usa Pillow. Son espacios
#: distintos y mezclarlos pinta las cosas de un color equivocado.
_ESQUINA = (255, 120, 0)
_ROVER = (0, 220, 255)
_GRILLA = (90, 90, 90)
_TEXTO = (255, 255, 255)
_CUBO_BGR = {"red": (60, 60, 235), "green": (80, 200, 80), "blue": (235, 130, 60)}


class Vista:
    """Ventana con la imagen de la cámara y lo detectado dibujado encima."""

    def __init__(self, cfg: ConfigVision, alto_imagen: int, hz: float = 12.0,
                 titulo: str = "Sistema de vision"):
        self._cfg = cfg
        self._titulo = titulo
        self._periodo = 1.0 / hz
        self._proximo = 0.0
        self._tipografia = Tipografia(escala_para(alto_imagen))
        self._abierta = False

    def toca_dibujar(self, ahora: float) -> bool:
        """Si ya corresponde refrescar. El bucle no debe dibujar en cada cuadro."""
        if ahora < self._proximo:
            return False
        self._proximo = max(ahora, self._proximo + self._periodo)
        return True

    def dibujar(self, imagen, sistema, estado, info: dict) -> None:
        """Muestra un cuadro con todo lo deducido encima.

        `sistema` puede ser `None`: es justo el caso en que no se pudo armar la
        geometría, y ahí lo importante es **mostrar la imagen igual** con el
        aviso de qué falta. Una ventana que se queda negra cuando hay un problema
        es una ventana inútil, porque el problema se ve en la imagen.
        """
        lienzo = imagen.copy() if imagen.ndim == 3 else cv2.cvtColor(imagen, cv2.COLOR_GRAY2BGR)

        if sistema is not None:
            self._dibujar_grilla(lienzo, sistema)
            self._dibujar_esquinas(lienzo, sistema)
        if sistema is not None and estado is not None:
            self._dibujar_rovers(lienzo, sistema, estado)
            self._dibujar_cubos(lienzo, sistema, estado)

        self._dibujar_panel(lienzo, estado, info)
        cv2.imshow(self._titulo, lienzo)
        self._abierta = True

    # -- capas ------------------------------------------------------------

    def _dibujar_grilla(self, lienzo, sistema) -> None:
        """La grilla de celdas reproyectada sobre la imagen.

        Es la comprobación visual más directa de que la geometría está bien: si
        las líneas dibujadas caen sobre la cuadrícula real del tablero, el
        sistema de coordenadas es correcto. Si están corridas o rotadas, se ve
        de inmediato — y ese es el error de montaje más peligroso, porque el
        sistema publica números válidos y mal sin quejarse.
        """
        paso = max(1, self._cfg.tablero.cols // 6)
        for col in range(0, self._cfg.tablero.cols + 1, paso):
            self._linea_celdas(lienzo, (col, 0), (col, self._cfg.tablero.rows), _GRILLA)
        for row in range(0, self._cfg.tablero.rows + 1, paso):
            self._linea_celdas(lienzo, (0, row), (self._cfg.tablero.cols, row), _GRILLA)
        self._linea_celdas(lienzo, (0, 0), (self._cfg.tablero.cols, 0), _ESQUINA, 2)
        self._linea_celdas(lienzo, (0, 0), (0, self._cfg.tablero.rows), _ESQUINA, 2)

    def _linea_celdas(self, lienzo, desde, hasta, color, grosor=1) -> None:
        p = self._a_px(lienzo, np.array([desde, hasta], dtype=np.float64))
        if p is not None:
            cv2.line(lienzo, p[0], p[1], color, grosor, cv2.LINE_AA)

    def _dibujar_esquinas(self, lienzo, sistema) -> None:
        for id_aruco, (x, y) in sistema.centros_px.items():
            centro = (int(round(x)), int(round(y)))
            cv2.circle(lienzo, centro, 10, _ESQUINA, 2, cv2.LINE_AA)
            cv2.putText(lienzo, str(id_aruco), (centro[0] + 13, centro[1] - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, _ESQUINA, 2, cv2.LINE_AA)
        self._sistema_actual = sistema

    def _dibujar_rovers(self, lienzo, sistema, estado) -> None:
        for r in estado.rovers:
            centro = self._a_px(lienzo, np.array([[r.col, r.row]]))
            if centro is None:
                continue
            rad = math.radians(r.theta_grados)
            punta = self._a_px(lienzo, np.array(
                [[r.col + 3.0 * math.cos(rad), r.row - 3.0 * math.sin(rad)]]))
            viejo = r.age_ms > 200
            color = AMBAR[::-1] if viejo else _ROVER
            if punta is not None:
                cv2.arrowedLine(lienzo, centro[0], punta[0], color, 2, cv2.LINE_AA, tipLength=0.3)
            cv2.circle(lienzo, centro[0], 6, color, -1, cv2.LINE_AA)
            self._etiqueta(lienzo, centro[0], "rover {}".format(r.id),
                           "({:.2f}, {:.2f})  {:.1f}°".format(r.col, r.row, r.theta_grados),
                           r.age_ms, color)  # el ° lo transliterá `sin_acentos`

    def _dibujar_cubos(self, lienzo, sistema, estado) -> None:
        lado = self._cfg.elementos.cubos.lado_mm / self._cfg.tablero.cell_mm
        for c in estado.cubos:
            esquinas = np.array([
                [c.col - lado / 2, c.row - lado / 2], [c.col + lado / 2, c.row - lado / 2],
                [c.col + lado / 2, c.row + lado / 2], [c.col - lado / 2, c.row + lado / 2],
            ], dtype=np.float64)
            px = self._a_px(lienzo, esquinas)
            centro = self._a_px(lienzo, np.array([[c.col, c.row]]))
            if px is None or centro is None:
                continue
            color = _CUBO_BGR.get(c.color, (200, 200, 200))
            if c.age_ms > 200:
                color = AMBAR[::-1]
            cv2.polylines(lienzo, [np.array(px, np.int32).reshape(-1, 1, 2)], True,
                          color, 2, cv2.LINE_AA)
            cv2.drawMarker(lienzo, centro[0], color, cv2.MARKER_CROSS, 10, 2)
            self._etiqueta(lienzo, centro[0], c.color,
                           "({:.2f}, {:.2f})".format(c.col, c.row), c.age_ms, color)

    def _etiqueta(self, lienzo, centro, titulo, posicion, edad_ms, color) -> None:
        """Nombre, celda publicada y edad. Es "lo que reporta el sistema".

        Todo el texto pasa por `sin_acentos`, que es la regla del proyecto para
        lo que va por `cv2.putText`: las fuentes Hershey son ASCII puro y ante un
        carácter multibyte dibujan un signo por byte —el grado sale como "??"—
        **sin avisar**. Es el mismo motivo por el que existe `panel.py`.

        La etiqueta se separa del objeto y se le pone un fondo: encima del
        marcador el texto blanco sobre negro no se lee, y una vista que no se lee
        no sirve para nada.
        """
        lineas = [(sin_acentos(titulo), 0.55, color, 2)]
        lineas.append((sin_acentos(posicion), 0.45, _TEXTO, 1))
        if edad_ms > 0:
            lineas.append(("edad {} ms".format(edad_ms), 0.45, AMBAR[::-1], 1))

        x, y = centro[0] + 26, centro[1] - 26
        alto, ancho = lienzo.shape[:2]
        ancho_max = max(cv2.getTextSize(t, cv2.FONT_HERSHEY_SIMPLEX, e, g)[0][0]
                        for t, e, _, g in lineas)
        # Si no entra a la derecha, se dibuja a la izquierda: en las esquinas de
        # la cancha, media etiqueta fuera de la imagen es media etiqueta perdida.
        if x + ancho_max + 8 > ancho:
            x = max(4, centro[0] - ancho_max - 26)
        y = max(20, min(y, alto - 18 * len(lineas) - 6))

        fondo = lienzo[y - 16:y + 18 * len(lineas) - 12, x - 6:x + ancho_max + 6]
        if fondo.size:
            fondo[:] = (fondo * 0.35).astype(fondo.dtype)
        for k, (texto, escala, col, grosor) in enumerate(lineas):
            cv2.putText(lienzo, texto, (x, y + 18 * k), cv2.FONT_HERSHEY_SIMPLEX,
                        escala, col, grosor, cv2.LINE_AA)

    def _a_px(self, lienzo, celdas):
        """Celdas a píxeles enteros, o `None` si caen fuera de la imagen."""
        sistema = getattr(self, "_sistema_actual", None)
        if sistema is None:
            return None
        puntos = sistema.a_pixeles(np.asarray(celdas, dtype=np.float64))
        alto, ancho = lienzo.shape[:2]
        salida = []
        for x, y in puntos:
            if not (-ancho < x < 2 * ancho and -alto < y < 2 * alto):
                return None
            salida.append((int(round(x)), int(round(y))))
        return salida

    def _dibujar_panel(self, lienzo, estado, info: dict) -> None:
        panel = Panel(self._tipografia)
        panel.titulo("Sistema de visión · protocolo v1")
        if info.get("sintetico"):
            panel.destacado("DATOS SINTÉTICOS", ROJO, "no es la cancha real")
        panel.destacado(info.get("fase", "IDLE"), VERDE if info.get("fase") == "RUNNING" else BLANCO,
                        "{} cliente(s) conectado(s)".format(info.get("clientes", 0)))
        panel.separador()

        visibles = info.get("esquinas_visibles", 0)
        if visibles == 4:
            panel.estado("Esquinas", "4 de 4", VERDE)
        elif visibles == 3:
            panel.estado("Esquinas", "3 de 4 · geometría conservada ({:.2f} mm)".format(
                info.get("desvio_mm", 0.0)), AMBAR)
        else:
            panel.estado("Esquinas", "{} de 4 · SIN COORDENADAS".format(visibles), ROJO)

        if estado is None:
            panel.estado("Estado", "todavía sin un cuadro bueno", AMBAR)
        else:
            panel.estado("Detectado", "{} rover(s) · {} cubo(s)".format(
                len(estado.rovers), len(estado.cubos)), BLANCO)
            edades = [o.age_ms for o in tuple(estado.rovers) + tuple(estado.cubos)]
            peor = max(edades) if edades else 0
            panel.estado("Edad máxima", "{} ms".format(peor),
                         VERDE if peor < 200 else AMBAR)

        panel.separador()
        panel.datos("proceso {:.1f} fps · publicación {} msg".format(
            info.get("fps", 0.0), info.get("emitidos", 0)), GRIS)
        if info.get("fallos"):
            panel.datos("cuadros no procesados: {}".format(info["fallos"]), AMBAR)
        panel.pie("r ready · s start · f stop · q salir")
        panel.dibujar(lienzo)

    # -- teclado y cierre --------------------------------------------------

    def tecla(self) -> str | None:
        """Lee una tecla de la ventana y la traduce a un comando.

        Se atiende el teclado **desde la ventana** además de la consola: cuando
        alguien está mirando la cancha, tiene el mouse y los ojos acá, no en otra
        terminal.
        """
        if not self._abierta:
            return None
        codigo = cv2.waitKey(1) & 0xFF
        return {ord("r"): "ready", ord("s"): "start", ord("f"): "stop",
                ord("q"): "quit", 27: "quit"}.get(codigo)

    def cerrar(self) -> None:
        if self._abierta:
            cv2.destroyWindow(self._titulo)
            self._abierta = False
