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
  ┌─────────────────┐   ②  Quita la curvatura que mete el lente gran angular,
  │   geometry/     │      usando el perfil de ESA cámara. Va antes que todo lo
  │   rectificación │      demás: la geometría de ③ supone que las rectas del
  └────────┬────────┘      mundo se ven rectas, y la distorsión rompe eso.
           ▼
  ┌─────────────────┐   ③  Encuentra los 4 marcadores ArUco de esquina y con
  │   geometry/     │      ellos arma el sistema de coordenadas, que convierte
  │   píxeles→celdas│      cualquier píxel en su celda.
  └────────┬────────┘
           ▼
  ┌─────────────────┐   ④  Busca los rovers por su marcador ArUco, y los cubos
  │   detectors/    │      y obstáculos por color. Solo DETECTA: no interpreta.
  │   qué hay dónde │
  └────────┬────────┘
           ▼
  ┌─────────────────┐   ⑤  Mantiene la identidad de cada objeto entre cuadros.
  │   tracking/     │      Si algo se tapa, conserva su última posición y le
  │   identidad     │      hace crecer la "edad" en vez de hacerlo desaparecer.
  └────────┬────────┘
           │
           ▼
  ╔═══════════════════════════════════╗
  ║      ESTADO DEL MUNDO             ║   ⑥  Una foto completa e INMUTABLE de
  ║   (inmutable, se produce uno      ║      la cancha en un instante. Es lo
  ║    nuevo en cada cuadro)          ║      ÚNICO que cruza de un lado al otro.
  ╚═══════════════┬═══════════════════╝
                  │
         ┌────────┴─────────┐
         ▼                  ▼
  ┌─────────────┐    ┌─────────────┐   ⑦  Dos consumidores independientes que
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
  │ código del equipo│   ⑧  Lee líneas, parsea el JSON, busca SU rover por id,
  │  (computadora    │      calcula a dónde ir…
  │   o ESP32)       │
  └────────┬─────────┘
           │ órdenes de motor (esto ya no es asunto nuestro)
           ▼
     ┌──────────┐
     │  rover   │
     └──────────┘
```

### Qué de todo esto ya funciona

El diagrama muestra el recorrido **completo**, que es a dónde va el sistema. Hoy
está construido hasta la mitad:

| Paso | Estado |
|---|---|
| ① captura · ② rectificación · ③ píxeles→celdas | ✅ **escritos y verificados** |
| ④ detectores — **rovers** | ✅ **escrito y verificado** |
| ④ detectores — cubos y obstáculos por color | ⚪ todavía no existe |
| ⑤ seguimiento · ⑥ estado del mundo · ⑦ consumidores | ⚪ todavía no existen |

Las etapas ya hechas existen como **piezas sueltas y probadas**, pero
**todavía no hay un programa que las encadene**: se ejercitan desde las
herramientas de `vision/tools/`, no desde un bucle de producción. El detalle
pieza por pieza está en la [sección 9](#9-estado-actual-del-proyecto).

### Dos relojes que no se esperan

Hay un detalle que define toda la arquitectura: **el procesamiento y la
publicación corren a ritmos distintos y no se bloquean entre sí**.

- El **procesamiento** (pasos ① a ⑤) va a la velocidad de la cámara.
- La **publicación** (paso ⑦) va por temporizador propio.

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

### Las capas se apilan, no se modifican entre sí

La corrección de distorsión es el primer ejemplo construido de una idea que se va
a repetir: **una etapa nueva se agrega envolviendo a la anterior, no editándola.**

`FuenteRectificada` recibe una fuente de imágenes y **es** una fuente de
imágenes. Se pone delante de la cámara y todo lo que viene después no se entera:

```
FuenteRectificada( FuenteCamara(...) )   ──►  .leer()  ──►  cuadro ya corregido
```

Se hizo por composición y no metiéndole la corrección a la cámara por dos
razones. Son **dos responsabilidades distintas** —capturar y corregir—, y así la
misma capa sirve también para la **fuente sintética**, que es lo que permite
verificar el sistema sin cámara.

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
    ├── PUESTA_A_PUNTO.md            # guía para dejar lista una cámara
    ├── CLAUDE.md                    # las reglas del proyecto
    ├── .gitignore
    │
    ├── contrato/                    # ◄── LO QUE SE ENTREGA A LOS EQUIPOS
    │   ├── CONTRATO.md              # el manual para los equipos
    │   ├── README.md
    │   ├── schema.py                # el formato en código (uso interno)
    │   ├── mock_publisher.py        # simulador: telemetría sin cámara
    │   ├── test_client.py           # cliente de referencia
    │   ├── config_simulador.json
    │   └── requirements.txt         # vacío a propósito: no hay dependencias
    │
    └── vision/                      # ◄── EL SISTEMA DE VISIÓN
        ├── README.md
        ├── configuracion.py         # carga y valida la configuración
        ├── config_vision.json       # toda la configuración, como datos
        ├── requirements.txt
        │
        ├── sources/                 # productor: de dónde salen las imágenes
        │   ├── fuente.py            #   la interfaz común (Cuadro, FuenteImagen)
        │   ├── camara.py            #   webcam USB real
        │   └── generador_sintetico.py   # imágenes de prueba con verdad conocida
        │
        ├── geometry/                # productor: píxeles → celdas
        │   ├── distorsion.py        #   corrección del lente + perfiles de cámara
        │   └── coordenadas.py       #   sistema de coordenadas por marcadores
        │
        ├── detectors/               # productor: qué hay y dónde
        │   └── rovers.py            #   rovers por su marcador: celda y ángulo
        │
        ├── tracking/                # productor: identidad y oclusión   (vacío)
        ├── publish/                 # consumidor: a la red              (vacío)
        ├── record/                  # consumidor: a disco               (vacío)
        │
        ├── tools/                   # herramientas de puesta a punto
        │   ├── diagnostico_camara.py    # ¿la cámara sirve?
        │   ├── patron_calibracion.py    # genera los PDF para imprimir
        │   ├── calibrar_camara.py       # mide la distorsión del lente
        │   ├── precision_ubicacion.py   # ¿ubica con error aceptable?
        │   ├── verificar_geometria.py   # coordenadas contra verdad conocida
        │   ├── verificar_rovers.py      # rovers contra verdad conocida
        │   └── panel.py                 # el panel que dibujan las demás
        │
        ├── calibraciones/           # DATOS: un perfil por cámara calibrada
        └── mediciones/              # DATOS: una sesión por prueba de precisión
```

