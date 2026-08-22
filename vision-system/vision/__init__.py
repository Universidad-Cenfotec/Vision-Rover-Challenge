"""Paquete `vision` — sistema de visión del Vision-Rover-Challenge.

Cámara cenital que observa la cancha y publica por TCP/NDJSON dónde está cada
robot, cada cubo y cada obstáculo. Sigue el flujo en una sola dirección
productores -> interfaz -> consumidores (ver README.md y CLAUDE.md, sección 3).

Puede depender de `contrato`, pero `contrato` nunca depende de `vision`.

Piso de versión: **Python 3.10+**, más alto que el de `contrato` (3.9+). Este
paquete corre en máquinas que controlamos nosotros —la de competencia y las
estaciones de calibración—, así que puede usar sintaxis moderna sin reparos
(`slots=True`, `match`, etc.). El contrato no, porque lo corren los veinte
equipos en las suyas.
"""
