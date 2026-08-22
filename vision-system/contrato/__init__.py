"""Paquete `contrato` — pieza autónoma del Vision-Rover-Challenge.

Define el formato de telemetría (el "contrato") que consumen los equipos y el
simulador. Corre con Python puro: NO depende de OpenCV, de la cámara ni del
paquete `vision`. Esta independencia es intencional y debe conservarse, para
poder entregar el contrato a los equipos por sí solo.

Piso de versión: **Python 3.9+**, más bajo que el de `vision/` (3.10+). Los
equipos corren esto en sus propias máquinas y el Python de fábrica de macOS es
3.9; `vision/` en cambio corre en estaciones que controlamos nosotros. Al tocar
este paquete hay que respetar el piso: nada de `slots=True` en dataclasses ni
`match`.
"""