Cada subcarpeta de `vision/` tiene su propio `README.md` que dice qué hay hoy y
qué está planificado.

**`calibraciones/` y `mediciones/` no son código ni configuración del sistema:**
son el resultado de medir **aparatos concretos**. Un perfil de calibración
describe un lente; una sesión de precisión describe cómo se portó una cámara
sobre una cancha. Por eso viven aparte de `config_vision.json`, que describe el
sistema y no los aparatos.

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

La ventaja escondida: **si alguien mueve la cámara, el sistema se reancla solo**
en el cuadro siguiente. Los marcadores no se movieron, así que las coordenadas
siguen significando lo mismo.

> No confundir esto con la **calibración de distorsión**, que es otra cosa y no
> hay que rehacerla: describe el **lente**, no dónde está puesta la cámara. Se
> mide una vez por aparato y sigue valiendo aunque la cámara se mueva.

Se usa el **centro** de cada marcador —no una esquina— porque es lo único que se
puede medir sin ambigüedad, tanto en una imagen como con una cinta métrica sobre
la cancha.

### Por qué el centro sale de cruzar las diagonales

Parece un detalle y no lo es. El centro de un marcador **no** es el promedio de
sus cuatro esquinas: es el **cruce de sus dos diagonales**.

Promediar es una operación afín, y mirar algo en perspectiva no lo es. Cuando la
cámara mira el tablero con algo de ángulo, el lado del marcador que quedó más
lejos se ve más chico, y el promedio de las cuatro esquinas se corre hacia el
lado que se ve más grande. El cruce de las diagonales, en cambio, **se conserva**:
una proyección manda rectas en rectas, así que manda las diagonales del cuadrado
impreso en las diagonales del cuadrilátero que se ve, y su punto de cruce en el
punto de cruce.

El sesgo **crece con el tamaño del marcador** —cuanta más superficie, más
perspectiva a lo ancho de la propia marca—, y por eso apareció recién al poner en
el generador sintético los marcadores de **100 mm** reales: con los 60 mm
nominales de antes quedaba escondido bajo el ruido. Medido con la cámara
inclinada, el centro se corría **1,37 px**; cruzando las diagonales quedan
**0,41 px**. Con más inclinación la diferencia se abre: a 0,30 son **7,4 px
contra 0,6**.

Importa porque esos cuatro centros son los que definen **todo** el sistema de
coordenadas: un sesgo ahí no afecta a un objeto, los corre a todos.

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

Eso instala OpenCV, NumPy y Pillow en un entorno aislado, sin tocar el Python
del sistema. La carpeta `.venv/` está ignorada por git.

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

### Poner a punto una cámara real

Cuatro etapas —diagnóstico, impresión del patrón, calibración de distorsión y
medición de precisión—, en un orden que no es arbitrario: cada una supone que
la anterior salió bien.

