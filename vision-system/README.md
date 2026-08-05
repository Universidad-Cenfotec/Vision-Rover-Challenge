# Sistema de Visión — Vision Rover Challenge

Este directorio contiene el **sistema de visión global** del Vision Rover
Challenge de CENFOTEC: una cámara cenital que mira la cancha desde arriba y le
dice a los equipos, varias veces por segundo, **dónde está cada cosa**.

Si llegaste acá sin contexto, este documento te explica el sistema entero. Está
escrito para una persona, de arriba abajo; no hace falta leer código para
entenderlo.

---

## Índice

1. [Qué es esto y para qué sirve](#1-qué-es-esto-y-para-qué-sirve)
2. [El reparto de responsabilidades](#2-el-reparto-de-responsabilidades)
3. [El flujo del dato, de punta a punta](#3-el-flujo-del-dato-de-punta-a-punta)
4. [Arquitectura: productores, interfaz, consumidores](#4-arquitectura-productores-interfaz-consumidores)
5. [Estructura de carpetas](#5-estructura-de-carpetas)
6. [Decisiones de diseño y su porqué](#6-decisiones-de-diseño-y-su-porqué)
7. [El contrato: la frontera con los equipos](#7-el-contrato-la-frontera-con-los-equipos)
8. [Cómo correr y probar lo que ya existe](#8-cómo-correr-y-probar-lo-que-ya-existe)
9. [Estado actual del proyecto](#9-estado-actual-del-proyecto)
10. [Cómo seguir](#10-cómo-seguir)

---

## 1. Qué es esto y para qué sirve

En el reto, **dos rovers** tienen que encontrar unos **cubos de colores**,
esquivar **obstáculos** y llevar cada cubo hasta su **zona de acopio**. Los
rovers son ciegos: no tienen cámara propia ni saben dónde están.

Lo que los guía es una **cámara cenital** montada sobre la cancha. Esa cámara y
el software que la procesa son este proyecto.

El sistema hace tres cosas:

1. **Mira** la cancha (~1 m × 1 m) desde arriba.
2. **Deduce** dónde está cada rover, cada cubo y cada obstáculo, y hacia dónde
   apunta cada rover.
3. **Publica** esa información por la red, varias veces por segundo, en un
   formato fijo que los equipos consumen.

Además, el sistema hace de **árbitro**: es quien dice si la ronda está por
empezar, corriendo o terminada.

### Lo que este proyecto NO hace

**No maneja los rovers.** La planificación de rutas, la coordinación entre los
dos robots, el control de motores y la lógica de juego son responsabilidad de
**cada equipo**. Nosotros solo informamos; ellos deciden.

Esa frontera es importante y se respeta con cuidado: el día de la competencia,
veinte equipos van a estar consumiendo nuestros datos, y todos tienen que poder
confiar en que el formato no cambió.

---

## 2. El reparto de responsabilidades

```
        ┌───────────────────────────┐         ┌───────────────────────────┐
        │   NOSOTROS (este repo)    │         │      LOS EQUIPOS          │
        ├───────────────────────────┤         ├───────────────────────────┤
        │ • cámara y procesamiento  │  datos  │ • planificar rutas        │
        │ • dónde está cada objeto  │ ──────► │ • coordinar los 2 rovers  │
        │ • orientación de rovers   │  TCP    │ • evitar colisiones       │
        │ • fase de la ronda        │         │ • mover los motores       │
        │ • publicar telemetría     │         │ • firmware del robot      │
        └───────────────────────────┘         └───────────────────────────┘
                    ▲                                      │
                    │                                      │
                    └──────── nunca vuelve nada ───────────┘
              La comunicación es en UNA sola dirección: nosotros
              publicamos, ellos leen. No reciben comandos de vuelta.
```

---

## 3. El flujo del dato, de punta a punta

Este es el recorrido completo, desde la luz que entra a la cámara hasta el
rover que decide girar:

```
  MUNDO FÍSICO              SISTEMA DE VISIÓN                    LOS EQUIPOS
  ════════════              ═════════════════                    ═══════════

  ┌──────────────┐
  │ cancha 1×1 m │
  │  4 marcadores│
  │  2 rovers    │
  │  3 cubos     │
  │  obstáculos  │
  └──────┬───────┘
         │ luz
         ▼
  ┌──────────────┐
  │   cámara     │
  │   cenital    │
  │  (webcam USB)│
  └──────┬───────┘
         │ imagen + instante de captura
         │
    ─────┼──────────────────────────────────────────────────────────────────
         ▼
  ┌─────────────────┐   ①  Captura con ajustes FIJOS (exposición, enfoque,
  │   sources/      │      balance de blancos). Sella cada cuadro con la hora
  │   captura       │      exacta en que se tomó.
  └────────┬────────┘
           ▼
  ┌─────────────────┐   ②  Encuentra los 4 marcadores ArUco de esquina y con
  │   geometry/     │      ellos arma el sistema de coordenadas: convierte
  │   píxeles→celdas│      píxeles en celdas. Corrige la distorsión del lente
  └────────┬────────┘      y el paralaje de los objetos altos.
           ▼
  ┌─────────────────┐   ③  Busca los rovers por su marcador ArUco, y los cubos
  │   detectors/    │      y obstáculos por color. Solo DETECTA: no interpreta.
  │   qué hay dónde │
  └────────┬────────┘
           ▼
  ┌─────────────────┐   ④  Mantiene la identidad de cada objeto entre cuadros.
  │   tracking/     │      Si algo se tapa, conserva su última posición y le
  │   identidad     │      hace crecer la "edad" en vez de hacerlo desaparecer.
  └────────┬────────┘
           │
           ▼
  ╔═══════════════════════════════════╗
  ║      ESTADO DEL MUNDO             ║   ⑤  Una foto completa e INMUTABLE de
  ║   (inmutable, se produce uno      ║      la cancha en un instante. Es lo
  ║    nuevo en cada cuadro)          ║      ÚNICO que cruza de un lado al otro.
  ╚═══════════════┬═══════════════════╝
                  │
         ┌────────┴─────────┐
         ▼                  ▼
  ┌─────────────┐    ┌─────────────┐   ⑥  Dos consumidores independientes que
  │  publish/   │    │   record/   │      solo LEEN el estado del mundo.
  │  a la red   │    │  a disco    │
  └──────┬──────┘    └─────────────┘
         │
         │  TCP · puerto 2026 · NDJSON (un JSON por línea)
         │  {"v":1,"seq":4137,"ts_ms":...,"phase":"RUNNING","rovers":[...]}
         │
    ─────┼──────────────────────────────────────────────────────────────────
         ▼
  ┌──────────────────┐
  │ código del equipo│   ⑦  Lee líneas, parsea el JSON, busca SU rover por id,
  │  (computadora    │      calcula a dónde ir…
  │   o ESP32)       │
  └────────┬─────────┘
           │ órdenes de motor (esto ya no es asunto nuestro)
           ▼
     ┌──────────┐
     │  rover   │
     └──────────┘
```

### Dos relojes que no se esperan

Hay un detalle que define toda la arquitectura: **el procesamiento y la
publicación corren a ritmos distintos y no se bloquean entre sí**.

- El **procesamiento** (pasos ① a ④) va a la velocidad de la cámara.
- La **publicación** (paso ⑥) va por temporizador propio.

Si un cuadro tarda de más en procesarse, la publicación no se frena: vuelve a
mandar el último estado bueno. Y si un equipo tiene la red lenta, el
procesamiento ni se entera.

### Qué pasa cuando algo falla

El sistema **falla abierto**: ante cualquier excepción conserva el **último
estado bueno** y sigue publicando. Nunca se cae a mitad de una ronda.

La lógica es simple: un dato de hace 300 milisegundos, marcado como viejo, le
sirve mucho más a un equipo que un silencio repentino.

---

## 4. Arquitectura: productores, interfaz, consumidores

Toda la arquitectura se apoya en una idea única:

> **Los productores generan un estado del mundo. Los consumidores lo leen. Eso
> es lo único que cruza entre los dos lados.**

| Lado | Quiénes | Qué hacen |
|---|---|---|
| **Productores** | `sources/`, `geometry/`, `detectors/`, `tracking/` | Convierten imágenes en un estado del mundo |
| **Interfaz** | el **estado del mundo** | Una foto inmutable de la cancha en un instante |
| **Consumidores** | `publish/`, `record/` | Solo leen ese estado. Nunca lo modifican |

### Por qué el estado del mundo es inmutable

Porque productores y consumidores corren en **hilos distintos**. Si el estado se
modificara en el lugar, un consumidor podría estar leyendo la posición del rover
justo cuando un productor la está reescribiendo, y publicaría una mezcla de dos
instantes distintos.

La solución no es poner candados por todos lados: es **no modificar nunca**. Cada
cuadro produce un estado **nuevo**. El anterior queda intacto para quien lo
estuviera usando.

---

## 5. Estructura de carpetas

```
Vision-Rover-Challenge/              # raíz del repositorio (fork de CENFOTEC)
├── README.md, reglamento.md         # material original de CENFOTEC
├── robot.md, archivos_fabricacion/  # (no los tocamos)
├── codigos/
│
└── vision-system/                   # ◄── TODO nuestro trabajo vive acá
    ├── README.md                    # este documento
    ├── MONTAJE.md                   # guía para armar la cancha física
    ├── CLAUDE.md                    # las reglas del proyecto
    ├── .gitignore
    │
    ├── contrato/                    # ◄── LO QUE SE ENTREGA A LOS EQUIPOS
    │   ├── CONTRATO.md              # el manual para los equipos
    │   ├── README.md
    │   ├── schema.py                # el formato en código (uso interno)
    │   ├── mock_publisher.py        # simulador: telemetría sin cámara
    │   ├── test_client.py           # cliente de referencia
    │   └── config_simulador.json
    │
    └── vision/                      # ◄── EL SISTEMA DE VISIÓN
        ├── README.md
        ├── configuracion.py         # carga la configuración
        ├── config_vision.json       # toda la configuración, como datos
        ├── requirements.txt
        │
        ├── sources/                 # productor: de dónde salen las imágenes
        ├── geometry/                # productor: píxeles → celdas
        ├── detectors/               # productor: qué hay y dónde
        ├── tracking/                # productor: identidad y oclusión
        ├── publish/                 # consumidor: a la red
        ├── record/                  # consumidor: a disco
        └── tools/                   # herramientas de puesta a punto
```

Cada subcarpeta de `vision/` tiene su propio `README.md` que dice qué hay hoy y
qué está planificado.

---

## 6. Decisiones de diseño y su porqué

Estas son las decisiones que más forma le dan al sistema. Están cerradas: se
discutieron, se resolvieron y no se vuelven a abrir sin un motivo nuevo. Las
reglas completas están en [`CLAUDE.md`](CLAUDE.md).

### Por qué TCP y NDJSON, y no MQTT ni WebSocket

**NDJSON** significa "un objeto JSON por línea, terminado en salto de línea".
Nada más.

- **Es legible.** Un equipo puede ver los datos con `nc` o un `print`, sin
  herramientas especiales. Cuando algo falla a las once de la noche antes de la
  competencia, eso vale más que cualquier eficiencia.
- **Es trivial de parsear.** Leer hasta el `\n` y `json.loads()`. Funciona igual
  en una computadora y en un microcontrolador.
- **No arrastra infraestructura.** MQTT necesita un *broker*: una pieza más que
  instalar, configurar y que puede fallar sola. WebSocket agrega un *handshake*
  HTTP para transportar los mismos bytes.

Veinte equipos con veinte niveles de experiencia distintos tienen que poder
conectarse. Un socket TCP es lo más simple que existe y está en todos los
lenguajes.

### Por qué el último valor gana

Cada cliente tiene un **buffer de un solo mensaje**. Si llega telemetría nueva y
el cliente no drenó la anterior, **la anterior se pisa**. Nunca se encola.

Porque en telemetría de posición **un dato viejo no vale nada**. Al rover le
sirve saber dónde está *ahora*, no dónde estuvo hace medio segundo. Con una cola,
un cliente lento se atrasaría cada vez más sin recuperarse jamás, navegando con
información cada vez más falsa.

Por eso los equipos ven saltos en el número de secuencia, y eso es **normal**:
es la política funcionando.

### Por qué las coordenadas se anclan a los marcadores

El sistema no dice "el rover está en el píxel 340, 210". Dice "el rover está en
la celda 12.4, 8.7".

**Los píxeles no le sirven a nadie**: dependen de la resolución, del lugar donde
quedó la cámara y de si alguien la movió sin querer. Las celdas son del mundo
físico y no cambian.

Para traducir, el sistema usa **cuatro marcadores ArUco** pegados en las esquinas
de la cancha. Al verlos en la imagen, sabe exactamente cómo está mirando el
tablero y puede convertir cualquier píxel a su celda.

La ventaja escondida: **si alguien mueve la cámara, el sistema se recalibra
solo** en el cuadro siguiente. Los marcadores no se movieron, así que las
coordenadas siguen significando lo mismo.

Se usa el **centro** de cada marcador —no una esquina— porque es lo único que se
puede medir sin ambigüedad, tanto en una imagen como con una cinta métrica sobre
la cancha.

### Por qué tres zonas de acopio, una por color

Hay **tres cubos**, de colores distintos (verde, azul, rojo), y **tres zonas de
acopio**, una de cada color, en las tres esquinas que no son la de salida.
**Cada cubo va a la zona de su color.**

Esto convierte el reto en un problema de **asignación**, no solo de transporte:
los equipos tienen que decidir qué rover lleva qué cubo y en qué orden, en vez de
empujar todo al mismo rincón.

Del lado del formato, los cubos y las zonas van en **listas separadas** aunque
compartan el color, porque son cosas distintas: los cubos se **detectan** —se
mueven, se tapan, envejecen— y las zonas se **declaran**: están siempre y no
cambian nunca.

### Por qué el color es la identidad del cubo

Los cubos no tienen número de identificación. **El color los identifica**, porque
no hay dos del mismo color.

Es una simplificación deliberada: si los cubos tuvieran ID, el sistema tendría
que seguir cada uno entre cuadros y no confundirlos al cruzarse. Con el color
alcanza, y no hay nada que confundir.

El **amarillo está reservado** para los obstáculos. Un objeto amarillo **nunca**
es un cubo. Por eso los obstáculos no llevan campo de color: ya se sabe cuál es.

### Por qué un objeto tapado no desaparece

Cuando un rover pasa por encima de un cubo, la cámara deja de verlo. El sistema
**no lo saca de la lista**: lo mantiene con su última posición conocida y le hace
crecer un campo de **edad** (`age_ms`).

Un objeto que parpadea entre existir y no existir vuelve loco al consumidor: el
código del equipo tendría que distinguir "se lo llevaron" de "no lo veo ahora
mismo", y no puede.

Es preferible un dato viejo **marcado como viejo** que un agujero.

### Por qué el contrato es una pieza aparte

`contrato/` es una carpeta **independiente** que se entrega a los equipos **por
sí sola**. Corre con Python puro: no necesita OpenCV, ni cámara, ni nada de
`vision/`.

La dependencia va en **un solo sentido**:

```
   vision/  ──puede depender de──►  contrato/
   contrato/  ──NUNCA depende de──►  vision/
```

Así los equipos reciben algo liviano que corre en cualquier máquina, sin
arrastrar 44 MB de OpenCV ni la mitad del sistema de visión.

### Por qué el sistema es árbitro

La visión publica un campo de **fase**: `IDLE`, `READY`, `RUNNING`, `FINISHED`.

Alguien tiene que decir cuándo empieza y termina la ronda, y tiene que ser una
sola voz. Si cada equipo decidiera por su cuenta, un rover podría arrancar antes
que el otro. La visión ya está mirando todo y hablándole a todos: es el lugar
natural para esa autoridad.

---

## 7. El contrato: la frontera con los equipos

El formato JSON que publica el sistema es un **contrato**. Es el único punto de
acuerdo entre nosotros y los equipos, y **no se cambia por sorpresa**.

Si algo tiene que cambiar, sube el número de versión (`v`) y se les avisa con
tiempo. Un equipo que escribió código contra el formato no puede adaptarse a un
cambio que descubre el día de la competencia.

### Qué reciben los equipos

Un mensaje por línea, unas veinte veces por segundo. Este es un mensaje real
completo, el mismo que aparece en [`contrato/CONTRATO.md`](contrato/CONTRATO.md)
(en el cable viaja todo en una sola línea; acá está formateado para leerlo):

```json
{
  "v": 1,
  "seq": 4137,
  "ts_ms": 1785012345678,
  "phase": "RUNNING",
  "grid": { "cols": 43, "rows": 43, "cell_mm": 20.0 },
  "rovers": [
    { "id": 10, "col": 4.302,  "row": 3.705,  "theta": 46.20, "age_ms": 0 },
    { "id": 11, "col": 15.265, "row": 28.661, "theta": 40.22, "age_ms": 0 }
  ],
  "cubes": [
    { "color": "green", "col": 25.968, "row": 9.999,  "age_ms": 0   },
    { "color": "blue",  "col": 15.000, "row": 29.000, "age_ms": 425 },
    { "color": "red",   "col": 33.071, "row": 25.983, "age_ms": 0   }
  ],
  "obstacles": [
    { "col": 21.468, "row": 21.511, "age_ms": 0 },
    { "col": 10.014, "row": 16.952, "age_ms": 0 },
    { "col": 30.946, "row": 14.951, "age_ms": 0 }
  ],
  "start":  { "col": 2.5, "row": 2.5 },
  "depots": [
    { "color": "green", "col": 40.5, "row": 2.5  },
    { "color": "blue",  "col": 2.5,  "row": 40.5 },
    { "color": "red",   "col": 40.5, "row": 40.5 }
  ]
}
```

**Fijate que `rovers`, `cubes`, `obstacles` y `depots` son listas con varios
elementos.** Eso no es casual: hay que **iterar** sobre ellas y buscar por
identidad —el rover por su `id`, el cubo por su `color`—, nunca tomar el primero
de la lista. La cantidad de objetos cambia entre mensajes y el orden no está
garantizado.

Mirá también el cubo **azul**: tiene `age_ms: 425` porque el rover 11 está
justo encima y lo tapa. El cubo **no desapareció** de la lista; sigue ahí con su
última posición conocida y la edad creciendo. Eso es lo normal, no un error.

Las posiciones van en **celdas con decimales** (una celda = 20 mm), con el origen
en el marcador ID 0, `col` creciendo a la derecha y `row` hacia abajo. Los
ángulos en grados, `0` = derecha, sentido antihorario.

### Los equipos consumen JSON crudo

**No importan ningún archivo nuestro.** Se conectan, cortan por `\n`, parsean con
`json.loads()` e iteran las listas buscando por identidad: el rover por su `id`,
el cubo por su `color`.

`schema.py` existe, pero es **infraestructura interna nuestra**: la fuente de
verdad compartida entre el simulador y el sistema de visión. No se ofrece como
biblioteca, y la documentación de los equipos tiene **un solo camino**.

### Pueden desarrollar sin cámara

`contrato/` incluye un **simulador** que emite telemetría con el mismo formato
que el sistema real, e incluso reproduce a propósito las patologías de la vida
real: ruido, oclusiones, pérdidas de detección y cubos que se mueven al ser
empujados.

Un equipo puede escribir y probar todo su código de rover **antes de ver una
cancha**.

El manual completo para los equipos está en
**[`contrato/CONTRATO.md`](contrato/CONTRATO.md)**.

---

## 8. Cómo correr y probar lo que ya existe

### Preparar el entorno (una sola vez)

El sistema de visión necesita **Python 3.10 o superior**. Parado en
`vision-system/`:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r vision/requirements.txt
```

Eso instala OpenCV y NumPy en un entorno aislado, sin tocar el Python del
sistema. La carpeta `.venv/` está ignorada por git.

### Probar el simulador del contrato

Esto **no necesita el entorno virtual ni ninguna instalación**: corre con
cualquier Python 3.9 o superior. Desde `vision-system/contrato/`, en dos
terminales:

```bash
python3 mock_publisher.py     # terminal 1: el simulador
python3 test_client.py        # terminal 2: el cliente de prueba
```

En la terminal 1, escribí `ready` y después `start`. Vas a ver la telemetría
llegando y validándose.

La guía completa, paso a paso y a prueba de principiantes, está en la sección 7
de [`contrato/CONTRATO.md`](contrato/CONTRATO.md).

### Probar la geometría del sistema de visión

Esto sí usa el entorno virtual. Desde `vision-system/`:

```bash
.venv/bin/python -m vision.tools.verificar_geometria
```

Genera imágenes sintéticas del tablero, detecta los cuatro marcadores de esquina,
arma el sistema de coordenadas y mide cuánto se desvía de la verdad conocida. Lo
hace en dos modos: con cámara perfectamente cenital y con la cámara inclinada.

Para ver la imagen que generó:

```bash
.venv/bin/python -m vision.tools.verificar_geometria --salida /tmp/tablero.png --anotar
```

---

## 9. Estado actual del proyecto

El sistema se construye por **hilos delgados**: en vez de completar una pieza
antes de empezar la siguiente, se arma un camino mínimo de punta a punta y se lo
va engrosando. Así siempre hay algo que funciona y se puede verificar.

### Terminado y verificado

| Pieza | Qué hace |
|---|---|
| **El contrato** (`contrato/`) | Formato definido, validador, simulador con patologías reales, cliente de referencia y manual completo. Protocolo **v1**. |
| **Generador sintético** (`vision/sources/`) | Crea imágenes del tablero con marcadores y rovers, **conociendo la verdad** de lo que dibujó. |
| **Geometría de esquinas** (`vision/geometry/`) | Detecta los 4 marcadores y convierte píxeles a celdas. Verificado con y sin inclinación de cámara: error máximo de **0,2 mm**. |
| **Verificación** (`vision/tools/`) | Compara lo detectado contra la verdad conocida. |

### Todavía no existe

| Pieza | Qué falta |
|---|---|
| **Captura real** (`sources/`) | Leer de la webcam USB con ajustes fijos. Hoy solo hay imágenes sintéticas. |
| **Calibración de distorsión** (`geometry/`) | El lente gran angular curva las líneas rectas y hay que corregirlo. |
| **Corrección de paralaje** (`geometry/`) | Los objetos altos se ven corridos hacia afuera; hay que compensarlo con la altura conocida. |
| **Detección de rovers** (`detectors/`) | Encontrar los rovers por su marcador y deducir su orientación. |
| **Detección de color** (`detectors/`) | Cubos y obstáculos por color, segmentando por saturación. |
| **Seguimiento** (`tracking/`) | Identidad entre cuadros, oclusión y edad. |
| **Publicación** (`publish/`) | Emitir el estado del mundo por TCP. Hoy solo lo hace el simulador. |
| **Grabación** (`record/`) | Guardar sesiones para repetirlas. |

---

## 10. Cómo seguir

- **Si vas a usar el sistema como equipo:** leé
  [`contrato/CONTRATO.md`](contrato/CONTRATO.md). Es lo único que necesitás.
- **Si vas a trabajar en el sistema de visión:** leé
  [`CLAUDE.md`](CLAUDE.md), que fija las reglas del proyecto, y después el
  `README.md` de la carpeta que vayas a tocar.
- **Si vas a montar la cancha física:** leé **[`MONTAJE.md`](MONTAJE.md)**. Tiene
  la disposición exacta de los marcadores, la regla del margen blanco y una
  comprobación para hacer antes de la primera ronda. Pegar los marcadores en otro
  orden rota todas las coordenadas, y el sistema no se queja.

El trabajo va en la rama **`desarrollo`**; `main` queda como llegó del fork.
