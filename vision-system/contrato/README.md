# contrato/

Pieza **autónoma** del Vision-Rover-Challenge. Se entrega a los equipos **por sí
sola** y corre con **Python puro**: no requiere OpenCV, ni cámara, ni el paquete
`vision`.

## Para qué sirve

- Define el **formato de telemetría** (el "contrato") que la visión publica por
  TCP/NDJSON y que los equipos consumen. Es el único punto de acuerdo entre la
  visión y los equipos.
- Permite a los equipos **desarrollar sin cámara**: incluye (o incluirá) un
  **simulador** que emite telemetría con el mismo formato que el sistema real,
  para que los equipos prueben su lógica de rover contra datos realistas.

## Regla de dependencias

El contrato **NUNCA depende de `vision/`** (ver `CLAUDE.md`, sección 4). El
sistema de visión puede depender del contrato, pero no al revés. Así el contrato
sigue siendo entregable de forma independiente.

## El contrato es sagrado

El formato **no se cambia** sin **subir la versión de protocolo** y **avisar** a
los equipos (ver `CLAUDE.md`, sección 2). Todo cambio de forma, nombre de campo,
unidad o semántica es un cambio de contrato.

## Cómo se corre el simulador

> Pendiente de implementar. El simulador correrá con Python puro, sin
> dependencias externas pesadas. La invocación prevista será algo como:
>
> ```bash
> python -m contrato.simulador
> ```
>
> Esta sección se completará cuando el simulador exista. Ver `requirements.txt`
> para las dependencias (por ahora, ninguna externa).