**El procedimiento completo, paso a paso, está en
[`PUESTA_A_PUNTO.md`](PUESTA_A_PUNTO.md)**, escrito para alguien que recibe la
cámara sin conocer el sistema. Los comandos exactos viven ahí y **solo ahí**,
para que no haya dos secuencias que puedan desincronizarse.

Acá quedan los enlaces según lo que necesites:

| Si querés… | Andá a |
|---|---|
| **Hacerlo**: los pasos, los comandos, qué mirar en pantalla | [`PUESTA_A_PUNTO.md`](PUESTA_A_PUNTO.md) |
| **Consultar** una herramienta: todas sus opciones y su porqué | [`vision/tools/README.md`](vision/tools/README.md) |
| **Entender** cómo funciona la corrección por dentro | [`vision/geometry/README.md`](vision/geometry/README.md) |

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
| **Captura real** (`vision/sources/`) | Lee la webcam USB en un hilo propio que **nunca bloquea**, con exposición, enfoque y balance de blancos fijos —y **verificados por efecto**, porque muchas cámaras aceptan el ajuste y siguen haciendo lo que quieren—. Incluye un menú para elegir qué cámara abrir. |
| **Geometría de esquinas** (`vision/geometry/`) | Detecta los 4 marcadores y convierte píxeles a celdas. Verificado contra la verdad del generador sintético, con los marcadores de **100 mm** reales: **exacto** con la cámara cenital y **0,44 mm** de error máximo con la cámara inclinada. El centro de cada marcador sale de **cruzar sus diagonales** y no de promediar sus esquinas (ver más abajo). |
| **Calibración de distorsión** (`vision/geometry/`) | Corrige la curvatura del lente gran angular. **Dos cámaras ya calibradas y verificadas**: ArgomTech CAM40 (1920×1080, 0,314 px) y Logitech C270 (1280×720, 0,206 px). |
| **Perfiles por cámara** (`vision/geometry/`) | Cada aparato guarda su propia calibración, y el sistema **avisa cuando el perfil no le corresponde** a la cámara conectada, en vez de corregir mal en silencio. |
| **Detección de rovers** (`vision/detectors/`) | Encuentra los rovers por su marcador y deduce su **celda y su ángulo**, calculados en celdas y no en píxeles porque la perspectiva no conserva los ángulos. Verificado contra la verdad del generador: **0,8 mm** de error de posición y **1,3°** de orientación con la cámara inclinada, sobre 36 rovers repartidos. |
| **Herramientas de puesta a punto** (`vision/tools/`) | Siete: diagnóstico de cámara, generación de los PDF para imprimir, calibración, verificación visual, verificación de geometría, verificación de rovers y medición de precisión. |

**Precisión medida sobre hardware real.** El criterio era **error máximo por
debajo de 10 mm** —un cubo mide 60 mm, así que 10 mm mantiene el objetivo dentro
del cubo—. Las dos cámaras quedaron muy por debajo:

| Cámara | Resolución | Error máximo | Error medio |
|---|---|---|---|
| Logitech C270 | 1280×720 | **1,01 mm** | 0,47 mm |
| ArgomTech CAM40 | 1920×1080 | **1,58 mm** | 0,75 mm |

La consecuencia práctica es que **la resolución no es el factor limitante**: 720p
ubica bien, así que la cámara se puede elegir por disponibilidad y precio.

### Todavía no existe

| Pieza | Qué falta |
|---|---|
| **Corrección de paralaje** (`geometry/`) | Los objetos altos se ven corridos hacia afuera; hay que compensarlo con la altura conocida. Ya se sabe **cuánto pesa** —la herramienta de precisión lo mide y lo descuenta—, pero todavía no es una etapa del flujo. |
| **Desfases marcador ↔ robot** (`detectors/`) | La estructura está y verificada, pero los dos desfases están **en cero**: el marcador está corrido del centro de giro del robot real y el frente son las paletas. Se miden con el propio sistema haciendo girar el robot en el lugar. |
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
- **Si te dieron una cámara y tenés que dejarla lista:** leé
  **[`PUESTA_A_PUNTO.md`](PUESTA_A_PUNTO.md)**. Te lleva de la mano desde
  imprimir las hojas hasta saber con cuántos milímetros de error ubica tu
  cámara. No hace falta que sepas nada del sistema por dentro.
- **Si vas a montar la cancha física:** leé **[`MONTAJE.md`](MONTAJE.md)**. Tiene
  la disposición exacta de los marcadores, la regla del margen blanco y una
  comprobación para hacer antes de la primera ronda. Pegar los marcadores en otro
  orden rota todas las coordenadas, y el sistema no se queja.

El trabajo va en la rama **`desarrollo`**; `main` queda como llegó del fork.
