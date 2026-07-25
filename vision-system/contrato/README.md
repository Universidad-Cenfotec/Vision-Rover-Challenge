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

## Qué hay acá

| Archivo | Qué es |
|---|---|
| `CONTRATO.md` | **El documento para los equipos.** Formato del mensaje, coordenadas, fases y reglas de consumo. Empezar por acá. |
| `schema.py` | El contrato en código: constantes, estructuras inmutables y `validate_message()`. |
| `mock_publisher.py` | Simulador: publica telemetría sintética por TCP/NDJSON, con las patologías reales incluidas. |
| `test_client.py` | Cliente de referencia: consume, valida y mide latencia y saltos de secuencia. |
| `config_simulador.json` | Toda la configuración del simulador. Nada incrustado en el código. |

## Cómo se corre

En una terminal, el simulador:

```bash
python -m contrato.mock_publisher          # publica en el puerto 2026
```

Comandos por teclado mientras corre: `ready`, `start`, `stop`, `quit`.

En otra, el cliente de referencia:

```bash
python -m contrato.test_client             # se conecta a 127.0.0.1:2026
```

Ambos corren con Python puro; ver `requirements.txt` (no hay dependencias
externas).
