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
    from .configuracion import ConfigVision, geometrias_deposito
    from .mundo import VERSION_PROTOCOLO
    # El formateador de tiempo se trae de donde ya vive, en vez de escribir otro
    # acá: si la pantalla dijera 0:03 y el acta 00:03, alguien tendría que
    # averiguar cuál de los dos miente.
    from .record.acta import mmss
    from .tools.panel import (
        AMBAR, BLANCO, GRIS, ROJO, VERDE, Panel, Tipografia, escala_para, sin_acentos,
    )
except ImportError:  # como script suelto
    from vision.configuracion import (  # type: ignore[no-redef]
        ConfigVision, geometrias_deposito,
    )
    from vision.mundo import VERSION_PROTOCOLO  # type: ignore[no-redef]
    from vision.record.acta import mmss  # type: ignore[no-redef]
    from vision.tools.panel import (  # type: ignore[no-redef]
        AMBAR, BLANCO, GRIS, ROJO, VERDE, Panel, Tipografia, escala_para, sin_acentos,
    )

#: Colores en BGR, que es lo que dibuja OpenCV directamente sobre la imagen.
#: Ojo: la paleta de `panel.py` va en RGB porque la usa Pillow. Son espacios
#: distintos y mezclarlos pinta las cosas de un color equivocado.
_ESQUINA = (255, 120, 0)
#: El perímetro que NO sale del origen, en un tono más apagado: cierra la cancha
#: sin competir visualmente con los ejes, que son los que llevan información.
_BORDE = (170, 90, 30)
_ROVER = (0, 220, 255)
_GRILLA = (90, 90, 90)
_TEXTO = (255, 255, 255)
_CUBO_BGR = {"red": (60, 60, 235), "green": (80, 200, 80), "blue": (235, 130, 60)}
_SALIDA = (200, 200, 200)

#: A partir de qué edad un dato se dibuja como viejo. Estaba escrito tres veces
#: como literal; ahora se declara una sola, porque el conteo de acopio agregó un
#: cuarto lugar donde hay que hacerse la misma pregunta y cuatro copias de un
#: umbral son cuatro formas de que un día digan cosas distintas.
_EDAD_VIEJA_MS = 200

#: A partir de cuánto queda, el cronómetro de la ronda se dibuja en ámbar en vez
#: de verde. Es una señal de PANTALLA y no una regla: no cambia nada de lo que el
#: sistema hace, solo avisa al que mira que la ronda se está por terminar. Un
#: minuto sobre diez es el último tramo en el que todavía se puede reaccionar.
_RONDA_POR_TERMINAR_MS = 60_000

#: Cuánto tiñe el relleno de una zona. Bajo a propósito: la zona es una ayuda
#: para el operador, no puede taparle el video, que es lo que de verdad hay que
#: mirar.
_ZONA_ALFA = 0.28


