"""Diagnóstico de la cámara real: ¿sirve tal cual o hay algo que resolver?

Abre la webcam, muestra el video en vivo y contesta cuatro preguntas:

1. ¿Cuántos cuadros por segundo entrega de verdad, y con cuánto atraso?
2. ¿Deja fijar exposición, enfoque y balance de blancos, **de verdad**?
3. ¿Se ven los cuatro marcadores de esquina apuntando al tablero real?
4. Si algo falla, ¿qué hay que hacer?

Cómo se corre:

    python -m vision.tools.diagnostico_camara
    python -m vision.tools.diagnostico_camara --listar
    python -m vision.tools.diagnostico_camara --indice 1
    python -m vision.tools.diagnostico_camara --sin-ventana --segundos 10
    python -m vision.tools.diagnostico_camara --sintetico     # sin cámara

Por qué reusa la detección de `geometry/`
-----------------------------------------
La detección de marcadores ya existe y está verificada contra imágenes con
verdad conocida. Escribir otra acá daría dos implementaciones que pueden
divergir, y entonces el diagnóstico dejaría de decir nada sobre el sistema real.
"""

from __future__ import annotations

import argparse
import sys
import time

import cv2
import numpy as np

try:  # como paquete
    from ..configuracion import cargar_config
    from ..geometry.coordenadas import centro_de, detectar_marcadores
    from ..sources.camara import (
        ErrorCamara,
        FuenteCamara,
        describir_camaras,
        verificar_por_efecto,
    )
    from ..sources.generador_sintetico import FuenteSintetica
    from .panel import AMBAR, BLANCO, GRIS, ROJO, VERDE, Panel, Tipografia, escala_para
except ImportError:  # como script suelto
    from vision.configuracion import cargar_config  # type: ignore[no-redef]
    from vision.geometry.coordenadas import centro_de, detectar_marcadores  # type: ignore[no-redef]
    from vision.sources.camara import (  # type: ignore[no-redef]
        ErrorCamara,
        FuenteCamara,
        describir_camaras,
        verificar_por_efecto,
    )
    from vision.sources.generador_sintetico import FuenteSintetica  # type: ignore[no-redef]
    from vision.tools.panel import (  # type: ignore[no-redef]
        AMBAR, BLANCO, GRIS, ROJO, VERDE, Panel, Tipografia, escala_para,
    )

# Colores en BGR para lo que se dibuja con OpenCV directamente sobre el video
# (contornos de marcadores). El panel usa los de `panel.py`, que van en RGB.
_VERDE_BGR = (60, 200, 60)
_ROJO_BGR = (60, 60, 235)
_AMARILLO_BGR = (40, 200, 240)


# --------------------------------------------------------------------------
# Dibujo sobre la imagen
# --------------------------------------------------------------------------


