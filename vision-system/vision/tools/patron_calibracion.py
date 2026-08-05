"""Genera el patrón de ajedrez para calibrar la cámara, en PDF a tamaño real.

    python -m vision.tools.patron_calibracion
    python -m vision.tools.patron_calibracion --salida /tmp/patron.pdf
    python -m vision.tools.patron_calibracion --columnas 13 --filas 9   # más grande

Por qué el PDF se escribe a mano
--------------------------------
No hay ninguna biblioteca de PDF instalada, y agregar una iría contra la regla de
dependencias del proyecto. Un ajedrezado son rectángulos rellenos, que es lo más
simple que sabe hacer PDF: se arma con biblioteca estándar y no arrastra nada.

Por qué el tamaño del cuadro es el dato crítico
-----------------------------------------------
La calibración deduce la geometría del lente comparando lo que ve con lo que
*sabe* que está mirando. Ese "sabe" es el tamaño real del cuadro. Si la hoja se
imprime al 97 % —que es lo que hace "ajustar a la página" sin avisar—, toda la
calibración queda escalada y en silencio: el error de reproyección puede salir
bajo igual, porque el patrón es coherente consigo mismo, pero las medidas del
mundo real quedan mal.

Por eso la hoja lleva una **regla de verificación de 100 mm** impresa: es la
única forma de comprobar la escala sin confiar en el diálogo de impresión.

Por qué filas y columnas son distintas
--------------------------------------
Con un patrón cuadrado el detector no puede distinguir la orientación, y las
esquinas salen ordenadas de forma inconsistente entre vistas. Eso arruina la
calibración sin dar ningún error.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

MM_A_PT = 72.0 / 25.4  # PDF trabaja en puntos: 1 pt = 1/72 de pulgada

#: Tamaños de papel en milímetros (ancho, alto) en vertical.
PAPELES = {
    "carta": (215.9, 279.4),
    "a4": (210.0, 297.0),
    "oficio": (215.9, 355.6),
}


@dataclass(frozen=True, slots=True)
class Hoja:
    """Una hoja del patrón: qué porción del ajedrezado le toca imprimir."""

    fila: int  # índice de la hoja dentro de la grilla de hojas
    columna: int
    col_inicio: int  # primer cuadro del ajedrezado que va en esta hoja
    col_fin: int
    fila_inicio: int
    fila_fin: int


# --------------------------------------------------------------------------
# Escritura de PDF con biblioteca estándar
# --------------------------------------------------------------------------


def _texto_pdf(cadena: str) -> bytes:
    """Codifica un texto para un PDF, respetando los acentos del español.

    PDF usa WinAnsi (parecido a CP1252) para las fuentes estándar. Los caracteres
    fuera de ASCII se escapan en octal, que es la forma portable de escribirlos.
    """
    salida = bytearray()
    for byte in cadena.encode("cp1252", errors="replace"):
        if byte in (0x28, 0x29, 0x5C):  # ( ) \
            salida += b"\\" + bytes([byte])
        elif 32 <= byte < 127:
            salida.append(byte)
        else:
            salida += "\\{:03o}".format(byte).encode("ascii")
    return bytes(salida)


class _PDF:
    """Constructor mínimo de PDF: páginas con rectángulos, líneas y texto."""

    def __init__(self, ancho_mm: float, alto_mm: float):
        self.ancho = ancho_mm * MM_A_PT
        self.alto = alto_mm * MM_A_PT
        self._paginas: list[bytearray] = []
        self._actual: bytearray | None = None

    def nueva_pagina(self) -> None:
        self._actual = bytearray()
        self._paginas.append(self._actual)

    def rectangulo(self, x_mm, y_mm, ancho_mm, alto_mm, gris=0.0) -> None:
        """Rectángulo relleno. `y` se mide desde ABAJO, como manda PDF."""
        self._actual += "{:.4f} g {:.4f} {:.4f} {:.4f} {:.4f} re f\n".format(
            gris, x_mm * MM_A_PT, y_mm * MM_A_PT, ancho_mm * MM_A_PT, alto_mm * MM_A_PT
        ).encode("ascii")

    def linea(self, x1_mm, y1_mm, x2_mm, y2_mm, grosor_pt=0.5, gris=0.0) -> None:
        self._actual += (
            "{:.4f} G {:.3f} w {:.4f} {:.4f} m {:.4f} {:.4f} l S\n".format(
                gris, grosor_pt,
                x1_mm * MM_A_PT, y1_mm * MM_A_PT, x2_mm * MM_A_PT, y2_mm * MM_A_PT,
            ).encode("ascii")
        )

    def texto(self, x_mm, y_mm, cadena, tamano_pt=9.0, gris=0.0) -> None:
        self._actual += b"BT " + "/F1 {:.2f} Tf {:.4f} g {:.4f} {:.4f} Td (".format(
            tamano_pt, gris, x_mm * MM_A_PT, y_mm * MM_A_PT
        ).encode("ascii") + _texto_pdf(cadena) + b") Tj ET\n"

    def bytes(self) -> bytes:
        """Arma el archivo completo con su tabla de referencias cruzadas."""
        objetos: list[bytes] = []

        def agregar(cuerpo: bytes) -> int:
            objetos.append(cuerpo)
            return len(objetos)

        num_paginas = len(self._paginas)
        id_catalogo, id_paginas = 1, 2
        ids_pagina = [3 + i * 2 for i in range(num_paginas)]
        id_fuente = 3 + num_paginas * 2

        objetos.append(b"<< /Type /Catalog /Pages 2 0 R >>")
        objetos.append(
            "<< /Type /Pages /Kids [{}] /Count {} >>".format(
                " ".join("{} 0 R".format(i) for i in ids_pagina), num_paginas
            ).encode("ascii")
        )
        for i, contenido in enumerate(self._paginas):
            id_pag = ids_pagina[i]
            objetos.append(
                "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {:.4f} {:.4f}] "
                "/Resources << /Font << /F1 {} 0 R >> >> /Contents {} 0 R >>".format(
                    self.ancho, self.alto, id_fuente, id_pag + 1
                ).encode("ascii")
            )
            objetos.append(
                "<< /Length {} >>\nstream\n".format(len(contenido)).encode("ascii")
                + bytes(contenido) + b"\nendstream"
            )
        objetos.append(
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
            b"/Encoding /WinAnsiEncoding >>"
        )

        salida = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        posiciones = []
        for numero, cuerpo in enumerate(objetos, start=1):
            posiciones.append(len(salida))
            salida += "{} 0 obj\n".format(numero).encode("ascii") + cuerpo + b"\nendobj\n"
        inicio_xref = len(salida)
        salida += "xref\n0 {}\n".format(len(objetos) + 1).encode("ascii")
        salida += b"0000000000 65535 f \n"
        for pos in posiciones:
            salida += "{:010d} 00000 n \n".format(pos).encode("ascii")
        salida += "trailer\n<< /Size {} /Root {} 0 R >>\nstartxref\n{}\n%%EOF\n".format(
            len(objetos) + 1, id_catalogo, inicio_xref
        ).encode("ascii")
        return bytes(salida)


# --------------------------------------------------------------------------
# Reparto en hojas
# --------------------------------------------------------------------------


def repartir_en_hojas(
    cuadros_col: int, cuadros_fila: int, lado_mm: float, util_ancho: float, util_alto: float
) -> list[Hoja]:
    """Divide el ajedrezado en hojas, cortando siempre en el borde de un cuadro.

    Cortar por el borde de un cuadro y no por el medio es lo que hace posible
    pegar las hojas bien: el empalme cae donde ya hay un cambio de color, así que
    un error de medio milímetro no deforma ningún cuadro.
    """
    por_hoja_col = max(1, int(util_ancho // lado_mm))
    por_hoja_fila = max(1, int(util_alto // lado_mm))
    hojas = []
    for i, fila_ini in enumerate(range(0, cuadros_fila, por_hoja_fila)):
        for j, col_ini in enumerate(range(0, cuadros_col, por_hoja_col)):
            hojas.append(
                Hoja(
                    fila=i, columna=j,
                    col_inicio=col_ini, col_fin=min(col_ini + por_hoja_col, cuadros_col),
                    fila_inicio=fila_ini, fila_fin=min(fila_ini + por_hoja_fila, cuadros_fila),
                )
            )
    return hojas


# --------------------------------------------------------------------------
# Dibujo
# --------------------------------------------------------------------------


def _dibujar_regla(pdf: _PDF, x_mm: float, y_mm: float, largo_mm: float = 100.0) -> None:
    """Regla de verificación: si no mide lo que dice, la hoja salió escalada."""
    pdf.linea(x_mm, y_mm, x_mm + largo_mm, y_mm, grosor_pt=0.8)
    for i in range(0, int(largo_mm) + 1, 10):
        alto = 3.5 if i % 50 == 0 else 2.0
        pdf.linea(x_mm + i, y_mm, x_mm + i, y_mm + alto, grosor_pt=0.8)
    pdf.texto(x_mm, y_mm - 4.0, "|<--- esta linea debe medir exactamente {:.0f} mm --->|".format(largo_mm), 7.5)


def generar_pdf(
    columnas_internas: int,
    filas_internas: int,
    lado_mm: float,
    papel: str,
    horizontal: bool,
    margen_mm: float,
) -> tuple[bytes, list[Hoja], tuple[float, float]]:
    """Arma el PDF completo. Devuelve `(bytes, hojas, tamaño del patrón en mm)`."""
    ancho_papel, alto_papel = PAPELES[papel]
    if horizontal:
        ancho_papel, alto_papel = alto_papel, ancho_papel

    cuadros_col = columnas_internas + 1
    cuadros_fila = filas_internas + 1
    patron_ancho = cuadros_col * lado_mm
    patron_alto = cuadros_fila * lado_mm

    # Se reserva espacio abajo para la regla de verificación y los datos.
    reserva_inferior = 16.0
    util_ancho = ancho_papel - 2 * margen_mm
    util_alto = alto_papel - 2 * margen_mm - reserva_inferior
    hojas = repartir_en_hojas(cuadros_col, cuadros_fila, lado_mm, util_ancho, util_alto)

    pdf = _PDF(ancho_papel, alto_papel)
    total = len(hojas)

    for hoja in hojas:
        pdf.nueva_pagina()
        n_col = hoja.col_fin - hoja.col_inicio
        n_fila = hoja.fila_fin - hoja.fila_inicio
        ancho_trozo = n_col * lado_mm
        alto_trozo = n_fila * lado_mm
        x0 = (ancho_papel - ancho_trozo) / 2.0
        y0 = (alto_papel - alto_trozo + reserva_inferior) / 2.0

        # Cuadros negros. La paridad se calcula con el índice GLOBAL para que el
        # damero siga siendo coherente al pegar las hojas.
        for f in range(hoja.fila_inicio, hoja.fila_fin):
            for c in range(hoja.col_inicio, hoja.col_fin):
                if (f + c) % 2 == 0:
                    # El eje Y del PDF va hacia arriba y el del patrón hacia abajo.
                    x = x0 + (c - hoja.col_inicio) * lado_mm
                    y = y0 + (n_fila - 1 - (f - hoja.fila_inicio)) * lado_mm
                    pdf.rectangulo(x, y, lado_mm, lado_mm, gris=0.0)

        # Línea de corte exactamente en el borde del patrón, para pegar a tope.
        if total > 1:
            pdf.linea(x0, y0, x0 + ancho_trozo, y0, 0.3, 0.6)
            pdf.linea(x0, y0 + alto_trozo, x0 + ancho_trozo, y0 + alto_trozo, 0.3, 0.6)
            pdf.linea(x0, y0, x0, y0 + alto_trozo, 0.3, 0.6)
            pdf.linea(x0 + ancho_trozo, y0, x0 + ancho_trozo, y0 + alto_trozo, 0.3, 0.6)
            pdf.texto(
                x0, y0 + alto_trozo + 4.0,
                "HOJA {} de {}  (fila {}, columna {})  -  cortar por la linea gris y pegar a tope".format(
                    hojas.index(hoja) + 1, total, hoja.fila + 1, hoja.columna + 1), 8.0, 0.35,
            )

        # Datos y regla, siempre en la misma posición.
        pdf.texto(
            margen_mm, margen_mm + 9.0,
            "Patron de calibracion  -  {}x{} esquinas internas  -  cuadros de {:.1f} mm  -  "
            "patron completo {:.0f} x {:.0f} mm".format(
                columnas_internas, filas_internas, lado_mm, patron_ancho, patron_alto), 8.0,
        )
        _dibujar_regla(pdf, margen_mm, margen_mm + 3.0)

    # Última página: instrucciones.
    pdf.nueva_pagina()
    _pagina_instrucciones(pdf, ancho_papel, alto_papel, margen_mm, columnas_internas,
                          filas_internas, lado_mm, patron_ancho, patron_alto, total)

    return pdf.bytes(), hojas, (patron_ancho, patron_alto)


def _pagina_instrucciones(pdf, ancho, alto, margen, cols, filas, lado, p_ancho, p_alto, hojas) -> None:
    """Las instrucciones van impresas: de que la hoja quede plana y a escala
    depende toda la calibración, y esa hoja se va a usar meses después."""
    lineas = [
        ("COMO IMPRIMIR Y ARMAR ESTE PATRON", 14.0),
        ("", 10.0),
        ("Este patron mide {:.0f} x {:.0f} mm y usa cuadros de {:.1f} mm.".format(p_ancho, p_alto, lado), 10.0),
        ("Son {} hoja(s) de patron mas esta de instrucciones.".format(hojas), 10.0),
        ("", 10.0),
        ("1. IMPRIMIR AL 100 %", 12.0),
        ("   En el dialogo de impresion elegir 'Tamano real' o 'Escala 100 %'.", 10.0),
        ("   NUNCA 'Ajustar a la pagina': achica la hoja sin avisar y toda la", 10.0),
        ("   calibracion queda mal, sin que ningun numero lo delate.", 10.0),
        ("   Desactivar tambien cualquier opcion de 'ajuste automatico'.", 10.0),
        ("", 10.0),
        ("2. VERIFICAR CON UNA REGLA  <-- el paso que no hay que saltear", 12.0),
        ("   Medir la linea de 100 mm impresa al pie de cada hoja del patron.", 10.0),
        ("   Si mide 100 mm, la escala es correcta.", 10.0),
        ("   Si mide otra cosa, volver a imprimir: no sirve 'corregir' el numero", 10.0),
        ("   de milimetros en la configuracion, porque el error no es uniforme.", 10.0),
        ("", 10.0),
        ("3. PEGAR SOBRE ALGO RIGIDO Y PLANO", 12.0),
        ("   Vidrio, acrilico, MDF o carton pluma. NO carton corrugado comun:", 10.0),
        ("   se comba con la humedad y deja de ser plano.", 10.0),
        ("   Usar pegamento en aerosol o cinta doble faz en TODA la superficie,", 10.0),
        ("   no solo en las esquinas: una hoja pegada por los bordes se ondula.", 10.0),
        ("   Alisar desde el centro hacia afuera para no dejar burbujas.", 10.0),
        ("", 10.0),
        ("   Una ondulacion de 1 mm ya mete error: la calibracion supone que el", 10.0),
        ("   patron es un plano perfecto, y cada desviacion la interpreta como", 10.0),
        ("   distorsion del lente.", 10.0),
        ("", 10.0),
        ("4. SI SON VARIAS HOJAS", 12.0),
        ("   Cortar exactamente por la linea gris del borde del patron y pegarlas", 10.0),
        ("   a tope, sin superponer y sin dejar separacion. El corte cae siempre", 10.0),
        ("   en el borde de un cuadro, asi que el damero tiene que continuar sin", 10.0),
        ("   saltos. Verificar con la regla el ancho total del patron ya armado.", 10.0),
        ("", 10.0),
        ("5. CUIDADOS AL USARLO", 12.0),
        ("   Mate, no brillante: el reflejo tapa las esquinas.", 10.0),
        ("   Sin dobleces ni marcas. Guardarlo plano, nunca enrollado.", 10.0),
        ("", 10.0),
        ("EL DATO QUE HAY QUE PASARLE AL PROGRAMA", 12.0),
        ("   Lado del cuadro: {:.1f} mm     Esquinas internas: {} x {}".format(lado, cols, filas), 11.0),
        ("   Tiene que coincidir con config_vision.json -> calibracion.patron", 10.0),
    ]
    y = alto - margen - 6.0
    for texto, tamano in lineas:
        if texto:
            pdf.texto(margen, y, texto, tamano)
        y -= tamano * 0.45 + 2.2


# --------------------------------------------------------------------------
# Marcador de prueba para medir precisión de ubicación
# --------------------------------------------------------------------------


def _modulos_de_marcador(id_aruco: int, diccionario: str = "DICT_4X4_50") -> list[list[bool]]:
    """Devuelve el marcador como una grilla de módulos blanco/negro.

    Se extrae el patrón de bits en vez de incrustar una imagen porque un
    marcador ArUco **es** una grilla de cuadrados: dibujarlo como rectángulos lo
    deja con bordes exactos a cualquier tamaño de impresión, sin el suavizado ni
    la resolución limitada de una imagen embebida. Y el borde nítido es
    justamente lo que el detector mide con precisión subpíxel.
    """
    import cv2  # solo hace falta acá; el ajedrezado se dibuja sin OpenCV
    import numpy as np

    constante = getattr(cv2.aruco, diccionario)
    dicc = cv2.aruco.getPredefinedDictionary(constante)
    # 4x4 bits + un módulo de borde negro por lado = 6x6 módulos
    lado_modulos = 6
    px_por_modulo = 20
    imagen = cv2.aruco.generateImageMarker(dicc, id_aruco, lado_modulos * px_por_modulo)
    grilla = []
    for f in range(lado_modulos):
        fila = []
        for c in range(lado_modulos):
            centro = imagen[f * px_por_modulo + px_por_modulo // 2,
                            c * px_por_modulo + px_por_modulo // 2]
            fila.append(bool(centro < 128))  # True = negro
        grilla.append(fila)
    return grilla


def generar_marcador_prueba(
    id_aruco: int, lado_mm: float, papel: str, horizontal: bool, margen_mm: float,
    diccionario: str = "DICT_4X4_50",
) -> bytes:
    """PDF del marcador que se usa para medir la precisión de ubicación.

    Lleva **marcas de alineación** en los cuatro lados, prolongadas hacia afuera
    del marcador: sirven para apoyarlo contra las líneas de la cuadrícula del
    tablero. De esa alineación depende toda la exactitud de la prueba, porque la
    verdad se obtiene contando cuadros y no midiendo.
    """
    grilla = _modulos_de_marcador(id_aruco, diccionario)
    n = len(grilla)
    lado_modulo = lado_mm / n

    ancho_papel, alto_papel = PAPELES[papel]
    if horizontal:
        ancho_papel, alto_papel = alto_papel, ancho_papel

    pdf = _PDF(ancho_papel, alto_papel)
    pdf.nueva_pagina()

    x0 = (ancho_papel - lado_mm) / 2.0
    y0 = alto_papel - margen_mm - 40.0 - lado_mm

    for f in range(n):
        for c in range(n):
            if grilla[f][c]:
                # El eje Y del PDF va hacia arriba y el del marcador hacia abajo.
                pdf.rectangulo(x0 + c * lado_modulo,
                               y0 + (n - 1 - f) * lado_modulo,
                               lado_modulo, lado_modulo, gris=0.0)

    # Marcas de alineación: pequeños trazos que continúan los bordes del
    # marcador hacia afuera, para poder apoyarlo contra las líneas del tablero.
    largo = 8.0
    for x in (x0, x0 + lado_mm):
        pdf.linea(x, y0 - largo, x, y0 - 1.5, 0.4, 0.45)
        pdf.linea(x, y0 + lado_mm + 1.5, x, y0 + lado_mm + largo, 0.4, 0.45)
    for y in (y0, y0 + lado_mm):
        pdf.linea(x0 - largo, y, x0 - 1.5, y, 0.4, 0.45)
        pdf.linea(x0 + lado_mm + 1.5, y, x0 + lado_mm + largo, y, 0.4, 0.45)

    lineas = [
        ("MARCADOR DE PRUEBA DE PRECISION", 13.0),
        ("", 9.0),
        ("ID {}  ·  {}  ·  {:.0f} x {:.0f} mm  =  {:.0f} x {:.0f} cuadros de 20 mm".format(
            id_aruco, diccionario, lado_mm, lado_mm, lado_mm / 20.0, lado_mm / 20.0), 10.0),
        ("", 9.0),
        ("IMPRIMIR AL 100 % / TAMANO REAL. Nunca 'ajustar a la pagina'.", 10.0),
        ("Verificar con la regla de abajo antes de usarlo.", 10.0),
        ("", 9.0),
        ("RECORTAR dejando el borde blanco: el detector lo necesita para", 10.0),
        ("encontrar el marcador. No recortar al ras del negro.", 10.0),
        ("", 9.0),
        ("APOYARLO PLANO sobre el tablero, sin espesor. Los objetos con altura", 10.0),
        ("se ven corridos hacia afuera (paralaje). Con papel comun el efecto es", 10.0),
        ("despreciable; si se pega sobre algo mas grueso, declarar el espesor en", 10.0),
        ("config_vision.json -> precision.altura_marcador_mm.", 10.0),
        ("", 9.0),
        ("ALINEAR sus bordes con las lineas de la cuadricula, usando las marcas", 10.0),
        ("de los cuatro lados. De esa alineacion depende la exactitud de la", 10.0),
        ("prueba: la distancia real se obtiene CONTANDO CUADROS, no midiendo.", 10.0),
    ]
    y = y0 - 22.0
    for texto, tamano in lineas:
        if texto:
            pdf.texto(margen_mm, y, texto, tamano)
        y -= tamano * 0.5 + 2.4

    _dibujar_regla(pdf, margen_mm, margen_mm + 4.0)
    return pdf.bytes()


# --------------------------------------------------------------------------
# Vista previa en PNG (para verificar sin imprimir)
# --------------------------------------------------------------------------


def vista_previa_png(columnas_internas: int, filas_internas: int, ruta: str, px_por_cuadro: int = 60) -> bool:
    """Dibuja el mismo ajedrezado como imagen y comprueba que se detecta.

    Sirve para verificar la geometría del patrón **sin gastar papel**: si el
    detector no encuentra las esquinas acá, tampoco las va a encontrar impreso.
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return False

    n_col, n_fil = columnas_internas + 1, filas_internas + 1
    borde = px_por_cuadro
    img = np.full((n_fil * px_por_cuadro + 2 * borde, n_col * px_por_cuadro + 2 * borde), 255, np.uint8)
    for f in range(n_fil):
        for c in range(n_col):
            if (f + c) % 2 == 0:
                y, x = borde + f * px_por_cuadro, borde + c * px_por_cuadro
                img[y:y + px_por_cuadro, x:x + px_por_cuadro] = 0
    ok, esquinas = cv2.findChessboardCornersSB(img, (columnas_internas, filas_internas))
    color = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if ok:
        cv2.drawChessboardCorners(color, (columnas_internas, filas_internas), esquinas, ok)
    cv2.imwrite(ruta, color)
    return bool(ok)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera el patrón de ajedrez de calibración en PDF.")
    parser.add_argument("--columnas", type=int, default=None, help="esquinas internas horizontales")
    parser.add_argument("--filas", type=int, default=None, help="esquinas internas verticales")
    parser.add_argument("--lado-mm", type=float, default=None, help="lado del cuadro en mm")
    parser.add_argument("--papel", choices=sorted(PAPELES), default=None)
    parser.add_argument("--vertical", action="store_true", help="papel vertical (por defecto horizontal)")
    parser.add_argument("--margen-mm", type=float, default=12.0)
    parser.add_argument("--salida", default="patron_calibracion.pdf")
    parser.add_argument("--vista-previa", default=None, help="además, guardar un PNG de control")
    parser.add_argument("--marcador-prueba", type=int, default=None, metavar="ID",
                        help="en vez del ajedrezado, generar el marcador de prueba de precisión")
    parser.add_argument("--lado-marcador-mm", type=float, default=None,
                        help="lado del marcador de prueba, en mm")
    args = parser.parse_args(argv)

    try:  # la configuración manda; los argumentos solo la pisan
        from vision.configuracion import cargar_config
        cal = cargar_config().calibracion
        columnas = args.columnas or cal.columnas_internas
        filas = args.filas or cal.filas_internas
        lado = args.lado_mm or cal.lado_mm
        papel = args.papel or cal.papel
    except Exception:  # noqa: BLE001 — la herramienta tiene que servir sin config
        columnas, filas = args.columnas or 9, args.filas or 6
        lado, papel = args.lado_mm or 25.0, args.papel or "carta"

    # --- marcador de prueba de precisión ---------------------------------
    if args.marcador_prueba is not None:
        try:
            from vision.configuracion import cargar_config
            pr = cargar_config().precision
            lado = args.lado_marcador_mm or pr.lado_marcador_mm
            dicc = cargar_config().marcadores_esquina.nombre_diccionario
        except Exception:  # noqa: BLE001 — tiene que servir sin configuración
            lado, dicc = args.lado_marcador_mm or 60.0, "DICT_4X4_50"
        salida = args.salida
        if salida == "patron_calibracion.pdf":
            salida = "marcador_prueba_{}.pdf".format(args.marcador_prueba)
        with open(salida, "wb") as f:
            f.write(generar_marcador_prueba(args.marcador_prueba, lado, papel,
                                            not args.vertical, args.margen_mm, dicc))
        print("=" * 70)
        print("MARCADOR DE PRUEBA GENERADO")
        print("=" * 70)
        print("  archivo   : {}".format(os.path.abspath(salida)))
        print("  ID        : {}  ({})".format(args.marcador_prueba, dicc))
        print("  lado      : {:.0f} mm  =  {:.0f} cuadros de la cuadrícula".format(lado, lado / 20.0))
        print()
        print("  Imprimir al 100 %, recortar DEJANDO el borde blanco, y apoyarlo")
        print("  PLANO sobre el tablero alineado a las líneas de la cuadrícula.")
        print("=" * 70)
        return 0

    if columnas == filas:
        print("ERROR: columnas y filas deben ser DISTINTAS, o el detector no puede "
              "determinar la orientación del patrón.", file=sys.stderr)
        return 2

    datos, hojas, (p_ancho, p_alto) = generar_pdf(
        columnas, filas, lado, papel, not args.vertical, args.margen_mm)

    with open(args.salida, "wb") as f:
        f.write(datos)

    ancho_papel, alto_papel = PAPELES[papel]
    if not args.vertical:
        ancho_papel, alto_papel = alto_papel, ancho_papel

    print("=" * 70)
    print("PATRÓN DE CALIBRACIÓN GENERADO")
    print("=" * 70)
    print("  archivo         : {}".format(os.path.abspath(args.salida)))
    print("  esquinas internas: {} x {}".format(columnas, filas))
    print("  cuadros          : {} x {} de {:.1f} mm".format(columnas + 1, filas + 1, lado))
    print("  patrón completo  : {:.0f} x {:.0f} mm".format(p_ancho, p_alto))
    print("  papel            : {} {} ({:.0f} x {:.0f} mm)".format(
        papel, "vertical" if args.vertical else "horizontal", ancho_papel, alto_papel))
    print("  hojas de patrón  : {}{}".format(
        len(hojas), " (+1 de instrucciones)" if len(hojas) else ""))
    if len(hojas) > 1:
        print("  ATENCIÓN: hay que cortar por la línea gris y pegar a tope.")
    print()
    print("  AL IMPRIMIR: escala 100 % / tamaño real. NUNCA 'ajustar a la página'.")
    print("  Después, medir con una regla la línea de 100 mm impresa al pie.")
    print("  Las instrucciones completas están en la última página del PDF.")

    if args.vista_previa:
        ok = vista_previa_png(columnas, filas, args.vista_previa)
        print()
        print("  vista previa PNG : {} (detección de esquinas: {})".format(
            args.vista_previa, "OK" if ok else "FALLÓ"))
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
