# contrato/

Pieza **autónoma** del Vision-Rover-Challenge. Se entrega a los equipos **por sí
sola** y corre con **Python puro**: no requiere OpenCV, ni cámara, ni el paquete
`vision`.

## 👉 ¿Sos de un equipo y querés arrancar?

Andá a **[`CONTRATO.md`](CONTRATO.md)**, sección 7. Ahí está la guía paso a paso
para levantar el simulador y ver telemetría en pantalla, sin dar nada por
sabido. Este README es el mapa de la carpeta; ese otro es el manual.

## Para qué sirve

- Define el **formato de telemetría** (el "contrato") que la visión publica por
  TCP/NDJSON y que los equipos consumen. Es el único punto de acuerdo entre la
  visión y los equipos.
- Permite a los equipos **desarrollar sin cámara**: incluye un **simulador** que
  emite telemetría con el mismo formato que el sistema real, para que los
  equipos prueben su lógica de rover contra datos realistas.

## Regla de dependencias

El contrato **NUNCA depende de `vision/`** (ver `CLAUDE.md`, sección 4). El
sistema de visión puede depender del contrato, pero no al revés. Así el contrato
sigue siendo entregable de forma independiente.

## El contrato es sagrado

El formato **no se cambia** sin **subir la versión de protocolo** y **avisar** a
los equipos (ver `CLAUDE.md`, sección 2). Todo cambio de forma, nombre de campo,
unidad o semántica es un cambio de contrato.

## Qué hay acá

| Archivo | Qué es |
|---|---|
| `CONTRATO.md` | **El documento para los equipos.** Guía de arranque, formato del mensaje, coordenadas, fases y reglas de consumo. Empezar por acá. |
| `schema.py` | **Uso interno del sistema de visión.** Fuente de verdad compartida entre el simulador y la visión real. Los equipos **no lo importan**: consumen el JSON crudo. |
| `mock_publisher.py` | Simulador: publica telemetría sintética por TCP/NDJSON, con las patologías reales incluidas. |
| `test_client.py` | Cliente de referencia: consume, valida y mide latencia y saltos de secuencia. |
| `config_simulador.json` | Toda la configuración del simulador. Nada incrustado en el código. |

## Cómo se corre, en dos líneas

Requiere **Python 3.9 o superior** y nada más: no hay dependencias que instalar.

Parado **dentro de esta carpeta** (`contrato/`), en dos terminales distintas:

```bash
python3 mock_publisher.py     # terminal 1: el simulador
python3 test_client.py        # terminal 2: el cliente de prueba
```

En Windows, cambiá `python3` por `python`.

Después escribí `ready` y luego `start` en la terminal 1.

> Si algo de esto falla, **no improvises**: la sección 7 de
> [`CONTRATO.md`](CONTRATO.md) tiene la guía completa y una lista de problemas
> frecuentes con su solución.

---

## Nota para quien mantiene el contrato

*(Esta sección no le hace falta a los equipos.)*

**Piso de versión más bajo que el resto del proyecto, a propósito.** El sistema
de visión (`vision/`) exige **Python 3.10+**; el contrato se conforma con
**3.9**. La razón está en **quién pone el intérprete**: `vision/` se instala con
un instalador que trae **su propio Python embebido**, así que su versión no
depende de la máquina; el contrato, en cambio, se entrega **suelto y sin
instalador**, y cada equipo lo corre con el Python que ya tiene —el de fábrica de
macOS es 3.9.

Al tocar `contrato/` hay que respetar ese piso: **nada de `slots=True` en
dataclasses, `match`, ni sintaxis 3.10+ que se evalúe en tiempo de ejecución**.
Las anotaciones modernas (`X | None`, `dict[str, Any]`) sí se pueden, porque
`from __future__ import annotations` hace que no se evalúen.

Para verificarlo antes de dar algo por bueno, correr las herramientas con un
intérprete 3.9 (en macOS, `/usr/bin/python3`).