def _dibujar_marcadores(lienzo: np.ndarray, detectados: dict, esperados: frozenset) -> None:
    """Marca cada marcador encontrado: contorno, ID y centro.

    Los de esquina van en verde y cualquier otro en amarillo, para que se vea de
    un golpe si están los cuatro que anclan las coordenadas.
    """
    for id_aruco, esquinas in detectados.items():
        color = _VERDE_BGR if id_aruco in esperados else _AMARILLO_BGR
        puntos = esquinas.astype(np.int32).reshape(-1, 1, 2)
        cv2.polylines(lienzo, [puntos], True, color, 2, cv2.LINE_AA)
        cx, cy = centro_de(esquinas)
        cv2.circle(lienzo, (int(cx), int(cy)), 5, color, -1)
        cv2.putText(
            lienzo, str(id_aruco), (int(cx) + 10, int(cy) - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2, cv2.LINE_AA,
        )


# --------------------------------------------------------------------------
# Texto del informe
# --------------------------------------------------------------------------


def _estados_ajustes(informes, efectos) -> list[tuple[str, str, tuple[int, int, int]]]:
    """Une lo que la cámara dijo con lo que la imagen demostró.

    Se muestran juntos a propósito: "la cámara dice que aceptó" sin "y la imagen
    cambió" no alcanza para confiar en que la exposición quedó fija.

    Devuelve `(etiqueta, estado, color)`; el color es el que primero se lee.
    """
    por_nombre = {e.nombre: e for e in efectos}
    filas = []
    for inf in informes:
        efecto = por_nombre.get(inf.nombre)
        etiqueta = inf.nombre.capitalize()
        if not inf.soportado:
            filas.append((etiqueta, "no soportado por el backend", AMBAR))
        elif efecto is None:
            filas.append((etiqueta, "{} · sin verificar".format(inf.veredicto.lower()), GRIS))
        elif efecto.confirmado:
            filas.append((etiqueta, "fijada · {} cambió".format(efecto.magnitud), VERDE))
        else:
            filas.append((etiqueta, "no se pudo fijar · {} no cambió".format(efecto.magnitud), ROJO))
    return filas


def _resumen_texto(fuente, informes, efectos, detectados, esperados) -> str:
    """El informe en lenguaje claro que se imprime al cerrar."""
    encontrados = sorted(set(detectados) & set(esperados))
    otros = sorted(set(detectados) - set(esperados))
    es_camara = hasattr(fuente, "formato_negociado")
    fmt = fuente.formato_negociado() if es_camara else {}

    partes = ["", "=" * 74, "RESUMEN DEL DIAGNÓSTICO", "=" * 74]
    if fmt:
        partes.append(
            "  Cámara {} por {}: {}x{} @ {:.0f} fps declarados, códec {}".format(
                fmt["indice"], fmt["backend"], fmt["ancho"], fmt["alto"],
                fmt["fps_declarado"], fmt["fourcc"]))
    else:
        partes.append("  Fuente SINTÉTICA (no hay cámara involucrada)")
    partes.append("  fps reales medidos: {:.1f}".format(getattr(fuente, "fps_real", 0.0)))
    if hasattr(fuente, "pisados"):
        partes.append("  cuadros leídos: {}  ·  pisados sin usar: {}  ·  fallos: {}".format(
            fuente.leidos, fuente.pisados, fuente.fallos))

    partes += ["", "  AJUSTES DE CÁMARA"]
    if not informes:
        partes.append("    (no se intentó fijar ninguno)")
    for inf in informes:
        efecto = next((e for e in efectos if e.nombre == inf.nombre), None)
        partes.append("    {:<20} reporta: {:<13} {}".format(
            inf.nombre, inf.veredicto,
            "efecto: " + efecto.veredicto if efecto else "efecto: no probado"))
        partes.append("      {}".format(inf.detalle))
        if efecto:
            partes.append("      medido: {} = {:.3f} vs {:.3f}  (diferencia {:.3f}, umbral {:.3f})".format(
                efecto.magnitud, efecto.valor_a, efecto.valor_b, efecto.diferencia, efecto.umbral))

    partes += ["", "  MARCADORES DE ESQUINA"]
    partes.append("    esperados: {}".format(sorted(esperados)))
    partes.append("    detectados: {}  ->  {} de {}".format(
        encontrados, len(encontrados), len(esperados)))
    if otros:
        partes.append("    otros marcadores visibles: {}".format(otros))

    partes += ["", "  QUÉ SIGNIFICA"]
    if len(encontrados) == len(esperados):
        partes.append("    ✓ Los cuatro marcadores se detectan{}.".format(
            " en el tablero real" if es_camara else " (en la imagen sintética)"))
        partes.append("      El sistema de coordenadas se puede anclar.")
    elif encontrados:
        partes.append("    ✗ Faltan marcadores: {}".format(
            sorted(set(esperados) - set(encontrados))))
        partes.append("      Revisar que estén completos, planos, iluminados, sin reflejos")
        partes.append("      y con su margen blanco libre. Ver MONTAJE.md.")
    else:
        partes.append("    ✗ No se detectó ningún marcador de esquina.")
        partes.append("      Revisar que la cámara apunte al tablero y que haya foco y luz.")

    exposicion = next((e for e in efectos if e.nombre == "exposición"), None)
    inf_exp = next((i for i in informes if i.nombre == "exposición"), None)
    if exposicion is not None and exposicion.confirmado:
        partes.append("    ✓ La exposición SE PUEDE FIJAR: la imagen cambió al moverla.")
        partes.append("      Es lo que hace falta para que el robot negro no arruine la toma.")
    elif inf_exp is not None and not inf_exp.soportado:
        partes.append("    ! La exposición no se pudo probar en este sistema.")
        partes.append("      En macOS, OpenCV sobre AVFoundation casi no expone controles de")
        partes.append("      cámara. Esto NO quiere decir que la cámara no sirva: la prueba")
        partes.append("      que vale hay que hacerla en Windows, que es el destino real.")
    elif exposicion is not None:
        partes.append("    ✗ La exposición NO se pudo fijar: la imagen no cambió al moverla.")
        partes.append("      Con exposición automática, la cámara sube la ganancia por el robot")
        partes.append("      negro y quema los marcadores. Habría que buscar otra cámara o")
        partes.append("      fijarla con la utilidad del fabricante.")

    if getattr(fuente, "aviso", None):
        partes += ["", "  ⚠ AVISO", "    " + fuente.aviso]

    partes.append("=" * 74)
    return "\n".join(partes)


# --------------------------------------------------------------------------
# Programa
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Diagnóstico de la cámara: fps, ajustes y marcadores de esquina."
    )
    parser.add_argument("--config", default=None)
    parser.add_argument("--indice", type=int, default=None, help="qué cámara abrir")
    parser.add_argument("--listar", action="store_true", help="probar qué cámaras responden y salir")
    parser.add_argument("--sintetico", action="store_true",
                        help="usar el generador sintético en vez de la cámara")
    parser.add_argument("--sin-ventana", action="store_true",
                        help="sin ventana; informa por consola (útil sin pantalla)")
    parser.add_argument("--segundos", type=float, default=0.0,
                        help="cerrar solo después de N segundos (0 = hasta que cierres vos)")
    parser.add_argument("--sin-efecto", action="store_true",
                        help="saltear la verificación por efecto (más rápido)")
    args = parser.parse_args(argv)

    cfg = cargar_config(args.config) if args.config else cargar_config()
    esperados = cfg.marcadores_esquina.ids_esperados

    if args.listar:
        print("Probando cámaras (hasta 3 s cada una, hay que tener paciencia)...")
        encontradas = describir_camaras(backend=cfg.camara.backend)
        print()
        if encontradas:
            print("  CÁMARAS DETECTADAS")
            print("  " + "-" * 68)
            for camara in encontradas:
                marca = "   <- la de config_vision.json" if camara.indice == cfg.camara.indice else ""
                print(camara.linea() + marca)
            print("  " + "-" * 68)
            print()
            print("  Para confirmar cuál es cuál, abrila y mirá la imagen:")
            for camara in encontradas:
                print("    python -m vision.tools.diagnostico_camara --indice {}".format(camara.indice))
            print()
            print("  Cuando sepas cuál es la del tablero, ponéla en config_vision.json,")
            print("  en camara.indice, para que deje de preguntar.")
        else:
            print("  Ninguna cámara respondió.")
            print("  En macOS suele ser el permiso: Ajustes del Sistema → Privacidad")
            print("  y seguridad → Cámara, habilitá la app desde donde lanzás esto,")
            print("  y reiniciala por completo.")
        return 0 if encontradas else 1

    # --- abrir la fuente --------------------------------------------------
    if args.sintetico:
        print("Usando el generador sintético (sin cámara).")
        fuente = FuenteSintetica(cfg)
        informes, efectos = (), ()
    else:
        print("Abriendo la cámara {}...".format(
            args.indice if args.indice is not None else cfg.camara.indice))
        try:
            fuente = FuenteCamara(cfg.camara, indice=args.indice)
        except ErrorCamara as exc:
            print("\nERROR: {}".format(exc), file=sys.stderr)
            print("\nProbá 'python -m vision.tools.diagnostico_camara --listar' para ver "
                  "qué cámaras responden.", file=sys.stderr)
            return 2
        if fuente.aviso:
            print("\n⚠ {}\n".format(fuente.aviso))
        informes = fuente.informes
        efectos = ()
        if not args.sin_efecto:
            print("Verificando si los ajustes tienen efecto real (unos segundos)...")
            try:
                efectos = verificar_por_efecto(fuente)
            except ErrorCamara as exc:
                print("  no se pudo completar la verificación: {}".format(exc))

    # --- bucle ------------------------------------------------------------
    inicio = time.monotonic()
    ultimo_aviso = 0.0
    detectados: dict = {}
    ventana = "Diagnostico de camara — Vision Rover Challenge"
    hay_ventana = not args.sin_ventana
    # La tipografía se carga una sola vez: el panel se dibuja en cada cuadro y
    # abrir la fuente cada vez costaría más que dibujar.
    tipografia = Tipografia()
    if hay_ventana and not tipografia.disponible:
        print("(Pillow no está instalado: el panel va sin acentos. "
              "Se arregla con 'pip install pillow'.)")

    try:
        while True:
            cuadro = fuente.leer()
            if cuadro is None:
                time.sleep(0.01)
                if time.monotonic() - inicio > 10:
                    print("La cámara no entregó ningún cuadro en 10 s.", file=sys.stderr)
                    return 2
                continue

            detectados = detectar_marcadores(
                cuadro.imagen, cfg.marcadores_esquina.nombre_diccionario)
            encontrados = sorted(set(detectados) & set(esperados))
            completo = len(encontrados) == len(esperados)

            if hay_ventana:
                lienzo = cuadro.imagen.copy()
                if lienzo.ndim == 2:
                    lienzo = cv2.cvtColor(lienzo, cv2.COLOR_GRAY2BGR)
                # El panel se escala con la resolución: uno pensado para 1080p
                # queda ilegible a 480p y ridículo a 4K.
                escala = escala_para(lienzo.shape[0])
                if abs(tipografia.escala - escala) > 0.01:
                    tipografia = Tipografia(escala)
                _dibujar_marcadores(lienzo, detectados, esperados)
                fmt = fuente.formato_negociado() if hasattr(fuente, "formato_negociado") else {}

                panel = Panel(tipografia)
                panel.titulo("Diagnóstico de cámara")
                panel.destacado(
                    "{} / {}  marcadores de esquina".format(len(encontrados), len(esperados)),
                    VERDE if completo else ROJO,
                    "IDs {}".format(" · ".join(str(i) for i in encontrados)) if encontrados
                    else "no se ve ninguno todavía",
                )
                panel.separador()
                panel.datos("{}×{}    {}    {:.1f} fps    edad {} ms".format(
                    fmt.get("ancho", lienzo.shape[1]), fmt.get("alto", lienzo.shape[0]),
                    fmt.get("fourcc", "sintético"), getattr(fuente, "fps_real", 0.0),
                    cuadro.edad_ms()))
                estados = _estados_ajustes(informes, efectos)
                if estados:
                    panel.separador()
                    for etiqueta, texto, color in estados:
                        panel.estado(etiqueta, texto, color)
                panel.separador()
                panel.pie("q  salir     ·     g  guardar imagen")
                panel.dibujar(lienzo)
                try:
                    cv2.imshow(ventana, lienzo)
                except cv2.error as exc:
                    print("No se pudo abrir la ventana ({}). Sigo sin ventana.".format(exc))
                    hay_ventana = False
                    continue
                tecla = cv2.waitKey(1) & 0xFF
                if tecla in (ord("q"), 27):
                    break
                if tecla == ord("g"):
                    nombre = "diagnostico_{}.png".format(int(time.time()))
                    cv2.imwrite(nombre, lienzo)
                    print("  imagen guardada: {}".format(nombre))
            else:
                ahora = time.monotonic()
                if ahora - ultimo_aviso >= 1.0:
                    ultimo_aviso = ahora
                    print("  {:.1f} fps · edad {} ms · marcadores de esquina {}/{} {}".format(
                        getattr(fuente, "fps_real", 0.0), cuadro.edad_ms(),
                        len(encontrados), len(esperados), encontrados))
                time.sleep(0.02)

            if args.segundos > 0 and time.monotonic() - inicio >= args.segundos:
                break
    except KeyboardInterrupt:
        pass
    finally:
        if hay_ventana:
            cv2.destroyAllWindows()
        print(_resumen_texto(fuente, informes, efectos, detectados, esperados))
        fuente.cerrar()

    encontrados = sorted(set(detectados) & set(esperados))
    return 0 if len(encontrados) == len(esperados) else 1


if __name__ == "__main__":
    sys.exit(main())
