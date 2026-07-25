"""Paquete `vision` — sistema de visión del Vision-Rover-Challenge.

Cámara cenital que observa la cancha y publica por TCP/NDJSON dónde está cada
robot, cada cubo y cada obstáculo. Sigue el flujo en una sola dirección
productores -> interfaz -> consumidores (ver README.md y CLAUDE.md, sección 3).

Puede depender de `contrato`, pero `contrato` nunca depende de `vision`.
"""
