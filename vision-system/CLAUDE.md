# CLAUDE.md — Reglas del Proyecto (Sistema de Visión)

Este repositorio es un **fork** del reto **Vision-Rover-Challenge** de CENFOTEC.
Este documento fija las reglas que rigen TODO el desarrollo del **sistema de visión**
para que sea consistente. Cualquier trabajo debe respetar lo aquí escrito.

> Rama de trabajo: **`desarrollo`**. Nunca se commitea a `main`.

---

## 1. Alcance

- Construimos **únicamente el sistema de visión**: una cámara cenital que observa
  una cancha de ~1 m × 1 m y publica varias veces por segundo, por TCP, la posición
  de cada robot, cada cubo y cada obstáculo, como telemetría que los equipos consumen.
- **NO construimos la inteligencia de los rovers**: planificación, control,
  coordinación ni firmware de juego. Eso es responsabilidad de los equipos.
- **NO se toca lo existente en el repo.** Son intocables:
  `archivos_fabricacion/`, `codigos/`, `README.md`, `reglamento.md`, `robot.md`
  y las imágenes. No se editan, mueven ni borran sin pedir permiso.

---

## 2. Regla de oro — El contrato es sagrado

El formato **JSON** que publica la visión es un **contrato** con los equipos.
Los equipos consumen ese formato y **no pueden adaptarse a cambios sorpresa**.

- El contrato **NO se cambia** sin **subir la versión de protocolo** y **avisar**.
- Todo cambio de forma, nombre de campo, unidad o semántica = cambio de contrato.
- Ante la duda: si un equipo ya escribió código contra el formato, es contrato.

---

## 3. Arquitectura

**Flujo en una sola dirección: productores → interfaz → consumidores.**

- **Productores** (cámara, geometría, detectores, seguimiento) generan un
  **"estado del mundo"**.
- **Consumidores** (publicación, grabación) **leen** ese estado.
- Lo único que cruza entre ambos lados es el **estado del mundo**, que es **inmutable**.
  No se muta en el lugar; se produce uno nuevo.

**Relojes desacoplados:**
- El **procesamiento** corre a la velocidad de la **cámara**.
- La **publicación** corre por **temporizador**.
- Uno **nunca** bloquea al otro.

**Falla abierto (fail-open):**
- Ante cualquier excepción se **conserva el último estado bueno** y se **sigue publicando**.
- El sistema **no se cae a mitad de ronda**.

---

## 4. Regla de dependencias

- El **contrato** es una pieza **independiente de primer nivel**:
  carpeta **`contrato/`**, hermana de **`vision/`**.
- El **sistema de visión puede depender del contrato**.
- El **contrato NUNCA depende del sistema de visión.**
  Debe poder entregarse solo a los equipos.

```
repositorio/
├── contrato/     # independiente; entregable a los equipos por sí solo
└── vision/       # depende de contrato/, nunca al revés
```

---

## 5. Decisiones cerradas (no re-litigar)

### Transporte y publicación
- **Transporte: TCP con NDJSON** (un JSON por línea). **No MQTT, no WebSocket.**
- **El último valor gana:** buffer de **un mensaje por cliente**; si no drena, se pisa.
  **Nunca encolar telemetría vieja.**
- Cada mensaje lleva **número de secuencia** y **marca de tiempo de captura**.

### Árbitro y fases
- La **visión es árbitro**: expone un campo de **fase**:
  `IDLE` / `READY` / `RUNNING` / `FINISHED`.

### Sistema de coordenadas
- Anclado a **cuatro marcadores ArUco de esquina** (`DICT_4X4_50`).
- **Origen (0,0) = marcador de menor ID (ID 0) = esquina de salida de los robots.**
- `col` crece a la **derecha**, `row` crece hacia **abajo**.
- **Ángulo en grados**, `0 = derecha`, sentido **antihorario**.
- Posiciones en **celdas con decimales** (una celda = **20 mm**).
  **Nunca redondear a entero.**

