"""Carga de la configuración del sistema de visión.

Todo umbral, tamaño, ID y disposición vive en `config_vision.json`, no en el
código (ver CLAUDE.md, sección 6). Este módulo traduce ese archivo a estructuras
inmutables, para que el resto del sistema no ande leyendo diccionarios sueltos
ni pueda modificar la configuración por accidente a mitad de una ronda.

Las claves que empiezan con `_` son notas para quien edita el JSON —que no
admite comentarios— y se ignoran solas, porque acá se leen las claves por nombre
en vez de barrer el diccionario.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import cv2

CONFIG_POR_DEFECTO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_vision.json")

#: Nombres de esquina admitidos y su celda, en función del tamaño de la grilla.
#: Se usan nombres en vez de números para que la disposición no se rompa al
#: cambiar `cols`/`rows` cuando se mida la cancha real.
_ESQUINAS = {
    "origen": lambda cols, rows: (0.0, 0.0),
    "fin_col": lambda cols, rows: (float(cols), 0.0),
    "diagonal": lambda cols, rows: (float(cols), float(rows)),
    "fin_row": lambda cols, rows: (0.0, float(rows)),
}


@dataclass(frozen=True, slots=True)
class Tablero:
    """Dimensiones de la cancha, en celdas.

    La cancha efectiva es el área entre los CENTROS de los cuatro marcadores de
    esquina, no el tablero físico. Por eso estos valores son "a confirmar" hasta
    que la cancha esté montada y medida.
    """

    cols: int
    rows: int
    cell_mm: float


@dataclass(frozen=True, slots=True)
class MarcadoresEsquina:
    """Los cuatro marcadores que anclan el sistema de coordenadas.

    `disposicion` mapea ID de marcador -> celda donde está su centro. El ID 0
    es el origen (0,0) y coincide con la esquina de salida de los robots
    (CLAUDE.md, sección 5). El orden de los otros tres es horario y es una
    REGLA DE MONTAJE FÍSICO: si se pegan en otro orden, todas las coordenadas
    salen rotadas o espejadas.

    `lado_mm` y `borde_blanco_mm` son la medida del marcador FÍSICO impreso. No
    entran en el cálculo de coordenadas —eso lo define el centro de cada
    marcador, que no depende de su tamaño—: dicen qué hay que imprimir y desde
    qué distancia se lo puede detectar de forma estable.
    """

    nombre_diccionario: str
    disposicion: dict[int, tuple[float, float]]
    lado_mm: float
    borde_blanco_mm: float

    @property
    def ids_esperados(self) -> frozenset[int]:
        return frozenset(self.disposicion)


@dataclass(frozen=True, slots=True)
class Cubos:
    """Medidas físicas de los cubos. CONFIRMADAS.

    Los va a consumir la detección de color (`detectors/`), que todavía no
    existe: `lado_mm` dice qué tamaño de mancha es plausible, y `colores` en qué
    clases hay que clasificar. El color es la identidad del cubo en el contrato
    —no hay dos del mismo—, y el amarillo está reservado para los obstáculos.

    La altura del cubo no es un campo aparte: es su lado, porque es un cubo.
    """

    lado_mm: float
    colores: tuple[str, ...]

    @property
    def altura_mm(self) -> float:
        """La altura que va a descontar la corrección de paralaje."""
        return self.lado_mm


@dataclass(frozen=True, slots=True)
class MarcadorRover:
    """Marcador ArUco pegado al robot. ⚠️ TAMAÑO PROVISIONAL.

    `lado_mm` y `borde_blanco_mm` son una **propuesta sin verificar**: 40 + 5 + 5
    suman los 50 mm del lado corto del espacio disponible en el robot, así que
    entra justo. Falta comprobar que un marcador de 40 mm se detecte de forma
    **estable** desde la Logitech C270 a 2,1 m de altura, y esa prueba se hará
    cuando la cámara esté montada a su altura de trabajo.

    Si no alcanza, el lado largo del espacio (70 mm) admite 60 mm de negro con
    sus 5 mm de blanco por lado.

    La **altura** a la que va montado no está acá sino en `Paralaje`, que es la
    etapa que la consume.
    """

    lado_mm: float
    borde_blanco_mm: float
    espacio_ancho_mm: float
    espacio_alto_mm: float

    @property
    def lado_con_blanco_mm(self) -> float:
        """Lo que ocupa el marcador impreso, blanco incluido."""
        return self.lado_mm + 2 * self.borde_blanco_mm


@dataclass(frozen=True, slots=True)
class Elementos:
    """Medidas físicas reales de los objetos del reto.

    Se registran antes de que exista quien las use, a propósito: son medidas del
    mundo, no parámetros de un algoritmo, y no cambian porque cambie el código.
    Cada una lleva en el JSON su estado —confirmada o provisional—, porque una
    medida provisional usada como confirmada no da error: da resultados mal en
    silencio.
    """

    cubos: Cubos
    marcador_rover: MarcadorRover


@dataclass(frozen=True, slots=True)
class DesfaseMarcadorRobot:
    """Vector del centro del MARCADOR al centro de rotación del ROBOT.

    Va en el marco del robot —adelante y a la izquierda— y no en coordenadas de
    la cancha, porque el desfase es solidario al robot y el robot gira: un
    `(col, row)` fijo solo sería correcto para una orientación.

    `adelante` positivo apunta hacia las paletas; `izquierda` positiva, hacia la
    izquierda del robot.
    """

    adelante_mm: float
    izquierda_mm: float

    @property
    def es_nulo(self) -> bool:
        """Si los dos son cero, la pose del robot es la del marcador."""
        return self.adelante_mm == 0.0 and self.izquierda_mm == 0.0


@dataclass(frozen=True, slots=True)
class Seguimiento:
    """Memoria entre cuadros: la última observación buena y la edad.

    Acá **no hay problema de asociación**, que es el problema difícil de todo
    seguimiento. Cada objeto de este reto trae su propia identidad —el rover en
    el ID de su marcador, el cubo en su color— así que no hay que adivinar qué
    detección de este cuadro corresponde a cuál del anterior: viene escrito.

    `edad_maxima_ms` no es para oclusiones —para eso está la edad, y el contrato
    promete que un objeto tapado no desaparece— sino para barrer **fantasmas**:
    detecciones espurias que nunca se repiten, u objetos que de verdad se fueron.
    """

    edad_maxima_ms: int
    refrescar_con_cubos_no_confiables: bool


@dataclass(frozen=True, slots=True)
class Publicacion:
    """Reloj y puerto de la publicación de telemetría.

    El transporte no está acá: vive en `contrato/publicador.py`, compartido con
    el simulador. Esto es solo lo propio de este lado.

    El reloj es **propio y no el de la cámara**: son dos relojes que no deben
    esperarse. Si un cuadro tarda de más, la publicación no se frena; si un
    cliente tiene la red lenta, el procesamiento ni se entera.
    """

    puerto: int
    hz: float


@dataclass(frozen=True, slots=True)
class Deposito:
    """Una zona de acopio: dónde está y de qué color."""

    color: str
    col: float
    row: float


@dataclass(frozen=True, slots=True)
class Lugares:
    """Los lugares fijos de la cancha: la salida y las tres zonas de acopio.

    **Se declaran, no se detectan.** Están siempre, no se mueven y no envejecen,
    así que buscarlos en cada cuadro sería trabajo perdido y una fuente de ruido
    donde no hace falta. Por eso viajan en el mensaje en listas separadas de los
    cubos, aunque compartan el color.

    El contrato los exige en **cada** mensaje: sin ellos el sistema de visión
    sabría dónde está cada objeto y no sabría adónde hay que llevarlo.
    """

    start_col: float
    start_row: float
    depositos: tuple[Deposito, ...]


@dataclass(frozen=True, slots=True)
class DeteccionRovers:
    """Cómo se pasa de marcadores detectados a rovers.

    Qué marcador es un rover no está declarado como lista: **es rover todo el
    que no sea una esquina**. Una lista de IDs de rover habría que mantenerla
    sincronizada con los marcadores que se peguen de verdad, y el día que no lo
    esté, un rover deja de existir sin que nada avise.

    Los desfases arrancan en cero, que hace que la pose del robot sea idéntica a
    la del marcador. No es que el robot real no tenga desfase —lo tiene—: es que
    todavía no se midió. Se van a medir con el propio sistema haciendo girar el
    robot en el lugar; el procedimiento está en las notas de `config_vision.json`.
    """

    ids_ignorados: frozenset[int]
    desfase_posicion: DesfaseMarcadorRobot
    desfase_angular_grados: float


@dataclass(frozen=True, slots=True)
class MedicionDesfases:
    """Parámetros de la herramienta que mide los desfases marcador ↔ robot.

    Mide y muestra; **no aplica**. Los valores medidos los revisa una persona y
    los pone en `deteccion_rovers`, porque un número que va a corregir todas las
    posiciones publicadas no se escribe solo.

    El parámetro que decide si la medición sirve es `arco_minimo_grados`:
    separar el centro de giro del desfase es un problema mal condicionado cuando
    el robot gira poco, y el error se amplifica por `1/(1−cos(arco/2))`.
    """

    muestras_objetivo: int
    muestras_minimas: int
    paso_angular_grados: float
    arco_minimo_grados: float
    arco_recomendado_grados: float
    arco_inaceptable_grados: float
    cuadros_por_muestra: int
    estabilidad_celdas: float
    pausa_s: float
    orientaciones_objetivo: int
    radio_minimo_mm: float
    residuo_bueno_mm: float
    residuo_aceptable_mm: float
    acuerdo_metodos_mm: float
    carpeta_mediciones: str


@dataclass(frozen=True, slots=True)
class DeteccionCubos:
    """Cómo se encuentran los cubos por su color.

    Se segmenta por **croma** en Lab —el tablero es acromático, así que todo lo
    saturado es objeto— y se clasifica por **matiz**, que es casi invariante a
    la iluminación: un cubo rojo a la sombra sigue teniendo matiz de rojo.

    El amarillo está entre los matices de referencia aunque esta edición no
    tenga obstáculos, y **no es un cubo**: es una clase de exclusión. Verde y
    amarillo están a solo 33° —el par más ajustado—, así que sin ella cualquier
    objeto amarillo suelto se leería como cubo verde.
    """

    croma_minimo: float
    matices_grados: dict[str, float]
    matiz_tolerancia_grados: float
    area_minima_relativa: float
    area_maxima_relativa: float
    recorte_robusto: float
    residuo_maximo_celdas: float
    pasos_refinamiento: int


@dataclass(frozen=True, slots=True)
class Paralaje:
    """Alturas para la corrección de paralaje. ETAPA TODAVÍA NO CONSTRUIDA.

    Un objeto con altura no se ve donde está: se ve corrido hacia afuera,
    alejándose del punto que está justo debajo de la cámara, tanto más cuanto
    más alto y más lejos del centro. El tablero y los marcadores de esquina
    están al ras y no sufren el efecto; los rovers y los cubos sí.

    Acá vive **solo** la altura del marcador del rover, que es la única que no
    se deduce de ninguna otra medida. La del cubo es su lado (`Cubos.altura_mm`)
    y la de la cámara **no se configura**: sale de la pose deducida de los
    cuatro marcadores de esquina.

    No confundir con `Precision.altura_marcador_mm`, que es el espesor del papel
    del marcador de prueba y sirve para descontar el paralaje de esa medición.
    """

    altura_marcador_rover_mm: float


@dataclass(frozen=True, slots=True)
class Perspectiva:
    """Inclinación FÍSICA de la cámara sintética, en grados.

    Es el ángulo entre el eje óptico y la vertical. La cámara se corre de lado y
    sigue apuntando al centro del tablero, que es lo que pasa cuando un soporte
    real no quedó perfectamente a plomo.
    """

    activa: bool
    inclinacion_grados: float


@dataclass(frozen=True, slots=True)
class CuerpoRover:
    """Tamaño del chasis, SOLO para dibujarlo en la imagen sintética.

    ⚠️ Medidas provisionales, no medidas sobre el robot real. No entran en
    ningún número que el sistema publique: existen porque sin un cuerpo que
    tape, no se puede verificar el caso más importante del juego —el rover
    empujando un cubo y ocultándole la arista de la base—.
    """

    ancho_mm: float
    largo_mm: float
    alto_mm: float
    gris: int


@dataclass(frozen=True, slots=True)
class CuboDemo:
    """Un cubo de ejemplo para las imágenes de prueba.

    `theta` es su rotación sobre el piso. No se publica —el contrato no lleva
    orientación de cubo— pero cambia la forma de la silueta, y el detector tiene
    que dar igual con cualquier rotación.
    """

    color: str
    col: float
    row: float
    theta: float


@dataclass(frozen=True, slots=True)
class Sintetico:
    """Parámetros del generador de imágenes de prueba."""

    ancho_px: int
    alto_px: int
    margen_px: int
    altura_camara_mm: float
    lado_marcador_esquina_celdas: float
    lado_marcador_rover_celdas: float
    borde_blanco_celdas: float
    colores_cubo_bgr: dict[str, tuple[int, int, int]]
    brillo_tapa: float
    brillo_lateral: float
    cuerpo_rover: CuerpoRover
    color_fondo: int
    color_grilla: int
    dibujar_grilla: bool
    paso_grilla_celdas: int
    desenfoque_px: int
    ruido_sigma: float
    perspectiva: Perspectiva


@dataclass(frozen=True, slots=True)
class RoverDemo:
    """Un rover de ejemplo para las imágenes de prueba.

    `theta` sigue la convención del contrato: grados, 0 = derecha, antihorario.
    """

    id: int
    col: float
    row: float
    theta: float


@dataclass(frozen=True, slots=True)
class Ajuste:
    """Un control de cámara que queremos fijar en manual.

    `prueba_a` y `prueba_b` son dos valores deliberadamente distintos que se usan
    para verificar **por efecto**: si la imagen no cambia entre uno y otro, la
    cámara ignoró el ajuste aunque haya dicho que lo aceptaba. Ese chequeo es el
    único que responde de verdad si se puede fijar la exposición.
    """

    fijar: bool
    valor: float
    prueba_a: float
    prueba_b: float


@dataclass(frozen=True, slots=True)
class UmbralesEfecto:
    """Cuánto tiene que cambiar la imagen para dar un ajuste por confirmado."""

    brillo_min: float
    nitidez_rel_min: float
    color_rel_min: float


@dataclass(frozen=True, slots=True)
class Camara:
    """Parámetros de la webcam USB real."""

    indice: int | str
    backend: str
    ancho: int
    alto: int
    fps: float
    fourcc: str | None
    buffersize: int
    cuadros_calentamiento: int
    segundos_arranque: float
    exposicion: Ajuste
    enfoque: Ajuste
    balance_blancos: Ajuste
    valor_manual_autoexposicion: float | None
    umbrales: UmbralesEfecto


@dataclass(frozen=True, slots=True)
class Calibracion:
    """Calibración intrínseca del lente: el patrón, las exigencias y los umbrales.

    Es una capa PREVIA a todo lo demás: se corrige la imagen y recién después se
    detectan marcadores y se calcula la geometría de esquinas.
    """

    columnas_internas: int
    filas_internas: int
    lado_mm: float
    papel: str
    vistas_minimas: int
    vistas_objetivo: int
    modelo: str
    alpha: float
    carpeta_perfiles: str
    perfil_por_defecto: str | None
    excelente_px: float
    bueno_px: float
    aceptable_px: float
    estabilidad_px: float
    inclinacion_min: float
    pausa_s: float

    @property
    def tamano_patron(self) -> tuple[int, int]:
        """Como lo espera OpenCV: (columnas, filas) de esquinas internas."""
        return (self.columnas_internas, self.filas_internas)

    def carpeta(self, base: str) -> str:
        """Carpeta absoluta donde viven los perfiles, resuelta contra `vision/`."""
        return (self.carpeta_perfiles if os.path.isabs(self.carpeta_perfiles)
                else os.path.join(base, self.carpeta_perfiles))

    def ruta_de(self, nombre_archivo: str, base: str) -> str:
        """Ruta del perfil de una cámara, a partir del nombre de su archivo."""
        return os.path.join(self.carpeta(base), nombre_archivo + ".json")


@dataclass(frozen=True, slots=True)
class Precision:
    """Prueba de precisión de ubicación sobre hardware real.

    Mide un DESPLAZAMIENTO conocido —contando cuadros de la cuadrícula, que es
    exacto— en vez de una posición absoluta. Eso evita tener que ubicar el
    origen con precisión y neutraliza el paralaje, que sobre una resta queda
    como un error de escala puro y por lo tanto descontable.
    """

    umbral_mm: float
    id_marcador_prueba: int
    lado_marcador_mm: float
    cuadros_por_medicion: int
    muestras_por_punto: int
    margen_marcadores_celdas: float
    altura_camara_mm: float
    altura_marcador_mm: float
    zonas: tuple[dict[str, Any], ...]
    carpeta_mediciones: str


@dataclass(frozen=True, slots=True)
class ConfigVision:
    tablero: Tablero
    marcadores_esquina: MarcadoresEsquina
    elementos: Elementos
    lugares: Lugares
    seguimiento: Seguimiento
    publicacion: Publicacion
    deteccion_rovers: DeteccionRovers
    deteccion_cubos: DeteccionCubos
    medicion_desfases: MedicionDesfases
    paralaje: Paralaje
    sintetico: Sintetico
    camara: Camara
    calibracion: Calibracion
    precision: Precision
    rovers_demo: tuple[RoverDemo, ...]
    cubos_demo: tuple[CuboDemo, ...]


def diccionario_aruco(nombre: str):
    """Resuelve el nombre del diccionario ArUco a su objeto de OpenCV.

    Se guarda el NOMBRE en la configuración, no la constante numérica: el número
    no le dice nada a quien edita el archivo, y el nombre además documenta qué
    hay que imprimir para la cancha.
    """
    constante = getattr(cv2.aruco, nombre, None)
    if constante is None:
        raise ValueError(
            "diccionario ArUco desconocido: {!r} (por ejemplo, 'DICT_4X4_50')".format(nombre)
        )
    return cv2.aruco.getPredefinedDictionary(constante)


def _leer_disposicion(bruto: dict[str, Any], cols: int, rows: int) -> dict[int, tuple[float, float]]:
    """Traduce {'0': 'origen', ...} a {0: (0.0, 0.0), ...}."""
    salida: dict[int, tuple[float, float]] = {}
    for id_texto, nombre in bruto.items():
        if nombre not in _ESQUINAS:
            raise ValueError(
                "esquina desconocida {!r} para el marcador {}; válidas: {}".format(
                    nombre, id_texto, sorted(_ESQUINAS)
                )
            )
        salida[int(id_texto)] = _ESQUINAS[nombre](cols, rows)
    return salida


def _leer_elementos(d: dict[str, Any]) -> Elementos:
    """Lee las medidas físicas de los objetos del reto.

    Los estados —confirmado o provisional— viven en las notas del JSON y no como
    campos: son para quien edita el archivo o escribe la etapa que las va a usar,
    no algo sobre lo que el código deba ramificar. Un `if provisional` sería una
    decisión tomada en el lugar equivocado.
    """
    c = d["cubos"]
    r = d["marcador_rover"]
    espacio = r["espacio_disponible_mm"]
    return Elementos(
        cubos=Cubos(
            lado_mm=float(c["lado_mm"]),
            colores=tuple(str(color) for color in c["colores"]),
        ),
        marcador_rover=MarcadorRover(
            lado_mm=float(r["lado_mm"]),
            borde_blanco_mm=float(r["borde_blanco_mm"]),
            espacio_ancho_mm=float(espacio["ancho"]),
            espacio_alto_mm=float(espacio["alto"]),
        ),
    )


def _leer_ajuste(d: dict[str, Any]) -> Ajuste:
    return Ajuste(
        fijar=bool(d["fijar"]),
        valor=float(d["valor"]),
        prueba_a=float(d["prueba_a"]),
        prueba_b=float(d["prueba_b"]),
    )


def _leer_camara(d: dict[str, Any]) -> Camara:
    a = d["ajustes"]
    u = d["umbrales_efecto"]
    return Camara(
        indice=(d["indice"] if isinstance(d["indice"], str) else int(d["indice"])),
        backend=str(d["backend"]).lower(),
        ancho=int(d["ancho"]),
        alto=int(d["alto"]),
        fps=float(d["fps"]),
        fourcc=d["fourcc"],
        buffersize=int(d["buffersize"]),
        cuadros_calentamiento=int(d["cuadros_calentamiento"]),
        segundos_arranque=float(d.get("segundos_arranque", 6.0)),
        exposicion=_leer_ajuste(a["exposicion"]),
        enfoque=_leer_ajuste(a["enfoque"]),
        balance_blancos=_leer_ajuste(a["balance_blancos"]),
        valor_manual_autoexposicion=a.get("valor_manual_autoexposicion"),
        umbrales=UmbralesEfecto(
            brillo_min=float(u["brillo_min"]),
            nitidez_rel_min=float(u["nitidez_rel_min"]),
            color_rel_min=float(u["color_rel_min"]),
        ),
    )


def _leer_calibracion(d: dict[str, Any]) -> Calibracion:
    p = d["patron"]
    u = d["umbrales"]
    return Calibracion(
        columnas_internas=int(p["columnas_internas"]),
        filas_internas=int(p["filas_internas"]),
        lado_mm=float(p["lado_mm"]),
        papel=str(d["papel"]).lower(),
        vistas_minimas=int(d["vistas_minimas"]),
        vistas_objetivo=int(d["vistas_objetivo"]),
        modelo=str(d["modelo"]).lower(),
        alpha=float(d["alpha"]),
        carpeta_perfiles=str(d["carpeta_perfiles"]),
        perfil_por_defecto=d.get("perfil_por_defecto") or None,
        excelente_px=float(u["excelente_px"]),
        bueno_px=float(u["bueno_px"]),
        aceptable_px=float(u["aceptable_px"]),
        estabilidad_px=float(u["estabilidad_px"]),
        inclinacion_min=float(u["inclinacion_min"]),
        pausa_s=float(u["pausa_s"]),
    )


def _leer_precision(d: dict[str, Any]) -> Precision:
    return Precision(
        umbral_mm=float(d["umbral_mm"]),
        id_marcador_prueba=int(d["id_marcador_prueba"]),
        lado_marcador_mm=float(d["lado_marcador_mm"]),
        cuadros_por_medicion=int(d["cuadros_por_medicion"]),
        muestras_por_punto=int(d["muestras_por_punto"]),
        margen_marcadores_celdas=float(d["margen_marcadores_celdas"]),
        altura_camara_mm=float(d["altura_camara_mm"]),
        altura_marcador_mm=float(d["altura_marcador_mm"]),
        zonas=tuple(d["zonas"]),
        carpeta_mediciones=str(d["carpeta_mediciones"]),
    )


def cargar_config(ruta: str = CONFIG_POR_DEFECTO) -> ConfigVision:
    """Lee y valida el archivo de configuración."""
    with open(ruta, "r", encoding="utf-8") as f:
        d = json.load(f)

    t = d["tablero"]
    tablero = Tablero(cols=int(t["cols"]), rows=int(t["rows"]), cell_mm=float(t["cell_mm"]))

    m = d["marcadores_esquina"]
    marcadores = MarcadoresEsquina(
        nombre_diccionario=m["diccionario"],
        disposicion=_leer_disposicion(m["disposicion"], tablero.cols, tablero.rows),
        lado_mm=float(m["lado_mm"]),
        borde_blanco_mm=float(m["borde_blanco_mm"]),
    )

    elementos = _leer_elementos(d["elementos"])

    sg = d["seguimiento"]
    seguimiento = Seguimiento(
        edad_maxima_ms=int(sg["edad_maxima_ms"]),
        refrescar_con_cubos_no_confiables=bool(sg["refrescar_con_cubos_no_confiables"]),
    )

    pu = d["publicacion"]
    publicacion = Publicacion(puerto=int(pu["puerto"]), hz=float(pu["hz"]))

    lu = d["lugares"]
    lugares = Lugares(
        start_col=float(lu["start"]["col"]),
        start_row=float(lu["start"]["row"]),
        depositos=tuple(
            Deposito(color=str(x["color"]), col=float(x["col"]), row=float(x["row"]))
            for x in lu["depots"]
        ),
    )

    dr = d["deteccion_rovers"]
    desf = dr["desfase_marcador_a_centro_mm"]
    deteccion_rovers = DeteccionRovers(
        ids_ignorados=frozenset(int(i) for i in dr["ids_ignorados"]),
        desfase_posicion=DesfaseMarcadorRobot(
            adelante_mm=float(desf["adelante"]),
            izquierda_mm=float(desf["izquierda"]),
        ),
        desfase_angular_grados=float(dr["desfase_angular_grados"]),
    )

    dc = d["deteccion_cubos"]
    deteccion_cubos = DeteccionCubos(
        croma_minimo=float(dc["croma_minimo"]),
        matices_grados={k: float(v) for k, v in dc["matices_lab_grados"].items()},
        matiz_tolerancia_grados=float(dc["matiz_tolerancia_grados"]),
        area_minima_relativa=float(dc["area_minima_relativa"]),
        area_maxima_relativa=float(dc["area_maxima_relativa"]),
        recorte_robusto=float(dc["recorte_robusto"]),
        residuo_maximo_celdas=float(dc["residuo_maximo_celdas"]),
        pasos_refinamiento=int(dc["pasos_refinamiento"]),
    )

    md = d["medicion_desfases"]
    medicion_desfases = MedicionDesfases(
        muestras_objetivo=int(md["muestras_objetivo"]),
        muestras_minimas=int(md["muestras_minimas"]),
        paso_angular_grados=float(md["paso_angular_grados"]),
        arco_minimo_grados=float(md["arco_minimo_grados"]),
        arco_recomendado_grados=float(md["arco_recomendado_grados"]),
        arco_inaceptable_grados=float(md["arco_inaceptable_grados"]),
        cuadros_por_muestra=int(md["cuadros_por_muestra"]),
        estabilidad_celdas=float(md["estabilidad_celdas"]),
        pausa_s=float(md["pausa_s"]),
        orientaciones_objetivo=int(md["orientaciones_objetivo"]),
        radio_minimo_mm=float(md["radio_minimo_mm"]),
        residuo_bueno_mm=float(md["residuo_bueno_mm"]),
        residuo_aceptable_mm=float(md["residuo_aceptable_mm"]),
        acuerdo_metodos_mm=float(md["acuerdo_metodos_mm"]),
        carpeta_mediciones=str(md["carpeta_mediciones"]),
    )

    paralaje = Paralaje(
        altura_marcador_rover_mm=float(d["paralaje"]["altura_marcador_rover_mm"])
    )

    s = d["sintetico"]
    p = s["perspectiva"]
    sintetico = Sintetico(
        ancho_px=int(s["ancho_px"]),
        alto_px=int(s["alto_px"]),
        margen_px=int(s["margen_px"]),
        altura_camara_mm=float(s["altura_camara_mm"]),
        lado_marcador_esquina_celdas=float(s["lado_marcador_esquina_celdas"]),
        lado_marcador_rover_celdas=float(s["lado_marcador_rover_celdas"]),
        borde_blanco_celdas=float(s["borde_blanco_celdas"]),
        # Se guarda en BGR porque es lo que espera OpenCV; en el JSON va en RGB,
        # que es como la gente piensa un color.
        colores_cubo_bgr={
            nombre: (int(rgb[2]), int(rgb[1]), int(rgb[0]))
            for nombre, rgb in s["colores_cubo_rgb"].items()
        },
        brillo_tapa=float(s["brillo_tapa"]),
        brillo_lateral=float(s["brillo_lateral"]),
        cuerpo_rover=CuerpoRover(
            ancho_mm=float(s["cuerpo_rover"]["ancho_mm"]),
            largo_mm=float(s["cuerpo_rover"]["largo_mm"]),
            alto_mm=float(s["cuerpo_rover"]["alto_mm"]),
            gris=int(s["cuerpo_rover"]["gris"]),
        ),
        color_fondo=int(s["color_fondo"]),
        color_grilla=int(s["color_grilla"]),
        dibujar_grilla=bool(s["dibujar_grilla"]),
        paso_grilla_celdas=int(s["paso_grilla_celdas"]),
        desenfoque_px=int(s["desenfoque_px"]),
        ruido_sigma=float(s["ruido_sigma"]),
        perspectiva=Perspectiva(activa=bool(p["activa"]),
                                inclinacion_grados=float(p["inclinacion_grados"])),
    )

    camara = _leer_camara(d["camara"])
    calibracion = _leer_calibracion(d["calibracion"])
    precision = _leer_precision(d["precision"])

    rovers = tuple(
        RoverDemo(id=int(r["id"]), col=float(r["col"]), row=float(r["row"]), theta=float(r["theta"]))
        for r in d.get("rovers_demo", ())
    )

    cubos = tuple(
        CuboDemo(color=str(c["color"]), col=float(c["col"]), row=float(c["row"]),
                 theta=float(c.get("theta", 0.0)))
        for c in d.get("cubos_demo", ())
    )

    cfg = ConfigVision(
        tablero=tablero,
        marcadores_esquina=marcadores,
        elementos=elementos,
        lugares=lugares,
        seguimiento=seguimiento,
        publicacion=publicacion,
        deteccion_rovers=deteccion_rovers,
        deteccion_cubos=deteccion_cubos,
        medicion_desfases=medicion_desfases,
        paralaje=paralaje,
        sintetico=sintetico,
        camara=camara,
        calibracion=calibracion,
        precision=precision,
        rovers_demo=rovers,
        cubos_demo=cubos,
    )
    error = revisar_config(cfg)
    if error is not None:
        raise ValueError("config_vision.json: " + error)
    return cfg


def revisar_config(cfg: ConfigVision) -> str | None:
    """Revisa que la configuración sea coherente antes de usarla.

    Vale la pena fallar acá con un mensaje claro: una configuración incoherente
    produce imágenes o coordenadas silenciosamente mal, que es mucho más caro de
    diagnosticar que un error al arrancar.
    """
    if cfg.tablero.cols <= 0 or cfg.tablero.rows <= 0:
        return "cols y rows deben ser > 0"
    if cfg.tablero.cell_mm <= 0:
        return "cell_mm debe ser > 0"
    if cfg.marcadores_esquina.ids_esperados != frozenset((0, 1, 2, 3)):
        return "se esperan exactamente los marcadores de esquina 0, 1, 2 y 3; hay {}".format(
            sorted(cfg.marcadores_esquina.ids_esperados)
        )
    if len(set(cfg.marcadores_esquina.disposicion.values())) != 4:
        return "hay dos marcadores de esquina asignados a la misma esquina"
    if cfg.marcadores_esquina.lado_mm <= 0:
        return "marcadores_esquina.lado_mm debe ser > 0 (es el tamaño del marcador impreso)"
    if cfg.marcadores_esquina.borde_blanco_mm <= 0:
        return (
            "marcadores_esquina.borde_blanco_mm debe ser > 0: sin zona blanca alrededor "
            "el detector de ArUco no encuentra el marcador"
        )
    cub = cfg.elementos.cubos
    if cub.lado_mm <= 0:
        return "elementos.cubos.lado_mm debe ser > 0"
    if not cub.colores:
        return "elementos.cubos.colores: hace falta al menos un color"
    if len(set(cub.colores)) != len(cub.colores):
        return (
            "elementos.cubos.colores tiene colores repetidos: el color ES la identidad "
            "del cubo, así que no puede haber dos del mismo"
        )
    if "yellow" in cub.colores:
        return (
            "elementos.cubos.colores incluye 'yellow', que está RESERVADO para los "
            "obstáculos: un objeto amarillo nunca es un cubo"
        )
    mr = cfg.elementos.marcador_rover
    if mr.lado_mm <= 0 or mr.borde_blanco_mm <= 0:
        return "elementos.marcador_rover: lado_mm y borde_blanco_mm deben ser > 0"
    if mr.lado_con_blanco_mm > min(mr.espacio_ancho_mm, mr.espacio_alto_mm):
        return (
            "elementos.marcador_rover: el marcador con su borde blanco mide {:.0f} mm y no "
            "entra en el espacio disponible del robot ({:.0f} x {:.0f} mm). El borde blanco "
            "NO es opcional: sin él el marcador no se detecta".format(
                mr.lado_con_blanco_mm, mr.espacio_ancho_mm, mr.espacio_alto_mm
            )
        )
    dr = cfg.deteccion_rovers
    chocan_esquina = sorted(dr.ids_ignorados & cfg.marcadores_esquina.ids_esperados)
    if chocan_esquina:
        return (
            "deteccion_rovers.ids_ignorados contiene {}, que son marcadores de ESQUINA. "
            "Las esquinas ya quedan afuera de los rovers por definición; ponerlas acá "
            "sugiere una confusión sobre para qué sirve la lista".format(chocan_esquina)
        )
    if not (-360.0 <= dr.desfase_angular_grados <= 360.0):
        return (
            "deteccion_rovers.desfase_angular_grados = {} está fuera de [-360, 360]; "
            "es un ángulo, no una cantidad de vueltas".format(dr.desfase_angular_grados)
        )
    if cfg.seguimiento.edad_maxima_ms <= 0:
        return "seguimiento.edad_maxima_ms debe ser > 0"
    if not (0 < cfg.publicacion.puerto < 65536):
        return "publicacion.puerto fuera de rango"
    if cfg.publicacion.hz <= 0:
        return "publicacion.hz debe ser > 0"
    lug = cfg.lugares
    colores_cubo = set(cfg.elementos.cubos.colores)
    colores_deposito = [dep.color for dep in lug.depositos]
    if sorted(colores_deposito) != sorted(colores_cubo):
        return (
            "lugares.depots tiene los colores {} y los cubos son {}: cada cubo tiene que "
            "tener un depósito de SU color, y el contrato lo exige".format(
                sorted(colores_deposito), sorted(colores_cubo))
        )
    if len(set(colores_deposito)) != len(colores_deposito):
        return "lugares.depots: hay dos depósitos del mismo color"
    puntos = [("start", lug.start_col, lug.start_row)]
    puntos += [("depot " + dep.color, dep.col, dep.row) for dep in lug.depositos]
    for nombre, col, row in puntos:
        if not (0.0 <= col <= cfg.tablero.cols and 0.0 <= row <= cfg.tablero.rows):
            return (
                "lugares: {} está en ({}, {}), fuera de la cancha de {}x{} celdas".format(
                    nombre, col, row, cfg.tablero.cols, cfg.tablero.rows)
            )
    dc_cfg = cfg.deteccion_cubos
    faltan_matices = sorted(set(cfg.elementos.cubos.colores) - set(dc_cfg.matices_grados))
    if faltan_matices:
        return (
            "deteccion_cubos.matices_lab_grados no tiene matiz de referencia para {}: "
            "esos cubos no se podrían clasificar".format(faltan_matices)
        )
    if "yellow" not in dc_cfg.matices_grados:
        return (
            "deteccion_cubos.matices_lab_grados debe incluir 'yellow' como clase de "
            "EXCLUSIÓN: está a 33° del verde, y sin ella un objeto amarillo se leería "
            "como cubo verde"
        )
    if not (0.0 < dc_cfg.recorte_robusto <= 1.0):
        return "deteccion_cubos.recorte_robusto debe estar en (0, 1]"
    if dc_cfg.croma_minimo <= 0:
        return "deteccion_cubos.croma_minimo debe ser > 0"
    colores_dibujo = set(cfg.sintetico.colores_cubo_bgr)
    faltan_colores = sorted(set(cfg.elementos.cubos.colores) - colores_dibujo)
    if faltan_colores:
        return (
            "sintetico.colores_cubo_rgb no tiene con qué dibujar {}: el generador no "
            "podría producir imágenes de prueba de esos cubos".format(faltan_colores)
        )
    colores_validos = set(cfg.elementos.cubos.colores)
    for cubo in cfg.cubos_demo:
        if cubo.color not in colores_validos:
            return (
                "cubos_demo: el color {!r} no está en elementos.cubos.colores ({})".format(
                    cubo.color, sorted(colores_validos))
            )
    if len({c.color for c in cfg.cubos_demo}) != len(cfg.cubos_demo):
        return "cubos_demo: hay dos cubos del mismo color, y el color ES la identidad"
    m = cfg.medicion_desfases
    if m.muestras_minimas < 3:
        return (
            "medicion_desfases.muestras_minimas: con menos de 3 muestras el ajuste "
            "tiene tantas incógnitas como ecuaciones y no hay nada que promediar"
        )
    if m.muestras_objetivo < m.muestras_minimas:
        return "medicion_desfases.muestras_objetivo no puede ser menor que muestras_minimas"
    if not (0.0 < m.arco_inaceptable_grados <= m.arco_minimo_grados <= m.arco_recomendado_grados <= 360.0):
        return (
            "medicion_desfases: los arcos tienen que cumplir "
            "0 < inaceptable <= mínimo <= recomendado <= 360"
        )
    if m.paso_angular_grados <= 0:
        return "medicion_desfases.paso_angular_grados debe ser > 0"
    if m.orientaciones_objetivo < 1:
        return "medicion_desfases.orientaciones_objetivo debe ser >= 1"
    if cfg.paralaje.altura_marcador_rover_mm <= 0:
        return (
            "paralaje.altura_marcador_rover_mm debe ser > 0: es la altura del marcador "
            "sobre el tablero, y con 0 no habría paralaje que corregir"
        )
    ids_rover = [r.id for r in cfg.rovers_demo]
    if len(set(ids_rover)) != len(ids_rover):
        return "hay rovers de demostración con el mismo ID de marcador"
    chocan = sorted(set(ids_rover) & cfg.marcadores_esquina.ids_esperados)
    if chocan:
        return "los IDs {} están reservados para los marcadores de esquina".format(chocan)
    s = cfg.sintetico
    if min(s.ancho_px, s.alto_px) <= 2 * s.margen_px:
        return "el margen no deja lugar para el tablero dentro de la imagen"
    if s.borde_blanco_celdas <= 0:
        return "borde_blanco_celdas debe ser > 0: sin zona blanca el detector no ve los marcadores"
    # Los marcadores de esquina están centrados EN la esquina, así que sobresalen
    # media marca más su borde blanco hacia afuera de la cancha. Si eso no entra
    # en el margen, el borde de la imagen le come el blanco y el detector deja de
    # encontrarlos: la prueba fallaría por el encuadre y no por lo que se quería
    # probar, que es el peor tipo de falla porque parece un error de geometría.
    ppc = min(
        (s.ancho_px - 2 * s.margen_px) / cfg.tablero.cols,
        (s.alto_px - 2 * s.margen_px) / cfg.tablero.rows,
    )
    vuelo_celdas = s.lado_marcador_esquina_celdas / 2.0 + s.borde_blanco_celdas
    if vuelo_celdas * ppc > s.margen_px:
        return (
            "sintetico.margen_px = {} no alcanza: los marcadores de esquina sobresalen "
            "{:.1f} celdas ≈ {:.0f} px hacia afuera de la cancha (media marca más su borde "
            "blanco) y quedarían recortados contra el borde de la imagen".format(
                s.margen_px, vuelo_celdas, vuelo_celdas * ppc
            )
        )
    if not (0.0 <= s.perspectiva.inclinacion_grados < 60.0):
        return "perspectiva.inclinacion_grados debe estar en [0, 60): es un ángulo físico"
    if s.altura_camara_mm <= 0:
        return "sintetico.altura_camara_mm debe ser > 0"
    c = cfg.camara
    if isinstance(c.indice, str):
        if c.indice.lower() not in ("menu", "auto"):
            return (
                "camara.indice debe ser un número, \"menu\" (preguntar cuál usar) "
                "o \"auto\" (tomar la primera que responda), no {!r}".format(c.indice)
            )
    elif c.indice < 0:
        return "camara.indice no puede ser negativo"
    if c.backend not in ("auto", "avfoundation", "dshow", "msmf", "v4l2", "any"):
        return "camara.backend desconocido: {!r}".format(c.backend)
    if c.ancho <= 0 or c.alto <= 0:
        return "camara.ancho y camara.alto deben ser > 0"
    if c.fourcc is not None and len(str(c.fourcc)) != 4:
        return "camara.fourcc debe tener exactamente 4 letras (por ejemplo 'MJPG') o ser null"
    for nombre, aj in (("exposicion", c.exposicion), ("enfoque", c.enfoque),
                       ("balance_blancos", c.balance_blancos)):
        if aj.prueba_a == aj.prueba_b:
            return (
                "camara.ajustes.{}: prueba_a y prueba_b son iguales, así no se puede "
                "verificar por efecto (hacen falta dos valores distintos)".format(nombre)
            )
    k = cfg.calibracion
    if k.columnas_internas == k.filas_internas:
        return (
            "calibracion.patron: columnas_internas y filas_internas deben ser DISTINTAS; "
            "con un patrón cuadrado el detector no puede determinar la orientación"
        )
    if min(k.columnas_internas, k.filas_internas) < 3:
        return "calibracion.patron: hacen falta al menos 3 esquinas internas por lado"
    if k.lado_mm <= 0:
        return "calibracion.patron.lado_mm debe ser > 0 (es el tamaño real medido con regla)"
    if k.modelo not in ("estandar", "racional"):
        return "calibracion.modelo debe ser 'estandar' o 'racional', no {!r}".format(k.modelo)
    if not (0.0 <= k.alpha <= 1.0):
        return "calibracion.alpha debe estar entre 0 y 1"
    if k.vistas_minimas < 6:
        return "calibracion.vistas_minimas: con menos de 6 vistas la calibración no es confiable"
    if k.papel not in ("carta", "a4", "oficio"):
        return "calibracion.papel desconocido: {!r}".format(k.papel)
    pr = cfg.precision
    if pr.umbral_mm <= 0:
        return "precision.umbral_mm debe ser > 0"
    if pr.id_marcador_prueba in cfg.marcadores_esquina.ids_esperados:
        return (
            "precision.id_marcador_prueba = {} choca con los marcadores de esquina: "
            "el marcador de prueba tiene que tener un ID distinto".format(pr.id_marcador_prueba)
        )
    if pr.cuadros_por_medicion < 2:
        return "precision.cuadros_por_medicion: con menos de 2 cuadros la medición no es sensible"
    if pr.altura_camara_mm <= pr.altura_marcador_mm:
        return "precision.altura_camara_mm tiene que ser mayor que altura_marcador_mm"
    if not pr.zonas:
        return "precision.zonas: hace falta al menos una zona donde medir"
    return None
