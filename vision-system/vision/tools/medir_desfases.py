"""Mide los dos desfases entre el marcador y el robot, con el propio sistema.

Cómo se corre:

    python -m vision.tools.medir_desfases --autoprueba     # sin cámara, verifica la matemática
    python -m vision.tools.medir_desfases                  # con el robot real
    python -m vision.tools.medir_desfases --solo-angular
    python -m vision.tools.medir_desfases --solo-posicion --desfase-angular 40.2

Qué mide y por qué hace falta
-----------------------------
Lo que la visión detecta es la pose del **marcador**. Lo que el contrato publica
es la pose del **robot**. No son la misma cosa: el marcador está pegado en algún
lugar del chasis, casi nunca sobre el centro de rotación ni perfectamente
alineado con el frente. Los dos desfases son el puente, y hasta que se midan
están en cero (`deteccion_rovers` en `config_vision.json`).

Esta herramienta los mide **usando el propio sistema de visión**, sin
instrumental aparte. No hace falta medir nada con regla sobre el robot.

El desfase de posición: por qué el robot tiene que girar
--------------------------------------------------------
Si el robot gira sobre su eje y el marcador estuviera justo sobre el centro de
rotación, la posición reportada se quedaría quieta. Como está corrido, **describe
una circunferencia**: el centro de esa circunferencia es el centro de rotación
real y el radio es el módulo del desfase.

El ajuste NO es un ajuste de círculo
------------------------------------
Ajustar un círculo a la nube de posiciones funciona, pero **tira información**:
en cada muestra también medimos la **orientación** del marcador, y el ajuste de
círculo no la usa.

Usándola, el problema se vuelve lineal y de un solo paso:

    M_i  =  C  +  a · adelante(φ_i)  +  i · izquierda(φ_i)

`M_i` es la posición medida y `φ_i` la orientación medida; las incógnitas son el
centro `C` (dos números) y el desfase `(a, i)` (dos más). Cuatro incógnitas y
**dos ecuaciones por muestra**, todo lineal: se resuelve por mínimos cuadrados
sin iterar, y **la dirección sale en el mismo paso** en vez de deducirse después.

El ajuste de círculo de Kåsa se hace igual, pero como **control cruzado
independiente**: usa solo las posiciones, ignora las orientaciones y llega por
otro camino. Que los dos radios coincidan es la salvaguarda de un número que
después va a corregir todas las posiciones publicadas. Si discrepan, algo está
mal y conviene enterarse antes y no después.

Por qué el residuo es un diagnóstico físico
-------------------------------------------
El modelo supone giro **puro**. Si el robot se traslada mientras gira, la
trayectoria deja de ser una circunferencia y el residuo se dispara. Un residuo
alto casi nunca significa "la matemática falló": significa **"el robot se movió
del lugar"**, y así se reporta.
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import sys
import time

import cv2
import numpy as np

try:  # como paquete
    from ..configuracion import ConfigVision, Perspectiva, RoverDemo, cargar_config
    from ..detectors.rovers import (
        detectar_rovers,
        diferencia_angular,
        normalizar_grados,
    )
    from ..geometry.coordenadas import ErrorGeometria, construir_sistema, detectar_marcadores
    from ..geometry.distorsion import (
        ErrorCalibracion, FuenteRectificada, Rectificador, comparar_con_camara, elegir_perfil,
    )
    from ..sources.camara import ErrorCamara, FuenteCamara
    from ..sources.generador_sintetico import generar
    from .panel import AMBAR, BLANCO, GRIS, ROJO, VERDE, Panel, Tipografia, escala_para
    from .precision_ubicacion import factor_paralaje
except ImportError:  # como script suelto
    from vision.configuracion import (  # type: ignore[no-redef]
        ConfigVision, Perspectiva, RoverDemo, cargar_config,
    )
    from vision.detectors.rovers import (  # type: ignore[no-redef]
        detectar_rovers, diferencia_angular, normalizar_grados,
    )
    from vision.geometry.coordenadas import (  # type: ignore[no-redef]
        ErrorGeometria, construir_sistema, detectar_marcadores,
    )
    from vision.geometry.distorsion import (  # type: ignore[no-redef]
        ErrorCalibracion, FuenteRectificada, Rectificador, comparar_con_camara, elegir_perfil,
    )
    from vision.sources.camara import ErrorCamara, FuenteCamara  # type: ignore[no-redef]
    from vision.sources.generador_sintetico import generar  # type: ignore[no-redef]
    from vision.tools.panel import (  # type: ignore[no-redef]
        AMBAR, BLANCO, GRIS, ROJO, VERDE, Panel, Tipografia, escala_para,
    )
    from vision.tools.precision_ubicacion import factor_paralaje  # type: ignore[no-redef]

BASE_VISION = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_VERDE_BGR = (0, 200, 0)
_AMARILLO_BGR = (0, 200, 220)
_AZUL_BGR = (255, 80, 0)


# --------------------------------------------------------------------------
# Versores del marco del robot
# --------------------------------------------------------------------------


def versores(theta_grados: float) -> tuple[np.ndarray, np.ndarray]:
    """Los versores "adelante" e "izquierda" de un cuerpo orientado a `theta`.

    Son **los mismos** que usa `aplicar_desfases` en `detectors/rovers.py` para
    el camino de ida. Escribirlos una sola vez es lo que garantiza que medir y
    aplicar no puedan discrepar por una convención de signo: si acá hubiera un
    menos de más, el desfase medido saldría bien y se aplicaría al revés.

    El menos en las componentes de fila es porque `row` crece hacia abajo
    mientras que theta se mide en sentido antihorario.
    """
    rad = math.radians(theta_grados)
    adelante = np.array([math.cos(rad), -math.sin(rad)], dtype=np.float64)
    izquierda = np.array([-math.sin(rad), -math.cos(rad)], dtype=np.float64)
    return adelante, izquierda


# --------------------------------------------------------------------------
# Ángulos: media circular
# --------------------------------------------------------------------------


def media_circular(angulos: list[float]) -> tuple[float, float]:
    """Promedio de ángulos que respeta el cierre del círculo, y su dispersión.

    Devuelve `(media en [0,360), dispersión máxima en grados)`.

    **Promediar ángulos a secas está mal.** La media aritmética de 359° y 1° da
    180°, que es exactamente el lado contrario de la respuesta correcta, que es
    0°. La forma que sí funciona es promediar los vectores unitarios y volver a
    sacar el ángulo: `atan2(Σ sen, Σ cos)`.

    La dispersión se devuelve como la mayor distancia angular de una muestra a
    la media, medida con `diferencia_angular`, que también respeta el cierre.
    """
    if not angulos:
        return 0.0, 0.0
    senos = sum(math.sin(math.radians(a)) for a in angulos)
    cosenos = sum(math.cos(math.radians(a)) for a in angulos)
    media = normalizar_grados(math.degrees(math.atan2(senos, cosenos)))
    dispersion = max(abs(diferencia_angular(a, media)) for a in angulos)
    return media, dispersion


# --------------------------------------------------------------------------
# Los dos ajustes
# --------------------------------------------------------------------------


class AjustePosicion:
    """Resultado de estimar el centro de giro y el desfase de posición."""

    def __init__(self, centro_celdas, desfase_marco_marcador, residuos_celdas,
                 radio_kasa_celdas, centro_kasa_celdas, arco_grados, n):
        self.centro_celdas = centro_celdas
        self.desfase_marco_marcador = desfase_marco_marcador  # (a, i) en celdas
        self.residuos_celdas = residuos_celdas
        self.radio_kasa_celdas = radio_kasa_celdas
        self.centro_kasa_celdas = centro_kasa_celdas
        self.arco_grados = arco_grados
        self.n = n

    @property
    def radio_celdas(self) -> float:
        """Módulo del desfase según el ajuste lineal."""
        return float(np.hypot(*self.desfase_marco_marcador))

    @property
    def residuo_max_celdas(self) -> float:
        return float(max(self.residuos_celdas)) if len(self.residuos_celdas) else 0.0

    @property
    def residuo_rms_celdas(self) -> float:
        if not len(self.residuos_celdas):
            return 0.0
        return float(np.sqrt(np.mean(np.square(self.residuos_celdas))))

    @property
    def acuerdo_celdas(self) -> float:
        """Cuánto discrepan los dos métodos en el radio. Cerca de 0 es lo bueno."""
        return abs(self.radio_celdas - self.radio_kasa_celdas)


def ajustar_giro(muestras: list[tuple[float, float, float]]) -> AjustePosicion:
    """Estima el centro de rotación y el desfase, por mínimos cuadrados lineales.

    `muestras` es una lista de `(col, row, phi_grados)`: la posición y la
    orientación **del marcador** en cada captura.

    El modelo es `M = C + a·adelante(φ) + i·izquierda(φ)`, lineal en las cuatro
    incógnitas `(C_col, C_row, a, i)`, con dos ecuaciones por muestra. El
    `(a, i)` que devuelve es el vector que va **del centro de rotación al centro
    del marcador**, expresado en el marco del **marcador** (todavía no en el del
    robot: para eso hace falta el desfase angular).

    Se calcula además el ajuste de círculo de Kåsa sobre las mismas posiciones,
    ignorando las orientaciones, como control cruzado independiente.
    """
    n = len(muestras)
    if n < 3:
        raise ValueError("hacen falta al menos 3 muestras para ajustar el giro")

    filas = []
    observado = []
    for col, row, phi in muestras:
        adelante, izquierda = versores(phi)
        filas.append([1.0, 0.0, adelante[0], izquierda[0]])
        filas.append([0.0, 1.0, adelante[1], izquierda[1]])
        observado.append(col)
        observado.append(row)

    solucion, *_ = np.linalg.lstsq(
        np.array(filas, dtype=np.float64), np.array(observado, dtype=np.float64), rcond=None
    )
    centro = np.array(solucion[:2], dtype=np.float64)
    desfase = np.array(solucion[2:], dtype=np.float64)

    # Residuo por muestra: distancia entre dónde cayó y dónde el modelo dice que
    # tendría que haber caído. Es lo que delata que el robot se trasladó.
    residuos = []
    for col, row, phi in muestras:
        adelante, izquierda = versores(phi)
        predicho = centro + desfase[0] * adelante + desfase[1] * izquierda
        residuos.append(float(np.hypot(col - predicho[0], row - predicho[1])))

    centro_kasa, radio_kasa = ajustar_circulo_kasa(
        np.array([[c, r] for c, r, _ in muestras], dtype=np.float64)
    )

    return AjustePosicion(
        centro_celdas=centro,
        desfase_marco_marcador=desfase,
        residuos_celdas=np.array(residuos, dtype=np.float64),
        radio_kasa_celdas=radio_kasa,
        centro_kasa_celdas=centro_kasa,
        arco_grados=arco_cubierto([m[2] for m in muestras]),
        n=n,
    )


def ajustar_circulo_kasa(puntos: np.ndarray) -> tuple[np.ndarray, float]:
    """Ajusta un círculo a una nube de puntos, por el método algebraico de Kåsa.

    Es el **control cruzado**: llega al mismo radio por un camino que no usa las
    orientaciones para nada. Dos matemáticas independientes que coinciden es una
    garantía mucho más fuerte que una sola que da un número lindo.

    El truco de Kåsa es que la ecuación del círculo, escrita como
    `x² + y² + D·x + E·y + F = 0`, es **lineal** en `(D, E, F)`. El centro sale
    de `(−D/2, −E/2)` y el radio de ahí.
    """
    x = puntos[:, 0]
    y = puntos[:, 1]
    a = np.column_stack((x, y, np.ones_like(x)))
    b = -(x ** 2 + y ** 2)
    solucion, *_ = np.linalg.lstsq(a, b, rcond=None)
    d, e, f = solucion
    centro = np.array([-d / 2.0, -e / 2.0], dtype=np.float64)
    bajo_raiz = centro[0] ** 2 + centro[1] ** 2 - f
    radio = float(math.sqrt(bajo_raiz)) if bajo_raiz > 0 else 0.0
    return centro, radio


def arco_cubierto(angulos: list[float]) -> float:
    """Cuánto del círculo abarcan las orientaciones capturadas, en grados.

    No es `max - min`: eso daría casi 360 para dos muestras en 1° y 359°, que en
    realidad están **pegadas**. Se ordenan los ángulos, se mide el hueco más
    grande entre consecutivos —cerrando la vuelta— y se resta de 360. Lo que
    queda es el arco realmente cubierto.
    """
    if len(angulos) < 2:
        return 0.0
    orden = sorted(normalizar_grados(a) for a in angulos)
    huecos = [orden[k + 1] - orden[k] for k in range(len(orden) - 1)]
    huecos.append(360.0 - orden[-1] + orden[0])  # el hueco que cierra la vuelta
    return float(360.0 - max(huecos))


def a_marco_robot(desfase_marco_marcador: np.ndarray, desfase_angular: float) -> np.ndarray:
    """Pasa el desfase del marco del MARCADOR al marco del ROBOT.

    Los dos marcos difieren en una rotación de `α` grados: el frente del robot
    está a `α` del "arriba" del marcador. Rotar las componentes por `−α` es todo
    lo que hace falta, y sale de proyectar los versores de un marco sobre los del
    otro.

    Devuelve el vector que va **del centro de rotación al centro del marcador**,
    ahora en adelante/izquierda del robot.
    """
    rad = math.radians(desfase_angular)
    a, i = float(desfase_marco_marcador[0]), float(desfase_marco_marcador[1])
    return np.array([a * math.cos(rad) + i * math.sin(rad),
                     -a * math.sin(rad) + i * math.cos(rad)], dtype=np.float64)


# --------------------------------------------------------------------------
# El veredicto
# --------------------------------------------------------------------------


class Veredicto:
    """Si el resultado se puede usar, y por qué sí o por qué no."""

    def __init__(self) -> None:
        self.motivos: list[tuple[str, str]] = []  # (nivel, texto); nivel: ok|flojo|malo

    def anotar(self, nivel: str, texto: str) -> None:
        self.motivos.append((nivel, texto))

    @property
    def sirve(self) -> bool:
        return not any(n == "malo" for n, _ in self.motivos)

    @property
    def etiqueta(self) -> str:
        if any(n == "malo" for n, _ in self.motivos):
            return "INSUFICIENTE"
        if any(n == "flojo" for n, _ in self.motivos):
            return "FLOJO"
        return "CONFIABLE"


def evaluar(ajuste: AjustePosicion, cfg: ConfigVision) -> Veredicto:
    """Aplica los umbrales de la configuración al ajuste y arma el veredicto."""
    m = cfg.medicion_desfases
    cell = cfg.tablero.cell_mm
    v = Veredicto()

    if ajuste.arco_grados < m.arco_inaceptable_grados:
        v.anotar("malo", "el robot giró solo {:.0f}°: por debajo de {:.0f}° el ajuste no "
                         "distingue el centro del desfase (amplificación ×{:.0f})".format(
                             ajuste.arco_grados, m.arco_inaceptable_grados,
                             amplificacion(ajuste.arco_grados)))
    elif ajuste.arco_grados < m.arco_minimo_grados:
        v.anotar("flojo", "arco de {:.0f}°, por debajo del mínimo de {:.0f}° "
                          "(amplificación del error ×{:.1f})".format(
                              ajuste.arco_grados, m.arco_minimo_grados,
                              amplificacion(ajuste.arco_grados)))
    elif ajuste.arco_grados < m.arco_recomendado_grados:
        v.anotar("flojo", "arco de {:.0f}°: alcanza, pero una vuelta completa mide mejor".format(
            ajuste.arco_grados))
    else:
        v.anotar("ok", "arco de {:.0f}° sobre {} muestras".format(ajuste.arco_grados, ajuste.n))

    if ajuste.n < m.muestras_minimas:
        v.anotar("malo", "solo {} muestras; hacen falta al menos {}".format(
            ajuste.n, m.muestras_minimas))

    # El veredicto mira el RMS y no el máximo. El máximo lo fija una sola muestra
    # desafortunada —con 24 muestras siempre hay una—, así que juzgar por él
    # daría falsas alarmas sobre mediciones sanas. Una traslación del robot no
    # afecta a una muestra: corre todas, y eso el RMS lo ve igual de bien.
    rms_mm = ajuste.residuo_rms_celdas * cell
    peor_mm = ajuste.residuo_max_celdas * cell
    if rms_mm > m.residuo_aceptable_mm:
        v.anotar("malo", "residuo RMS de {:.2f} mm: las muestras no describen un giro puro. "
                         "Casi seguro el robot SE TRASLADÓ mientras giraba".format(rms_mm))
    elif rms_mm > m.residuo_bueno_mm:
        v.anotar("flojo", "residuo RMS de {:.2f} mm: el robot se movió un poco del lugar".format(
            rms_mm))
    else:
        v.anotar("ok", "residuo RMS {:.2f} mm (peor muestra {:.2f}): el giro fue limpio".format(
            rms_mm, peor_mm))

    acuerdo_mm = ajuste.acuerdo_celdas * cell
    if acuerdo_mm > m.acuerdo_metodos_mm:
        v.anotar("malo", "los dos métodos discrepan {:.2f} mm en el radio "
                         "(lineal {:.2f} vs Kåsa {:.2f})".format(
                             acuerdo_mm, ajuste.radio_celdas * cell,
                             ajuste.radio_kasa_celdas * cell))
    else:
        v.anotar("ok", "ajuste lineal y círculo de Kåsa coinciden en {:.2f} mm".format(acuerdo_mm))

    radio_mm = ajuste.radio_celdas * cell
    if radio_mm < m.radio_minimo_mm:
        v.anotar("flojo", "el desfase mide {:.2f} mm, comparable al ruido: el marcador está "
                          "prácticamente sobre el centro de giro y la DIRECCIÓN no está "
                          "determinada. Conviene dejarlo en cero".format(radio_mm))
    return v


class DiagnosticoVivo:
    """Cómo va el giro, calculado mientras se captura y no al final.

    Existe por una sesión perdida: el robot se trasladaba mientras giraba y eso
    recién se supo al terminar de capturar, con el veredicto INSUFICIENTE. La
    información estaba disponible desde la cuarta muestra; lo único que faltaba
    era mostrarla.

    Usa **los mismos umbrales** que el veredicto final. Un aviso en vivo que
    juzgara con otro criterio sería peor que no tenerlo: diría "vas bien" y
    después reprobaría, o al revés.
    """

    def __init__(self, nube_mm: float, diametro_mm: float, rms_mm: float, nivel: str):
        self.nube_mm = nube_mm
        self.diametro_mm = diametro_mm
        self.rms_mm = rms_mm
        self.nivel = nivel

    @property
    def texto(self) -> str:
        return "nube {:.0f} mm · círculo esperado {:.0f} mm".format(
            self.nube_mm, self.diametro_mm)


def diagnostico_en_vivo(muestras, cfg) -> DiagnosticoVivo | None:
    """Compara el tamaño de la nube con el círculo que el ajuste va estimando.

    La comprobación es directa: si el desfase vale `r`, la posición del marcador
    en una vuelta completa tiene que recorrer un círculo de diámetro `2r` **y
    nada más**. Una nube mucho más grande que eso no es un desfase grande: es el
    robot desplazándose por la cancha mientras gira.

    Hacen falta al menos cuatro muestras: con tres, el ajuste tiene tantas
    ecuaciones como incógnitas y el residuo da cero por construcción, lo que
    diría "todo bien" siempre.
    """
    if len(muestras) < 4:
        return None
    try:
        ajuste = ajustar_giro(muestras)
    except (ValueError, np.linalg.LinAlgError):
        return None

    cell = cfg.tablero.cell_mm
    columnas = [c for c, _, _ in muestras]
    filas = [r for _, r, _ in muestras]
    nube_mm = max(max(columnas) - min(columnas), max(filas) - min(filas)) * cell
    diametro_mm = 2.0 * ajuste.radio_celdas * cell
    rms_mm = ajuste.residuo_rms_celdas * cell

    m = cfg.medicion_desfases
    if rms_mm > m.residuo_aceptable_mm:
        nivel = "malo"
    elif rms_mm > m.residuo_bueno_mm:
        nivel = "flojo"
    else:
        nivel = "ok"
    return DiagnosticoVivo(nube_mm, diametro_mm, rms_mm, nivel)


def amplificacion(arco_grados: float) -> float:
    """Cuánto amplifica el error del centro un arco corto: `1/(1−cos(arco/2))`.

    Es la razón por la que hay un arco mínimo. Con 360° o 180° vale 1; con 45°
    ya vale 13, y con 20° vale 66: el mismo ruido de medición produce un centro
    sesenta veces peor. El número no se estima, se calcula.
    """
    sagitta = 1.0 - math.cos(math.radians(min(arco_grados, 180.0)) / 2.0)
    return float(1.0 / sagitta) if sagitta > 1e-9 else float("inf")


# --------------------------------------------------------------------------
# Informe
# --------------------------------------------------------------------------


def informar(ajuste, desfase_angular, dispersion_angular, n_orientaciones,
             cfg, altura_camara_mm) -> dict:
    """Imprime el resultado completo y devuelve lo que hay que guardar."""
    cell = cfg.tablero.cell_mm
    veredicto = evaluar(ajuste, cfg)

    centro_a_marcador = a_marco_robot(ajuste.desfase_marco_marcador, desfase_angular) * cell
    marcador_a_centro = -centro_a_marcador

    k = factor_paralaje(altura_camara_mm, cfg.paralaje.altura_marcador_rover_mm)
    corregido = marcador_a_centro / k

    print()
    print("=" * 78)
    print("RESULTADO DE LA MEDICIÓN")
    print("=" * 78)

    print("\n  Calidad del ajuste: {}\n".format(veredicto.etiqueta))
    simbolos = {"ok": "  ✓", "flojo": "  ⚠", "malo": "  ✗"}
    for nivel, texto in veredicto.motivos:
        print("{} {}".format(simbolos[nivel], texto))

    print("\n  Geometría del giro")
    print("    centro de rotación   : celda ({:.3f}, {:.3f})".format(*ajuste.centro_celdas))
    print("    radio (ajuste lineal): {:.2f} mm".format(ajuste.radio_celdas * cell))
    print("    radio (círculo Kåsa) : {:.2f} mm   <- control cruzado independiente".format(
        ajuste.radio_kasa_celdas * cell))

    print("\n  Desfase de posición, en el marco del robot")
    print("    del centro de giro AL marcador : adelante {:+.2f} mm, izquierda {:+.2f} mm".format(
        *centro_a_marcador))
    print("    del marcador AL centro de giro : adelante {:+.2f} mm, izquierda {:+.2f} mm".format(
        *marcador_a_centro))
    print("                                     ^ éste es el que espera la configuración")

    print("\n  Corrección de paralaje")
    print("    el marcador está a {:.0f} mm del tablero y la cámara a {:.0f} mm,".format(
        cfg.paralaje.altura_marcador_rover_mm, altura_camara_mm))
    print("    así que toda distancia medida viene inflada por k = {:.4f} ({:+.1f} %).".format(
        k, (k - 1) * 100))
    print("    El paralaje escala pero NO rota: la dirección ya estaba bien, solo sobra módulo.")
    print("    medido    : adelante {:+.2f} mm, izquierda {:+.2f} mm".format(*marcador_a_centro))
    print("    corregido : adelante {:+.2f} mm, izquierda {:+.2f} mm   <- el recomendado".format(
        *corregido))

    print("\n  Desfase angular")
    print("    {:+.2f}°  sobre {} orientaciones, dispersión máxima {:.2f}°".format(
        desfase_angular, n_orientaciones, dispersion_angular))

    print("\n" + "-" * 78)
    print("  Para pegar en vision/config_vision.json -> deteccion_rovers:\n")
    print('      "desfase_marcador_a_centro_mm": {{ "adelante": {:.2f}, "izquierda": {:.2f} }},'.format(
        corregido[0], corregido[1]))
    print('      "desfase_angular_grados": {:.2f}'.format(desfase_angular))
    print("\n  NO se aplicó nada. Revisalos y ponelos vos.")
    if not veredicto.sirve:
        print("\n  ⚠️  EL VEREDICTO ES {}: estos números NO son confiables.".format(
            veredicto.etiqueta))
        print("      Repetí la medición atendiendo los puntos marcados con ✗.")
    print("-" * 78)
    print()

    return {
        "veredicto": veredicto.etiqueta,
        "motivos": [{"nivel": n, "texto": t} for n, t in veredicto.motivos],
        "muestras": ajuste.n,
        "arco_grados": round(ajuste.arco_grados, 2),
        "centro_celdas": [round(float(x), 4) for x in ajuste.centro_celdas],
        "radio_lineal_mm": round(ajuste.radio_celdas * cell, 3),
        "radio_kasa_mm": round(ajuste.radio_kasa_celdas * cell, 3),
        "residuo_max_mm": round(ajuste.residuo_max_celdas * cell, 3),
        "residuo_rms_mm": round(ajuste.residuo_rms_celdas * cell, 3),
        "altura_camara_mm": altura_camara_mm,
        "factor_paralaje": round(k, 5),
        "desfase_marcador_a_centro_mm_medido": [round(float(x), 3) for x in marcador_a_centro],
        "desfase_marcador_a_centro_mm_corregido": [round(float(x), 3) for x in corregido],
        "desfase_angular_grados": round(desfase_angular, 3),
        "dispersion_angular_grados": round(dispersion_angular, 3),
        "orientaciones": n_orientaciones,
    }


def guardar_sesion(datos: dict, muestras, cfg, ruta: str) -> None:
    """Guarda la medición cruda, para que sea auditable y repetible.

    Se guardan las muestras y no solo el resultado: si mañana aparece una forma
    mejor de ajustar, se puede recalcular sobre los mismos datos sin volver a
    girar el robot.
    """
    datos = dict(datos)
    datos["muestras_crudas"] = [
        {"col": round(c, 4), "row": round(r, 4), "phi_grados": round(p, 3)}
        for c, r, p in muestras
    ]
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)
    print("  Sesión guardada en: {}\n".format(ruta))


# --------------------------------------------------------------------------
# Autoprueba: verificar la matemática contra la verdad conocida
# --------------------------------------------------------------------------


def simular_giro(cfg, adelante_mm, izquierda_mm, desfase_angular, centro_celda,
                 pasos, con_perspectiva) -> list[tuple[float, float, float]]:
    """Genera imágenes de un robot con un desfase CONOCIDO y las detecta.

    Coloca el marcador donde estaría de verdad si el robot, con ese desfase,
    girara sobre su eje: `M = C + adelante·f(θ) + izquierda·l(θ)`, con la
    orientación del marcador `φ = θ − α`. Después detecta esas imágenes con la
    cadena real —marcadores, geometría, `detectar_rovers`— y devuelve lo que el
    sistema **midió**, no lo que se dibujó.

    Es lo que convierte la autoprueba en una prueba de verdad: si hubiera un
    signo cambiado en los versores, en el paso al marco del robot o en el
    ajuste, acá se ve.
    """
    cell = cfg.tablero.cell_mm
    persp = Perspectiva(activa=con_perspectiva, inclinacion_grados=cfg.sintetico.perspectiva.inclinacion_grados)
    centro = np.array(centro_celda, dtype=np.float64)

    muestras = []
    for theta in pasos:
        adelante, izquierda = versores(theta)
        posicion = centro + (adelante_mm / cell) * adelante + (izquierda_mm / cell) * izquierda
        phi = normalizar_grados(theta - desfase_angular)
        rover = RoverDemo(id=10, col=float(posicion[0]), row=float(posicion[1]), theta=phi)

        imagen, _ = generar(cfg, rovers=(rover,), perspectiva=persp)
        detectados = detectar_marcadores(imagen, cfg.marcadores_esquina.nombre_diccionario)
        sistema = construir_sistema(imagen, cfg, detectados)
        vistos = detectar_rovers(detectados, sistema, cfg)
        if not vistos:
            continue
        medido = vistos[0].marcador
        muestras.append((medido.col, medido.row, medido.theta_grados))
    return muestras


def autoprueba(cfg, con_perspectiva: bool) -> bool:
    """Verifica el estimador contra un desfase inyectado y conocido."""
    # Valores deliberadamente asimétricos y con signos distintos: un error de
    # signo o un cambio de eje no podría pasar desapercibido detrás de una
    # simetría.
    ADELANTE, IZQUIERDA, ANGULAR = 35.0, -12.0, 40.0
    CENTRO = (21.5, 21.5)

    titulo = "CON perspectiva" if con_perspectiva else "SIN perspectiva (cenital)"
    print("=" * 78)
    print("AUTOPRUEBA — {}".format(titulo))
    print("=" * 78)
    print("  desfase inyectado (del centro de giro al marcador, marco del robot):")
    print("    adelante {:+.2f} mm   izquierda {:+.2f} mm   angular {:+.2f}°".format(
        ADELANTE, IZQUIERDA, ANGULAR))
    print("  centro de rotación inyectado: celda ({:.2f}, {:.2f})".format(*CENTRO))

    cell = cfg.tablero.cell_mm
    todo_bien = True

    print("\n  {:<26} {:>8} {:>10} {:>10} {:>10} {:>9}".format(
        "vuelta del robot", "muestras", "adelante", "izquierda", "angular", "estado"))
    print("  " + "-" * 78)

    for etiqueta, pasos in (
        ("completa (360°)", [float(k * 15) for k in range(24)]),
        ("media vuelta (180°)", [float(k * 15) for k in range(13)]),
        ("un cuarto (90°)", [float(k * 15) for k in range(7)]),
    ):
        muestras = simular_giro(cfg, ADELANTE, IZQUIERDA, ANGULAR, CENTRO, pasos, con_perspectiva)
        if len(muestras) < 3:
            print("  {:<26} {:>8} — no se detectaron suficientes marcadores".format(
                etiqueta, len(muestras)))
            todo_bien = False
            continue

        ajuste = ajustar_giro(muestras)

        # El desfase angular, con el mismo método que usa el modo real: se
        # conoce theta del robot y se mide phi del marcador.
        alfas = [diferencia_angular(theta, phi) for theta, (_, _, phi) in zip(pasos, muestras)]
        angular, dispersion_ang = media_circular(alfas)

        # Se verifica el valor CORREGIDO, que es el que la herramienta recomienda
        # pegar en la configuración. El crudo viene inflado por el paralaje: el
        # marcador está a 90 mm del tablero, así que el círculo que describe se
        # ve más grande de lo que es. Comparar el crudo daría un error de 1,5 mm
        # que no es del estimador sino del efecto que la corrección descuenta.
        k = factor_paralaje(cfg.sintetico.altura_camara_mm,
                            cfg.paralaje.altura_marcador_rover_mm)
        crudo = a_marco_robot(ajuste.desfase_marco_marcador, angular) * cell
        centro_a_marcador = crudo / k
        err_a = abs(centro_a_marcador[0] - ADELANTE)
        err_i = abs(centro_a_marcador[1] - IZQUIERDA)
        err_ang = abs(diferencia_angular(angular, ANGULAR))
        err_centro = float(np.hypot(*(ajuste.centro_celdas - np.array(CENTRO)))) * cell

        # Tolerancias generosas para el cuarto de vuelta: el punto de ese caso es
        # justamente mostrar que el error crece, no que se mantenga.
        tolerancia = 2.0 if len(pasos) > 10 else 6.0
        paso = err_a <= tolerancia and err_i <= tolerancia and err_ang <= 1.5
        todo_bien = todo_bien and (paso or len(pasos) <= 7)

        print("  {:<26} {:>8} {:>+10.2f} {:>+10.2f} {:>+10.2f} {:>9}".format(
            etiqueta, len(muestras), centro_a_marcador[0], centro_a_marcador[1],
            angular, "OK" if paso else "flojo"))
        print("  {:<26} {:>8} {:>10} {:>10} {:>10}".format(
            "   error contra la verdad", "", "{:.2f} mm".format(err_a),
            "{:.2f} mm".format(err_i), "{:.2f}°".format(err_ang)))
        print("  {:<26} {:>8} {:>10.2f} {:>10.2f} {:>10}".format(
            "   crudo, antes de paralaje", "", crudo[0], crudo[1],
            "x{:.4f}".format(k)))
        print("  {:<26} {:>8} {:>10} {:>10} {:>10}".format(
            "   centro / residuo / acuerdo", "",
            "{:.2f} mm".format(err_centro),
            "{:.2f} mm".format(ajuste.residuo_max_celdas * cell),
            "{:.2f} mm".format(ajuste.acuerdo_celdas * cell)))
        print("  {:<26} {:>8} arco {:.0f}°  amplificación ×{:.1f}".format(
            "", "", ajuste.arco_grados, amplificacion(ajuste.arco_grados)))
        print()

    return todo_bien


def autoprueba_media_circular() -> bool:
    """Comprueba que el promedio de ángulos respeta el cierre del círculo."""
    print("=" * 78)
    print("AUTOPRUEBA — media circular contra promedio ingenuo")
    print("=" * 78)
    casos = [
        ([359.0, 1.0], 0.0),
        ([350.0, 10.0, 355.0, 5.0], 0.0),
        ([89.0, 91.0], 90.0),
        ([358.0, 2.0, 0.0], 0.0),
    ]
    todo_bien = True
    print("\n  {:<28} {:>12} {:>12} {:>10} {}".format(
        "ángulos", "ingenuo", "circular", "esperado", "estado"))
    print("  " + "-" * 74)
    for angulos, esperado in casos:
        ingenuo = sum(angulos) / len(angulos)
        circular, _ = media_circular(angulos)
        ok = abs(diferencia_angular(circular, esperado)) < 0.001
        todo_bien = todo_bien and ok
        aviso = "  <- el ingenuo miente" if abs(diferencia_angular(ingenuo, esperado)) > 1.0 else ""
        print("  {:<28} {:>12.2f} {:>12.2f} {:>10.2f} {}{}".format(
            str(angulos), ingenuo, circular, esperado, "OK" if ok else "FALLA", aviso))
    print()
    return todo_bien


# --------------------------------------------------------------------------
# Captura con el robot real
# --------------------------------------------------------------------------


def _pose_del_rover(imagen, cfg, id_rover):
    """Devuelve la pose del marcador del rover pedido, o None."""
    detectados = detectar_marcadores(imagen, cfg.marcadores_esquina.nombre_diccionario)
    try:
        sistema = construir_sistema(imagen, cfg, detectados)
    except ErrorGeometria:
        return None, detectados, None
    for rover in detectar_rovers(detectados, sistema, cfg):
        if rover.id == id_rover:
            return rover.marcador, detectados, sistema
    return None, detectados, sistema


def _promediar_cuadros(fuente, cfg, id_rover, cuantos, tiempo_max=5.0):
    """Promedia la pose sobre varios cuadros. Los ángulos, en media circular."""
    cols, rows, angulos = [], [], []
    limite = time.monotonic() + tiempo_max
    while len(cols) < cuantos and time.monotonic() < limite:
        cuadro = fuente.leer()
        if cuadro is None:
            time.sleep(0.01)
            continue
        pose, _, _ = _pose_del_rover(cuadro.imagen, cfg, id_rover)
        if pose is None:
            continue
        cols.append(pose.col)
        rows.append(pose.row)
        angulos.append(pose.theta_grados)
    if len(cols) < max(3, cuantos // 3):
        return None
    media_ang, _ = media_circular(angulos)
    return (sum(cols) / len(cols), sum(rows) / len(rows), media_ang)


def _dibujar_estado(lienzo, detectados, id_rover, muestras, sistema):
    """Marca los marcadores y deja ver la nube de puntos que se va formando."""
    for id_m, esquinas in detectados.items():
        color = _VERDE_BGR if id_m == id_rover else _AMARILLO_BGR
        cv2.polylines(lienzo, [esquinas.astype(np.int32).reshape(-1, 1, 2)], True, color, 2)
    if sistema is None or not muestras:
        return
    puntos = sistema.a_pixeles(np.array([[c, r] for c, r, _ in muestras], dtype=np.float64))
    for x, y in puntos:
        cv2.circle(lienzo, (int(round(x)), int(round(y))), 4, _AZUL_BGR, -1)


def medir_posicion(fuente, cfg, id_rover, tipografia, ventana) -> list | None:
    """Guía la captura del giro y devuelve las muestras. `None` si se canceló."""
    m = cfg.medicion_desfases
    muestras: list[tuple[float, float, float]] = []
    anterior = None
    quieto_desde = None
    mensaje = ""
    diagnostico = None
    aviso_dado = False

    print("\n  PASO 2 — desfase de posición")
    print("  Hacé girar el robot SOBRE SU EJE, sin que se traslade: las dos ruedas")
    print("  en sentidos opuestos y a la misma velocidad, no un pivote sobre una.")
    print("  Girá un poco, soltá, esperá a que capture, y seguí. Una vuelta completa.")
    print("  Mirá el indicador 'Giro puro': si se pone rojo, el robot se está")
    print("  trasladando y conviene parar y reintentar.")
    print("  ESPACIO fuerza una captura · ENTER termina · ESC cancela\n")

    while True:
        cuadro = fuente.leer()
        if cuadro is None:
            time.sleep(0.01)
            continue
        lienzo = cuadro.imagen.copy()
        pose, detectados, sistema = _pose_del_rover(cuadro.imagen, cfg, id_rover)
        _dibujar_estado(lienzo, detectados, id_rover, muestras, sistema)

        arco = arco_cubierto([p for _, _, p in muestras])
        listo = len(muestras) >= m.muestras_minimas and arco >= m.arco_minimo_grados

        # Captura automática: el marcador tiene que estar quieto y haber girado
        # lo suficiente desde la última muestra aceptada.
        capturar = False
        if pose is not None:
            if anterior is not None and math.hypot(pose.col - anterior[0], pose.row - anterior[1]) < m.estabilidad_celdas:
                if quieto_desde is None:
                    quieto_desde = time.monotonic()
                elif time.monotonic() - quieto_desde >= m.pausa_s:
                    avance = min(
                        (abs(diferencia_angular(pose.theta_grados, p)) for _, _, p in muestras),
                        default=999.0,
                    )
                    if avance >= m.paso_angular_grados:
                        capturar = True
            else:
                quieto_desde = None
            anterior = (pose.col, pose.row)

        panel = Panel(tipografia)
        panel.titulo("Medición de desfases · giro del robot")
        panel.destacado("{} de {} muestras".format(len(muestras), m.muestras_objetivo),
                        VERDE if listo else BLANCO,
                        "arco cubierto: {:.0f}° de 360°".format(arco))
        panel.separador()
        if pose is None:
            panel.estado("Rover {}".format(id_rover), "no se ve", ROJO)
        else:
            panel.estado("Rover {}".format(id_rover),
                         "celda ({:.2f}, {:.2f})  {:.1f}°".format(pose.col, pose.row, pose.theta_grados),
                         VERDE)
        panel.estado("Arco", "{:.0f}°  (mínimo {:.0f}°)".format(arco, m.arco_minimo_grados),
                     VERDE if arco >= m.arco_recomendado_grados else
                     (AMBAR if arco >= m.arco_minimo_grados else ROJO))
        if diagnostico is not None:
            panel.estado("Giro puro", diagnostico.texto,
                         {"ok": VERDE, "flojo": AMBAR, "malo": ROJO}[diagnostico.nivel])
        panel.separador()
        if diagnostico is not None and diagnostico.nivel == "malo":
            panel.datos("EL ROBOT SE ESTÁ TRASLADANDO — pará y reintentá", ROJO)
            panel.datos("la nube tendría que ser una manchita, no un paseo", GRIS)
        else:
            panel.datos("Girá el robot SOBRE SU EJE, sin trasladarlo")
            panel.datos("Girá un poco y soltá: captura sola al quedar quieto", GRIS)
        if mensaje:
            panel.datos(mensaje, VERDE)
        panel.pie("ESPACIO capturar · ENTER terminar · ESC cancelar")
        panel.dibujar(lienzo)

        cv2.imshow(ventana, lienzo)
        tecla = cv2.waitKey(1) & 0xFF

        if tecla == 27:
            return None
        if tecla == 13 or tecla == 10:
            if listo:
                return muestras
            mensaje = "faltan muestras o arco"
        if tecla == 32:
            capturar = pose is not None

        if capturar:
            promedio = _promediar_cuadros(fuente, cfg, id_rover, m.cuadros_por_muestra)
            if promedio is not None:
                muestras.append(promedio)
                mensaje = "muestra {} capturada".format(len(muestras))
                quieto_desde = None
                # El diagnóstico se recalcula al agregar una muestra y no en cada
                # cuadro: entre muestra y muestra no cambia nada, y así el bucle
                # de video no carga con un ajuste que daría siempre lo mismo.
                diagnostico = diagnostico_en_vivo(muestras, cfg)
                if diagnostico is not None and diagnostico.nivel == "malo" and not aviso_dado:
                    aviso_dado = True
                    print("    ⚠️  El robot se está TRASLADANDO mientras gira: la nube mide "
                          "{:.0f} mm y\n        para este desfase tendría que medir {:.0f} mm. "
                          "Conviene parar (ESC) y\n        reintentar con las dos ruedas en "
                          "sentidos opuestos a la misma velocidad.".format(
                              diagnostico.nube_mm, diagnostico.diametro_mm))
        if len(muestras) >= m.muestras_objetivo and arco >= m.arco_recomendado_grados:
            return muestras


def medir_angular_declarado(fuente, cfg, id_rover, tipografia, ventana) -> tuple | None:
    """Desfase angular alineando el robot y declarando hacia dónde mira."""
    m = cfg.medicion_desfases
    alfas: list[float] = []

    print("\n  PASO 1 — desfase angular (método: alinear y declarar)")
    print("  Alineá las PALETAS del robot con una línea de la cuadrícula.")
    print("  Después indicá hacia dónde mira: 0=derecha  9=arriba  8=izquierda  2=abajo")
    print("  ENTER termina · ESC cancela\n")

    while True:
        cuadro = fuente.leer()
        if cuadro is None:
            time.sleep(0.01)
            continue
        lienzo = cuadro.imagen.copy()
        pose, detectados, sistema = _pose_del_rover(cuadro.imagen, cfg, id_rover)
        _dibujar_estado(lienzo, detectados, id_rover, [], sistema)

        media, dispersion = media_circular(alfas) if alfas else (0.0, 0.0)

        panel = Panel(tipografia)
        panel.titulo("Medición de desfases · orientación")
        panel.destacado("{} de {} orientaciones".format(len(alfas), m.orientaciones_objetivo),
                        VERDE if len(alfas) >= m.orientaciones_objetivo else BLANCO,
                        "desfase parcial: {:+.2f}°".format(media) if alfas else "")
        panel.separador()
        if pose is None:
            panel.estado("Marcador", "no se ve", ROJO)
        else:
            panel.estado("Marcador", "{:.2f}°".format(pose.theta_grados), VERDE)
        if alfas:
            panel.estado("Dispersión", "{:.2f}°".format(dispersion),
                         VERDE if dispersion < 3.0 else AMBAR)
        panel.separador()
        panel.datos("Alineá las PALETAS con una línea de la cuadrícula")
        panel.datos("0 = derecha   9 = arriba   8 = izquierda   2 = abajo", GRIS)
        panel.pie("0/9/8/2 declarar · ENTER terminar · ESC cancelar")
        panel.dibujar(lienzo)

        cv2.imshow(ventana, lienzo)
        tecla = cv2.waitKey(1) & 0xFF

        if tecla == 27:
            return None
        if tecla in (13, 10):
            if alfas:
                return media_circular(alfas) + (len(alfas),)
        rumbos = {ord("0"): 0.0, ord("9"): 90.0, ord("8"): 180.0, ord("2"): 270.0}
        if tecla in rumbos and pose is not None:
            promedio = _promediar_cuadros(fuente, cfg, id_rover, m.cuadros_por_muestra)
            if promedio is not None:
                theta_real = rumbos[tecla]
                alfa = diferencia_angular(theta_real, promedio[2])
                alfas.append(alfa)
                print("    declarado {:.0f}°  ·  marcador {:.2f}°  ->  desfase {:+.2f}°".format(
                    theta_real, promedio[2], alfa))


def medir_angular_avance(fuente, cfg, id_rover, tipografia, ventana) -> tuple | None:
    """Desfase angular midiendo la DIRECCIÓN EN QUE AVANZA el robot.

    Más preciso que alinear a ojo: para un robot diferencial, la dirección en la
    que se desplaza cuando va derecho **es** su frente, y esa dirección la mide
    la visión con su propia precisión en vez de la del ojo de quien alinea.

    Se captura una pose antes y otra después de un avance recto; el rumbo real
    es el ángulo del desplazamiento, y el desfase es su diferencia con la
    orientación del marcador.
    """
    m = cfg.medicion_desfases
    alfas: list[float] = []
    inicio = None

    print("\n  PASO 1 — desfase angular (método: avance recto)")
    print("  Poné el robot quieto, marcá el inicio, mandalo DERECHO unos 20 cm,")
    print("  frenalo y marcá el fin. Repetí en varias direcciones distintas.")
    print("  ESPACIO marca inicio/fin · ENTER termina · ESC cancela\n")

    while True:
        cuadro = fuente.leer()
        if cuadro is None:
            time.sleep(0.01)
            continue
        lienzo = cuadro.imagen.copy()
        pose, detectados, sistema = _pose_del_rover(cuadro.imagen, cfg, id_rover)
        _dibujar_estado(lienzo, detectados, id_rover, [], sistema)

        media, dispersion = media_circular(alfas) if alfas else (0.0, 0.0)

        panel = Panel(tipografia)
        panel.titulo("Medición de desfases · orientación por avance")
        panel.destacado("{} de {} avances".format(len(alfas), m.orientaciones_objetivo),
                        VERDE if len(alfas) >= m.orientaciones_objetivo else BLANCO,
                        "desfase parcial: {:+.2f}°".format(media) if alfas else "")
        panel.separador()
        panel.estado("Marcador", "no se ve" if pose is None else "{:.2f}°".format(pose.theta_grados),
                     ROJO if pose is None else VERDE)
        panel.estado("Estado", "esperando el FIN del avance" if inicio else "esperando el INICIO",
                     AMBAR if inicio else BLANCO)
        if alfas:
            panel.estado("Dispersión", "{:.2f}°".format(dispersion),
                         VERDE if dispersion < 3.0 else AMBAR)
        panel.separador()
        panel.datos("Mandá el robot DERECHO, al menos 10 cm")
        panel.datos("Cuanto más largo el avance, más preciso el rumbo", GRIS)
        panel.pie("ESPACIO marcar · ENTER terminar · ESC cancelar")
        panel.dibujar(lienzo)

        cv2.imshow(ventana, lienzo)
        tecla = cv2.waitKey(1) & 0xFF

        if tecla == 27:
            return None
        if tecla in (13, 10) and alfas:
            return media_circular(alfas) + (len(alfas),)
        if tecla == 32 and pose is not None:
            promedio = _promediar_cuadros(fuente, cfg, id_rover, m.cuadros_por_muestra)
            if promedio is None:
                continue
            if inicio is None:
                inicio = promedio
                print("    inicio en celda ({:.2f}, {:.2f})".format(inicio[0], inicio[1]))
                continue

            d_col = promedio[0] - inicio[0]
            d_row = promedio[1] - inicio[1]
            recorrido_mm = math.hypot(d_col, d_row) * cfg.tablero.cell_mm
            if recorrido_mm < 100.0:
                print("    avance de solo {:.0f} mm: muy corto, el rumbo sale impreciso. "
                      "Repetí desde el inicio.".format(recorrido_mm))
                inicio = None
                continue
            # El menos en la fila es la conversión de siempre: row crece hacia
            # abajo y theta se mide antihorario.
            rumbo = normalizar_grados(math.degrees(math.atan2(-d_row, d_col)))
            # Se usa la orientación del marcador en el punto de partida: es la
            # que corresponde al momento en que el robot empezó a avanzar.
            alfa = diferencia_angular(rumbo, inicio[2])
            alfas.append(alfa)
            print("    avance de {:.0f} mm  ·  rumbo {:.2f}°  ·  marcador {:.2f}°  "
                  "->  desfase {:+.2f}°".format(recorrido_mm, rumbo, inicio[2], alfa))
            inicio = None


# --------------------------------------------------------------------------
# Programa
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mide los desfases marcador-robot usando el propio sistema de visión."
    )
    parser.add_argument("--config", default=None, help="archivo de configuración")
    parser.add_argument("--autoprueba", action="store_true",
                        help="verifica la matemática contra un desfase conocido, sin cámara")
    parser.add_argument("--rover", type=int, default=10, help="ID del marcador del robot")
    parser.add_argument("--indice", type=int, default=None, help="índice de cámara")
    parser.add_argument("--camara", default=None, help="nombre del perfil de calibración")
    parser.add_argument("--altura-camara-mm", type=float, default=2100.0,
                        help="altura de la cámara sobre el tablero, para el paralaje")
    parser.add_argument("--metodo-angular", choices=("declarado", "avance"), default="declarado",
                        help="cómo medir el desfase angular")
    parser.add_argument("--desfase-angular", type=float, default=None,
                        help="usar este desfase angular en vez de medirlo")
    parser.add_argument("--solo-angular", action="store_true")
    parser.add_argument("--solo-posicion", action="store_true")
    args = parser.parse_args(argv)

    cfg = cargar_config(args.config) if args.config else cargar_config()

    if args.autoprueba:
        ok_media = autoprueba_media_circular()
        ok_cenital = autoprueba(cfg, con_perspectiva=False)
        ok_persp = autoprueba(cfg, con_perspectiva=True)
        print("=" * 78)
        todo = ok_media and ok_cenital and ok_persp
        print("AUTOPRUEBA: {}".format("TODO OK" if todo else "HAY FALLAS"))
        print("=" * 78)
        return 0 if todo else 1

    if args.solo_posicion and args.desfase_angular is None:
        print("ERROR: --solo-posicion necesita --desfase-angular, porque el desfase de\n"
              "       posición se expresa en el marco del ROBOT y para eso hace falta\n"
              "       saber cuánto difiere del marco del marcador.", file=sys.stderr)
        return 2

    try:
        camara = FuenteCamara(cfg.camara, indice=args.indice)
    except ErrorCamara as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        return 2

    with camara:
        primero = None
        limite = time.monotonic() + 10.0
        while primero is None and time.monotonic() < limite:
            primero = camara.leer()
            time.sleep(0.01)
        if primero is None:
            print("ERROR: la cámara no entregó imágenes.", file=sys.stderr)
            return 2
        alto, ancho = primero.imagen.shape[:2]

        interactivo = bool(sys.stdin and sys.stdin.isatty())
        try:
            perfil = elegir_perfil(cfg.calibracion, BASE_VISION, ancho, alto,
                                   nombre=args.camara, interactivo=interactivo)
        except ErrorCalibracion as exc:
            print("\nERROR: {}".format(exc), file=sys.stderr)
            return 2
        print(comparar_con_camara(perfil, ancho, alto).mensaje())

        fuente = FuenteRectificada(
            camara, Rectificador(perfil, alpha=cfg.calibracion.alpha, tamano=(ancho, alto))
        )
        tipografia = Tipografia(escala_para(alto))
        ventana = "Medicion de desfases"

        try:
            desfase_angular = args.desfase_angular
            dispersion_ang, n_orientaciones = 0.0, 0
            if not args.solo_posicion and desfase_angular is None:
                medidor = (medir_angular_avance if args.metodo_angular == "avance"
                           else medir_angular_declarado)
                resultado = medidor(fuente, cfg, args.rover, tipografia, ventana)
                if resultado is None:
                    print("\nCancelado.")
                    return 1
                desfase_angular, dispersion_ang, n_orientaciones = resultado
            if desfase_angular is None:
                desfase_angular = 0.0

            if args.solo_angular:
                print("\n  Desfase angular medido: {:+.2f}°  "
                      "(dispersión {:.2f}° sobre {} orientaciones)".format(
                          desfase_angular, dispersion_ang, n_orientaciones))
                print('\n      "desfase_angular_grados": {:.2f}'.format(desfase_angular))
                print("\n  NO se aplicó nada.\n")
                return 0

            muestras = medir_posicion(fuente, cfg, args.rover, tipografia, ventana)
            if muestras is None:
                print("\nCancelado.")
                return 1
        finally:
            cv2.destroyAllWindows()

    try:
        ajuste = ajustar_giro(muestras)
    except ValueError as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        return 2

    datos = informar(ajuste, desfase_angular, dispersion_ang, n_orientaciones,
                     cfg, args.altura_camara_mm)
    marca = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    carpeta = os.path.join(BASE_VISION, cfg.medicion_desfases.carpeta_mediciones)
    guardar_sesion(datos, muestras, cfg,
                   os.path.join(carpeta, "desfases_rover{}_{}.json".format(args.rover, marca)))
    return 0 if datos["veredicto"] != "INSUFICIENTE" else 1


if __name__ == "__main__":
    sys.exit(main())