### Entidades
- **Rovers:** identidad = **ID de su marcador ArUco**
  (los dos robots son negros e idénticos; solo el marcador los distingue).
- **Cubos:** **6 cm**, identidad = **color** (`green`, `blue`, `red`);
  **no hay dos del mismo color**.
- **Obstáculos:** bloques **amarillos de 10 cm**.
  El **amarillo está reservado**: nunca es un cubo.
- **Lugares fijos** (salida y zonas de acopio) van en **listas separadas** de los cubos.
  Cada cubo va a la **zona de acopio de su color**.

### Cámara
- **Webcam USB**, lente **gran angular**, **enfoque manual**.
- **Exposición, enfoque y balance de blancos SIEMPRE fijos, nunca en automático.**
- **Calibración de distorsión obligatoria** por el lente ancho.

### Percepción
- **Detección de color:** segmentar por **saturación** (el tablero es acromático)
  y clasificar en espacio **Lab** (no HSV).
- **Paralaje:** los objetos altos (cubo 6 cm, marcador del rover ~10 cm) se ven
  corridos **hacia afuera**. **Corregirlo es obligatorio**, usando la **pose de cámara**
  deducida de los cuatro marcadores más la **altura conocida** del objeto.
- **Oclusión:** un objeto tapado **mantiene su última posición** con su **edad creciendo**.
  **Nunca** hacerlo parpadear entre existir y no existir.

### Configuración
- **Perfiles de cámara:** los parámetros específicos de cada cámara van en
  **configuración, no en el código**, para soportar más de un modelo sin bifurcar.

---

## 6. Estándares de código

- **Python:** `contrato/` requiere **3.9+** (lo corren los equipos en sus máquinas;
  piso bajo a propósito para no excluir a nadie). `vision/` requiere **3.10+**
  (lo corro yo y las estaciones controladas; puede usar sintaxis moderna sin reparos).
- **Dependencias de visión:** `opencv-contrib-python`, `numpy`, `pyyaml`.
  Nada pesado sin pedirlo.
- El **cliente de referencia del robot** se escribe en **CircuitPython** (ESP32/IdeaBoard),
  **no en Arduino**.
- **Configuración como datos:** todo umbral, ID, rango de color, tamaño de grilla y tasa
  va en un **archivo de configuración**, no incrustado en el código.
- **Código y comentarios en español**; docstrings que expliquen el **porqué**.
- Preferir **lo simple sobre lo ingenioso**; funciones **cortas y testeables**.
- Separar **"detectar"** de **"decidir"**.
- **No sobre-ingeniería.**

---

## 7. Qué NO hacer

- ❌ No implementar lógica de los rovers.
- ❌ No cambiar el contrato sin subir versión.
- ❌ No usar MQTT ni WebSocket ni colas que acumulen.
- ❌ No usar ajustes automáticos de cámara.
- ❌ No indexar arreglos por posición fija (iterar; la cantidad de objetos varía).
- ❌ No bloquear el proceso esperando la red, ni la red esperando al proceso.
- ❌ No mutar el estado del mundo en el lugar.
- ❌ No crear archivos fuera de `contrato/` y `vision/` sin pedirlo.

---

## 8. Despliegue

- El sistema corre en **Docker sobre Windows** en la máquina de competencia,
  con un **puente de captura nativo** para la webcam.
- Los equipos instalan el **sistema nativo en Windows** con un **instalador de un clic**
  y **autodiagnóstico**.
- El **contrato** y el **simulador** se entregan **aparte, livianos**,
  para correr con **Python directo**.
- Las **herramientas visuales** (calibración, monitor) corren **nativas fuera de Docker**.

---

## 9. Git

- Rama de trabajo: **`desarrollo`**. **No commitear a `main`.**
- Commits **chicos y descriptivos, en español**.
- Remotos: `origin` = fork propio (`soviedos/Vision-Rover-Challenge`);
  `upstream` = repo original de CENFOTEC.