def _estadia(z) -> str:
    """Desde cuándo está el cubo en su zona, para la etiqueta y el panel.

    Dice dos cosas y las dos importan: **a qué altura del cronómetro entró**
    —que es lo que un equipo pregunta después— y **cuánto hace** que está,
    que es lo que dice si ya se sostuvo. Si el cubo entró fuera de la ronda,
    o ya estaba puesto al arrancar, no hay hora de entrada que mostrar y se
    muestra solo la permanencia. Las dos cosas vuelven a cero si el cubo sale.
    """
    hace = "hace {:.1f} s".format(z.adentro_hace_ms / 1000.0)
    if z.entro_en_ronda_ms is None:
        return "dentro {}".format(hace)
    return "entró a {} · {}".format(mmss(z.entro_en_ronda_ms), hace)


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
        # Las zonas son lugares DECLARADOS: no cambian entre cuadros, así que se
        # arman una vez. El sistema de coordenadas sí cambia, y por eso lo que se
        # recalcula en cada cuadro es solo el paso de celdas a píxeles.
        self._zonas = geometrias_deposito(cfg)
        self._salida = (cfg.lugares.start_col, cfg.lugares.start_row)
        self._sistema_actual = None

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

        # El sistema de coordenadas del cuadro se guarda ACÁ, antes de dibujar
        # nada. Se guardaba dentro de `_dibujar_esquinas`, que corre después de
        # la grilla: el primer cuadro salía sin grilla y los siguientes la
        # dibujaban con la geometría del cuadro ANTERIOR. Con la cámara quieta no
        # se nota, y con la cámara recién movida —que es justo cuando uno mira la
        # grilla— dibujaba lo de antes.
        self._sistema_actual = sistema

        if sistema is not None:
            self._dibujar_grilla(lienzo, sistema)
            self._dibujar_esquinas(lienzo, sistema)
            # Las zonas y la salida van DEBAJO de rovers y cubos: son el fondo
            # contra el que se mira lo que se mueve, y taparlo sería al revés.
            self._dibujar_zonas(lienzo, info.get("acopio"))
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
        cols, rows = self._cfg.tablero.cols, self._cfg.tablero.rows
        paso = max(1, cols // 6)
        for col in range(0, cols + 1, paso):
            self._linea_celdas(lienzo, (col, 0), (col, rows), _GRILLA)
        for row in range(0, rows + 1, paso):
            self._linea_celdas(lienzo, (0, row), (cols, row), _GRILLA)

        # El perímetro completo de la cancha: las cuatro aristas entre los
        # centros de los marcadores. Cerrarlo importa porque deja ver de un
        # vistazo si TODA el área está bien mapeada, no solo la esquina del
        # origen.
        self._linea_celdas(lienzo, (cols, 0), (cols, rows), _BORDE, 2)   # 1 -> 2
        self._linea_celdas(lienzo, (0, rows), (cols, rows), _BORDE, 2)   # 3 -> 2

        # Las dos que SALEN DEL ORIGEN van más brillantes y encima, porque no
        # son decoración: marcan hacia dónde crecen `col` y `row`. Si apuntan al
        # lado equivocado, los marcadores se pegaron en orden antihorario y
        # todas las coordenadas salen espejadas.
        self._linea_celdas(lienzo, (0, 0), (cols, 0), _ESQUINA, 3)       # 0 -> 1 : col
        self._linea_celdas(lienzo, (0, 0), (0, rows), _ESQUINA, 3)       # 0 -> 3 : row

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

    @staticmethod
    def _sufijo_zona(z) -> str:
        """El estado de la zona, para el título de su etiqueta."""
        if z is None or not z.presente:
            return ""
        if z.contado:
            return " · EN POSICIÓN"
        if z.adentro:
            return " · SOSTENIENDO"
        return ""

    def _detalle_zona(self, z, geo) -> str:
        """La segunda línea de la etiqueta: POR QUÉ la zona está como está.

        Antes decía siempre el centro de la zona, que no cambia nunca y ya está
        en la configuración. Mostrar en su lugar el estado del cubo responde la
        pregunta que uno se hace mirando la pantalla —*¿por qué esta zona no
        cuenta?*— en vez de dejar tres casos muy distintos con la misma cara:
        no hay cubo, el cubo está adentro pero todavía no se sostuvo, y el cubo
        está afuera por unos milímetros.

        Pasó en la cancha real: con dos cubos bien puestos el sistema mostraba
        una sola zona marcada, y desde la imagen no había forma de saber si el
        conteo estaba mal o si los cubos no cumplían el criterio. Estaban
        oscilando a través del límite.
        """
        cell = self._cfg.tablero.cell_mm
        if z is None:
            return "({:.2f}, {:.2f})".format(geo.col, geo.row)
        if not z.presente:
            return "sin cubo"
        if z.adentro:
            return _estadia(z)
        return "le falta {:.1f} mm".format(z.falta_celdas * cell)

    def _rect_celdas(self, lienzo, col, row, semi_col, semi_row):
        """Las cuatro esquinas de un rectángulo en celdas, ya en píxeles."""
        esquinas = np.array([
            [col - semi_col, row - semi_row], [col + semi_col, row - semi_row],
            [col + semi_col, row + semi_row], [col - semi_col, row + semi_row],
        ], dtype=np.float64)
        return self._a_px(lienzo, esquinas)

    def _dibujar_zonas(self, lienzo, acopio) -> None:
        """Las tres zonas de acopio y la salida, dibujadas sobre la cancha.

        **En la cancha no hay nada pintado**: las zonas son virtuales, y este
        dibujo es la única forma de verlas. Por eso incluye el rectángulo
        interior de la VENTANA DE ACEPTACIÓN, que es donde tiene que caer el
        centro del cubo para que el cubo entero quede adentro. Con la zona sola,
        el operador ve un cubo pisando el borde y no puede saber si entró; con la
        ventana, lo ve.

        El relleno se compone en una sola pasada sobre la imagen entera. Parece
        caro y no lo es: la copia solo difiere dentro de los rectángulos, así que
        la mezcla es idéntica a la original en todo el resto.
        """
        estados = {z.color: z for z in acopio.zonas} if acopio is not None else {}

        capa = lienzo.copy()
        pintada = False
        for color, geo in sorted(self._zonas.items()):
            rect = self._rect_celdas(lienzo, geo.col, geo.row, geo.semi_col, geo.semi_row)
            if rect is None:
                continue
            contado = bool(estados.get(color) and estados[color].contado)
            base = _CUBO_BGR.get(color, (200, 200, 200))
            # La zona que ya tiene su cubo se pinta con el color pleno; las que
            # faltan, apagadas. El estado se lee por color antes que por texto.
            relleno = base if contado else tuple(int(v * 0.45) for v in base)
            cv2.fillPoly(capa, [np.array(rect, np.int32).reshape(-1, 1, 2)], relleno)
            pintada = True
        if pintada:
            cv2.addWeighted(capa, _ZONA_ALFA, lienzo, 1 - _ZONA_ALFA, 0, lienzo)

        for color, geo in sorted(self._zonas.items()):
            rect = self._rect_celdas(lienzo, geo.col, geo.row, geo.semi_col, geo.semi_row)
            ventana = self._rect_celdas(lienzo, geo.col, geo.row, geo.ventana_col, geo.ventana_row)
            centro = self._a_px(lienzo, np.array([[geo.col, geo.row]]))
            if rect is None or centro is None:
                continue
            z = estados.get(color)
            contado = bool(z and z.contado)
            color_bgr = _CUBO_BGR.get(color, (200, 200, 200))

            cv2.polylines(lienzo, [np.array(rect, np.int32).reshape(-1, 1, 2)], True,
                          color_bgr, 3 if contado else 2, cv2.LINE_AA)
            if ventana is not None:
                cv2.polylines(lienzo, [np.array(ventana, np.int32).reshape(-1, 1, 2)], True,
                              color_bgr, 1, cv2.LINE_AA)
            cv2.drawMarker(lienzo, centro[0], color_bgr, cv2.MARKER_CROSS, 14, 1)

            # La etiqueta se ancla en una ESQUINA de la zona, sobre el borde
            # donde apoya, y no en su centro ni en el medio de ese borde. El
            # motivo se vio dibujando: el cubo entregado queda en el centro de la
            # zona con su propia etiqueta, y las dos se tapaban justo en el
            # momento que la zona importa —"EN POSICION" quedaba ilegible—. Desde
            # la esquina hay media zona de distancia, unas cinco celdas.
            ancla = {
                "arriba": (geo.col - geo.semi_col, geo.row - geo.semi_row),
                "abajo": (geo.col - geo.semi_col, geo.row + geo.semi_row),
                "izquierda": (geo.col - geo.semi_col, geo.row - geo.semi_row),
                "derecha": (geo.col + geo.semi_col, geo.row - geo.semi_row),
            }.get(geo.lado, (geo.col, geo.row))
            punto = self._a_px(lienzo, np.array([list(ancla)]))
            if punto is None:
                continue
            # La edad solo se muestra si el cubo cuenta y el dato ya está viejo:
            # ahí el veredicto se apoya en una posición CONSERVADA —el rover que
            # entregó el cubo lo está tapando— y quien mira tiene que saberlo.
            edad = z.edad_cubo_ms if (contado and z.edad_cubo_ms > _EDAD_VIEJA_MS) else 0
            self._etiqueta(lienzo, punto[0],
                           "{}{}".format(color, self._sufijo_zona(z)),
                           self._detalle_zona(z, geo), edad, color_bgr)

        salida = self._a_px(lienzo, np.array([list(self._salida)]))
        if salida is not None:
            cv2.drawMarker(lienzo, salida[0], _SALIDA, cv2.MARKER_TILTED_CROSS, 16, 2)
            self._etiqueta(lienzo, salida[0], "salida",
                           "({:.2f}, {:.2f})".format(*self._salida), 0, _SALIDA)

    def _dibujar_rovers(self, lienzo, sistema, estado) -> None:
        for r in estado.rovers:
            centro = self._a_px(lienzo, np.array([[r.col, r.row]]))
            if centro is None:
                continue
            rad = math.radians(r.theta_grados)
            punta = self._a_px(lienzo, np.array(
                [[r.col + 3.0 * math.cos(rad), r.row - 3.0 * math.sin(rad)]]))
            viejo = r.age_ms > _EDAD_VIEJA_MS
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
            if c.age_ms > _EDAD_VIEJA_MS:
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
        panel.titulo("Sistema de visión · protocolo v{}".format(VERSION_PROTOCOLO))
        if info.get("sintetico"):
            panel.destacado("DATOS SINTÉTICOS", ROJO, "no es la cancha real")
        fase = info.get("fase", "IDLE")
        panel.destacado(fase, VERDE if fase == "RUNNING" else BLANCO,
                        "{} cliente(s) conectado(s)".format(info.get("clientes", 0)))
        acopio = info.get("acopio")

        # El cronómetro va en grande: es lo que miran el operador y los equipos,
        # y tiene que leerse de reojo, sin buscarlo. En IDLE no se dibuja, porque
        # no se está contando nada y un 0:00 ahí parecería una ronda por terminar.
        reloj = info.get("reloj")
        if reloj is not None and reloj.total_ms:
            if fase == "READY":
                panel.destacado("empieza en {}".format(mmss(reloj.restante_ms)), AMBAR,
                                "preparación · el paso a RUNNING es automático")
            elif fase == "RUNNING":
                panel.destacado(
                    "quedan {}".format(mmss(reloj.restante_ms)),
                    VERDE if reloj.restante_ms > _RONDA_POR_TERMINAR_MS else AMBAR,
                    "de {} de ronda".format(mmss(reloj.total_ms)))
            else:
                motivo = (info.get("motivo") or "").replace("_", " ")
                panel.destacado(mmss(reloj.transcurrido_ms), BLANCO,
                                "tiempo final{}".format(" · " + motivo if motivo else ""))

        # Que el sistema no vea la cancha es lo más grave que puede pasarle a un
        # árbitro, así que va arriba de todo lo demás y en rojo. Durante la ronda
        # se muestra además cuánto falta para que se cierre sola: quien mira
        # tiene ese tiempo para destapar un marcador.
        if not info.get("geometria_ok", True):
            ciego = info.get("ciego_ms", 0)
            limite = info.get("limite_ceguera_ms", 0)
            if fase == "RUNNING" and limite:
                detalle = "se cierra la ronda en {:.1f} s si no vuelve".format(
                    max(0, limite - ciego) / 1000.0)
            elif fase == "READY":
                detalle = "la ronda no va a arrancar hasta que vuelvan"
            else:
                detalle = "no se puede preparar una ronda así"
            panel.destacado("SIN COORDENADAS", ROJO, detalle)
        elif fase == "IDLE" and info.get("impedimento"):
            # En IDLE no alarma, pero tiene que explicar por qué `r` no va a
            # funcionar: descubrirlo apretando la tecla es peor.
            panel.datos("no se puede preparar: {}".format(info["impedimento"]), AMBAR)

        # Un cubo que ya está en su zona durante la preparación es un arranque
        # irregular: la ronda empezaría con parte del reto hecho. No se impide
        # —el acta lo registra y se decide después— pero tiene que verse ACÁ,
        # que es el único momento en que todavía se puede corregir.
        if fase == "READY" and acopio is not None:
            ya_dentro = [z.color for z in acopio.zonas if z.adentro]
            if ya_dentro:
                panel.destacado("CUBOS YA EN ZONA", ROJO,
                                "{} · sacalos antes de que empiece".format(", ".join(ya_dentro)))

        if acopio is not None and acopio.completo:
            panel.destacado("RETO COMPLETADO", VERDE,
                            "los {} cubos en su zona".format(acopio.total))
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
                         VERDE if peor < _EDAD_VIEJA_MS else AMBAR)

        if acopio is not None and acopio.total:
            panel.estado("Acopio", "{} de {} en posición".format(
                acopio.en_posicion, acopio.total), VERDE if acopio.completo else BLANCO)
            # Una fila por zona con la hora de entrada de su cubo. El que sale
            # vuelve a "afuera" en el mismo cuadro: la hora es de la estadía
            # actual, no de la primera vez que pisó la zona.
            for z in acopio.zonas:
                if not z.presente:
                    panel.estado("  " + z.color, "sin cubo", GRIS)
                elif not z.adentro:
                    panel.estado("  " + z.color, "afuera", GRIS)
                else:
                    panel.estado("  " + z.color, _estadia(z), VERDE if z.contado else AMBAR)

        panel.separador()
        panel.datos("proceso {:.1f} fps · publicación {} msg".format(
            info.get("fps", 0.0), info.get("emitidos", 0)), GRIS)
        if info.get("fallos"):
            panel.datos("cuadros no procesados: {}".format(info["fallos"]), AMBAR)
        panel.pie("r ready · f stop · a abort · q salir")
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
        # No hay tecla para `start`: el paso de READY a RUNNING es automático y
        # poder adelantarlo volvería decorativo el tiempo de preparación igual
        # para todos. `a` aborta la preparación y vuelve a IDLE, porque alguna
        # vez algo va a salir mal antes de empezar.
        return {ord("r"): "ready", ord("f"): "stop", ord("a"): "abort",
                ord("q"): "quit", 27: "quit"}.get(codigo)

    def cerrar(self) -> None:
        if self._abierta:
            cv2.destroyWindow(self._titulo)
            self._abierta = False
