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

Consecuencia práctica, ya medida: la corrección de paralaje —que **ya existe**,
en [`../geometry/`](../geometry/README.md)— baja el error de posición de 41 mm a
0,9 mm y **deja la orientación igual**. Se le pasa a `detectar_rovers` como
`pose_de_camara`.

Es opcional a propósito, y no un descuido: hay un caso legítimo sin pose —
`medir_desfases` necesita la pose **cruda** del marcador para poder calibrar.

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
| `desfase_marcador_a_centro_mm` | vector del centro del marcador al centro de rotación, en **adelante / izquierda** | ⚠️ en cero, **sin medir**: los dos intentos fallaron porque el robot se trasladó mientras giraba |
| `desfase_angular_grados` | del ángulo del marcador al frente del robot | ✅ en cero por **medición confirmada**: dos sesiones dieron +0,18° y −0,50° |

Los dos están en cero, pero **por razones distintas**, y la diferencia importa.
El detalle de cada uno está en las notas de `config_vision.json`.

**El desfase de posición va en el marco del robot y no en coordenadas de la
cancha**, porque es solidario al robot y el robot gira: un `(col, row)` fijo solo
sería correcto para una orientación. El detector lo rota por el ángulo detectado
antes de sumarlo.

**El de posición está en cero porque todavía no se midió, no porque el robot real
no lo tenga.** Se mide con el propio sistema: haciendo **girar el robot sobre su
eje** y mirando la posición que reporta la visión. Si el marcador estuviera sobre
el centro de rotación, el punto reportado se quedaría quieto; como está corrido,
describe una **circunferencia** cuyo radio es el módulo del desfase y cuyo centro
es el centro de rotación real. El procedimiento completo está en las notas de
`config_vision.json`.

### `cubos.py` — detección de cubos por color

**Cubos:** 6 cm, identidad por **color** (`green`, `blue`, `red`). No hay dos del
mismo color, así que el color alcanza para identificarlos.

> **Los obstáculos no entran en esta primera edición del reto.** El campo
> `obstacles` del contrato **sigue existiendo** y se emite como lista vacía: eso
> no es un cambio de formato y no obliga a los equipos a tocar nada. El
> **amarillo sigue reservado** de todas formas, para que ningún objeto amarillo
> que ande por ahí se lea como cubo.

**Verificado** con `python -m vision.tools.verificar_cubos`: **1,05 mm** con los
cubos despejados y **4,88 mm** con un rover empujando uno y tapándole el 22 %,
con la cámara inclinada. El centroide ingenuo —el método que se descartó— da 9,84
y 17,01 mm respectivamente.

El método: **segmentar por croma** en Lab y clasificar por **matiz**, no HSV.

**Por qué saturación:** el tablero es acromático —grises, blancos, negros—, así
que cualquier cosa con color saturado es, por definición, un objeto de interés.
Es un filtro que separa el fondo del contenido casi gratis.

**Por qué Lab y no HSV:** el matiz de HSV se vuelve inestable justo donde más
importa —con poca saturación o poca luz— y da saltos entre valores extremos. Lab
separa la luminosidad del color de forma más pareja, así que un cubo rojo a la
sombra se sigue pareciendo a un cubo rojo.

**Por qué el matiz y no la distancia a un color de referencia:** el matiz es casi
invariante a la iluminación y a lo saturado que sea el plástico. Por eso **no
hizo falta medir los cubos reales** antes de escribir el detector: los tres
colores del reto están de **94° a 170°** entre sí, y el único par ajustado es
verde–amarillo, a 33°.

#### El límite, declarado en vez de escondido

Con el **70 %** del cubo tapado el ajuste llega a errar 34 mm, **más que el
centroide ingenuo**: cuando se le acaba la evidencia, el método se degrada feo.

No se relajó el umbral. El residuo del ajuste resultó un autodiagnóstico limpio
—0,014 despejado, 0,133 con el 22 % tapado, 0,28 con el 70 %— y de esos números
sale el umbral, no de la intuición. `CuboDetectado` lleva `confiable`, y lo que
se verifica en ese escenario no es que **acierte** sino que **no mienta**.

Un cubo marcado como no confiable es trabajo de
[`../tracking/`](../tracking/README.md), que conserva su última posición buena
con la edad creciendo — que es lo que manda el contrato para un objeto ocluido.

#### El cubo se ubica por su borde inferior, no por el centro de la mancha

Lo que la cámara ve de un cubo no es una cara: es la **tapa más una o dos caras
laterales**. El centroide de esa mancha está a una altura efectiva intermedia,
que además **cambia según dónde esté el cubo** en la cancha.

Por eso el cubo se ubica por su **borde inferior**, la línea donde apoya en el
piso. Un punto en el piso está a **altura cero**, así que el factor de paralaje
`(H−h)/H` vale exactamente **1**: no hay nada que corregir, y la homografía del
tablero es exacta ahí por construcción. **La posición del cubo no depende de
dónde ni a qué altura esté montada la cámara.**

**Pero el borde no es el centro, y el contrato publica el centro.** El punto más
bajo de la mancha es una esquina de la base, y el centro está entre 30 y 42 mm de
ahí según cómo esté rotado el cubo — tres a cuatro veces el umbral de 10 mm.

La forma correcta es trabajar **en celdas y no en píxeles**, igual que en la
detección de rovers. Al pasar el contorno por la homografía, lo que está en el
piso cae exactamente donde está y lo que tiene altura cae corrido **hacia afuera
del punto bajo la cámara**. Entonces el borde de la mancha que **mira hacia el
nadir** son las dos aristas de la base. Como la huella es un cuadrado de 60 mm
conocido, ajustar esas dos aristas perpendiculares reconstruye el cuadrado, y el
centro queda a medio lado hacia adentro de cada una.

Las medidas físicas de los cubos ya están registradas en `config_vision.json`,
bajo `elementos.cubos`.
