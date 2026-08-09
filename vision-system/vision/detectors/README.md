# detectors/

**Productor.** Encuentra qué hay en la cancha y dónde. **Solo detecta; no
decide**: informa lo que ve, sin interpretar ni corregir.

## Lo que ya existe

### `rovers.py` — detección de rovers

Recibe los marcadores ArUco ya detectados en un cuadro y el sistema de
coordenadas de [`../geometry/`](../geometry/README.md), y devuelve dónde está y
hacia dónde apunta cada rover.

No recuerda cuadros anteriores, no calcula edades y no decide si un rover
desapareció: eso es seguimiento y va en [`../tracking/`](../tracking/README.md).

**Verificado** contra la verdad del generador sintético con
`python -m vision.tools.verificar_rovers`: error de posición **≤ 0,8 mm** y de
orientación **≤ 1,3°** con la cámara inclinada, sobre 36 rovers repartidos por
toda la cancha.

#### Cómo se separan los rovers de las esquinas

No hay una lista de "IDs de rover". La regla es al revés: **es rover todo
marcador que no sea una esquina**, y las esquinas son las que declara
`marcadores_esquina.disposicion` en la configuración.

Una lista de rovers habría que mantenerla sincronizada con los marcadores que se
peguen de verdad, y el día que no lo estuviera, un rover dejaría de existir sin
que nada avisara. Con esta regla, un marcador nuevo aparece solo.

La única excepción es `ids_ignorados`, que **arranca vacío**. Existe para un caso
concreto: el marcador ID 20 de la prueba de precisión es un objeto físico real y
podría quedar olvidado sobre la cancha. Arranca vacío porque descartar en
silencio un marcador que sí es un rover es peor que reportar uno de más, que al
menos se ve.

#### Por qué todo se calcula en celdas y no en píxeles

Es el punto que más importa de este módulo. **Bajo perspectiva los ángulos no se
conservan:** dos rovers con la misma orientación real, uno en el centro y otro
en un borde, se ven en la imagen con inclinaciones distintas. Medir el ángulo en
píxeles daría un número que cambia según dónde esté el rover.

La homografía manda el plano del tablero a celdas de forma exacta, así que en el
espacio de celdas el marcador vuelve a ser un cuadrado y su ángulo vuelve a
significar lo que tiene que significar. Por eso las cuatro esquinas se convierten
a celdas **primero**, y todo lo demás se calcula ahí.

El centro sale de `centro_de`, la misma función que usan los marcadores de
esquina: **cruzar las diagonales**, no promediar. Una sola definición de "centro"
en todo el sistema.

#### El paralaje no afecta la orientación

El marcador del rover está a 90 mm sobre el tablero, así que no está en el plano
que define la homografía y aparece **corrido hacia afuera**. Pero como su plano
es **paralelo** al del tablero, esa deformación es una homotecia —un
agrandamiento alrededor del punto que está bajo la cámara— y una homotecia
**conserva las direcciones**.

Consecuencia práctica: la corrección de paralaje, cuando llegue, va a mover la
**posición** del rover. Su **orientación** ya está bien hoy.

#### Los dos desfases marcador ↔ robot

Lo que se detecta es la pose del **marcador**. Lo que el contrato publica es la
pose del **robot**. No son la misma cosa: el marcador está pegado en algún lugar
del robot, casi nunca sobre su centro de rotación ni perfectamente alineado con
el frente (las paletas).

Por eso `RoverDetectado` lleva las dos: `col`/`row`/`theta_grados` son del
**robot**, y `marcador` conserva la medición cruda —que es lo único que el
sistema mide de verdad, y lo que hace falta para **calibrar** los desfases.

| Desfase | Qué es | Estado |
|---|---|---|
| `desfase_marcador_a_centro_mm` | vector del centro del marcador al centro de rotación, en **adelante / izquierda** | ⚠️ en cero, sin medir |
| `desfase_angular_grados` | del ángulo del marcador al frente del robot | ⚠️ en cero, sin medir |

**El desfase de posición va en el marco del robot y no en coordenadas de la
cancha**, porque es solidario al robot y el robot gira: un `(col, row)` fijo solo
sería correcto para una orientación. El detector lo rota por el ángulo detectado
antes de sumarlo.

**Están en cero porque todavía no se midieron, no porque el robot real no los
tenga.** Se van a medir con el propio sistema: haciendo **girar el robot sobre su
eje** y mirando la posición que reporta la visión. Si el marcador estuviera sobre
el centro de rotación, el punto reportado se quedaría quieto; como está corrido,
describe una **circunferencia** cuyo radio es el módulo del desfase y cuyo centro
es el centro de rotación real. El procedimiento completo está en las notas de
`config_vision.json`.

## Lo que todavía NO existe

### Detección de cubos y obstáculos por color

- **Cubos:** 6 cm, identidad por **color** (`green`, `blue`, `red`). No hay dos
  del mismo color, así que el color alcanza para identificarlos.
- **Obstáculos:** bloques **amarillos** de 10 cm. El **amarillo está reservado**:
  un objeto amarillo nunca es un cubo.

El método decidido: **segmentar por saturación** y clasificar en espacio **Lab**,
no HSV.

**Por qué saturación:** el tablero es acromático —grises, blancos, negros—, así
que cualquier cosa con color saturado es, por definición, un objeto de interés.
Es un filtro que separa el fondo del contenido casi gratis.

**Por qué Lab y no HSV:** el matiz de HSV se vuelve inestable justo donde más
importa —con poca saturación o poca luz— y da saltos entre valores extremos. Lab
separa la luminosidad del color de forma más pareja, así que un cubo rojo a la
sombra se sigue pareciendo a un cubo rojo.

Las medidas físicas de los cubos ya están registradas en `config_vision.json`,
bajo `elementos.cubos`.
