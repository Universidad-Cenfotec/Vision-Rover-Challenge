# Criterio de dificultad para la distribución de cubos

> [Generador de posición inicial de cubos](https://universidad-cenfotec.github.io/Vision-Rover-Challenge/)

## 1. Objetivo

La aplicación genera escenarios aleatorios para el Vision Rover Challenge, distribuyendo tres cubos de colores rojo, azul y verde sobre un tablero de 50 × 50 casillas, con un área efectiva interior de 40 × 40 casillas.

Cada cubo ocupa un espacio de 3 × 3 casillas y debe ser transportado por uno de los dos robots hasta su zona de acopio correspondiente.

Las zonas de acopio están ubicadas de la siguiente manera:

* **Rojo:** Centro del borde superior.
* **Verde:** Centro del borde izquierdo.
* **Azul:** Centro del borde derecho.
* **Robots:** Dos posiciones de partida en el borde inferior.

La aplicación permite seleccionar un nivel de dificultad $D$ entre 0 y 1.

$$
D \in [0,1]
$$

La dificultad se determina mediante dos factores principales:

1. La distancia de cada cubo a su zona de acopio.
2. La posibilidad de interferencia entre las trayectorias de transporte de los cubos.

Un valor cercano a 0 genera escenarios con cubos próximos a sus zonas de acopio y pocas interferencias entre trayectorias. Un valor cercano a 1 genera escenarios con mayores distancias y más posibilidades de interferencia entre las rutas de transporte.

---

## 2. Distancia a las zonas de acopio

Para cada cubo se calcula la distancia Manhattan entre su centro y el centro de su zona de acopio correspondiente.

$$
d_i = |x_i-x_{a_i}|+|y_i-y_{a_i}|
$$

Donde:

* $(x_i,y_i)$ representa el centro del cubo.
* $(x_{a_i},y_{a_i})$ representa el centro de su zona de acopio.
* $d_i$ es la distancia del cubo $i$ a su zona de acopio, expresada en casillas.

La distancia media de los tres cubos se calcula mediante:

$$
\overline{d}=\frac{d_1+d_2+d_3}{3}
$$

La aplicación utiliza el nivel de dificultad para establecer una distancia media objetivo:

$$
d_{\text{objetivo}}=6.5+35D
$$

Por lo tanto, a mayor dificultad, mayor es la distancia media que se busca entre los cubos y sus zonas de acopio.

Esta distancia es una estimación geométrica y no representa necesariamente la longitud de la trayectoria real que recorrerá cada robot.

---

## 3. Interferencia entre trayectorias

Para estimar la posibilidad de interferencia entre los robots, la aplicación considera una trayectoria recta desde el centro de cada cubo hasta el centro de su zona de acopio.

Se comparan las tres parejas posibles de trayectorias:

* Rojo y azul.
* Rojo y verde.
* Azul y verde.

Se considera que existe una posible interferencia cuando dos trayectorias se cruzan geométricamente o cuando la distancia mínima entre ellas es inferior a 4 casillas.

La cantidad de parejas de trayectorias con interferencia puede variar entre 0 y 3.

El nivel de dificultad establece el siguiente objetivo:

| Dificultad seleccionada | Interferencias objetivo |
| ----------------------- | ----------------------: |
| $0.00 \leq D < 0.28$    |                       0 |
| $0.28 \leq D < 0.53$    |                       1 |
| $0.53 \leq D < 0.77$    |                       2 |
| $0.77 \leq D \leq 1.00$ |                       3 |

Este criterio favorece escenarios en los cuales los robots podrían necesitar coordinar sus movimientos, esperar, modificar sus trayectorias o evitar interferencias durante el transporte de los cubos.

Las interferencias se calculan a partir de trayectorias geométricas de referencia. No constituyen una predicción de colisiones reales ni consideran la asignación de cubos a los robots, sus dimensiones físicas, velocidades o estrategias de navegación.

---

## 4. Generación aleatoria de escenarios

La aplicación genera múltiples distribuciones candidatas de los tres cubos.

Las posiciones iniciales de estas distribuciones se obtienen mediante una combinación de coordenadas de referencia, el nivel de dificultad seleccionado y una perturbación aleatoria.

Cada distribución válida se evalúa mediante una función de pérdida:

$$
L=0.55L_d+0.45L_c+\epsilon
$$

Donde:

$$
L_d=\frac{|\overline{d}-d_{\text{objetivo}}|}{36}
$$

$$
L_c=\frac{|C-C_{\text{objetivo}}|}{3}
$$

En estas expresiones:

* $L_d$ mide la diferencia entre la distancia media obtenida y la distancia objetivo.
* $L_c$ mide la diferencia entre las interferencias obtenidas y las interferencias objetivo.
* $C$ representa el número de parejas de trayectorias con interferencia.
* $C_{\text{objetivo}}$ representa la cantidad de interferencias buscada para el nivel de dificultad seleccionado.
* $\epsilon$ es una pequeña perturbación aleatoria entre 0 y 0.06 que introduce variabilidad entre escenarios.

La función asigna un peso del 55 % al criterio de distancia y un 45 % al criterio de interferencia.

La aplicación evalúa hasta 700 distribuciones candidatas y selecciona aquella que obtiene la menor pérdida entre las distribuciones válidas evaluadas.

**El nivel de dificultad es un objetivo de generación y no una garantía de que todas las distribuciones presenten exactamente la misma distancia o cantidad de interferencias.**

---

## 5. Restricciones de ubicación de los cubos

Independientemente del nivel de dificultad seleccionado, todas las distribuciones generadas deben cumplir las siguientes restricciones:

* Cada cubo ocupa exactamente 3 × 3 casillas.
* Los tres cubos deben permanecer completamente dentro del área efectiva de 40 × 40 casillas.
* Los cubos no pueden superponerse entre sí.
* Debe existir una separación mínima de 2 casillas libres entre los cubos, incluyendo las aproximaciones diagonales.
* Los cubos no pueden superponerse con las zonas de acopio ni con las posiciones iniciales de los robots.

Estas restricciones se aplican tanto durante la generación automática como durante el desplazamiento manual de los cubos en la aplicación.

---

## 6. Interpretación de la dificultad

El nivel de dificultad representa una estimación de la complejidad espacial del escenario, basada en la distancia de transporte y la interferencia geométrica entre las trayectorias.

Un escenario de dificultad elevada puede requerir una mayor coordinación entre los robots, estrategias de asignación de tareas y planificación de movimientos para completar el transporte de los cubos.

Sin embargo, la dificultad real también depende de factores que no forman parte del generador, como las dimensiones y capacidades de los robots, su velocidad, el algoritmo de navegación, la estrategia de asignación de cubos y la comunicación entre ellos.

**El nivel de dificultad permite generar escenarios con diferentes condiciones espaciales, pero no representa una medida absoluta del tiempo necesario para completar el reto ni de la probabilidad de éxito de los robots.**
