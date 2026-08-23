# Códigos ArUco

## ¿Qué es ArUco?

Los **códigos ArUco** son marcadores visuales cuadrados formados por un patrón binario en blanco y negro. Cada marcador contiene un **identificador numérico único (ID)** que puede ser detectado por una cámara mediante técnicas de visión por computadora.

Además de reconocer el ID del marcador, un sistema de visión puede determinar su **posición y orientación dentro de la imagen**. Si la cámara está calibrada y se conoce el tamaño físico del marcador, también es posible utilizarlo como referencia para estimar posiciones y distancias en el espacio.

En el **Vision Rover Challenge**, los marcadores ArUco se utilizan con dos propósitos diferentes:

* Los marcadores grandes de **10 cm**, con identificadores del **0 al 3**, se colocan en las **cuatro esquinas del área de trabajo** y permiten al sistema de visión establecer una referencia espacial del tablero.
* Los marcadores pequeños de **40 mm**, con identificadores **10 y 11**, se colocan sobre los **rovers** y permiten identificar y localizar independientemente cada robot.

## Archivos disponibles

| Archivo                            | ID ArUco | Tamaño | Uso                                                         |
| ---------------------------------- | -------: | -----: | ----------------------------------------------------------- |
| `aruco_id0_negro10cm.pdf`          |        0 |  10 cm | Marcador de referencia para una esquina del área de trabajo |
| `aruco_id1_negro10cm.pdf`          |        1 |  10 cm | Marcador de referencia para una esquina del área de trabajo |
| `aruco_id2_negro10cm.pdf`          |        2 |  10 cm | Marcador de referencia para una esquina del área de trabajo |
| `aruco_id3_negro10cm.pdf`          |        3 |  10 cm | Marcador de referencia para una esquina del área de trabajo |
| `aruco_robot_id10_negro40mm-1.pdf` |       10 |  40 mm | Identificador del **Rover 1**                               |
| `aruco_robot_id11_negro40mm.pdf`   |       11 |  40 mm | Identificador del **Rover 2**                               |

## Marcadores de las esquinas

Los códigos **0, 1, 2 y 3** funcionan como puntos de referencia fijos. Al detectar simultáneamente estos cuatro marcadores, el sistema de visión puede reconocer los límites del área de trabajo y establecer un sistema de coordenadas sobre el tablero.

Estos marcadores tienen un tamaño de **10 × 10 cm** para facilitar su detección desde la cámara ubicada sobre el área del reto.

## Marcadores de los rovers

Cada rover lleva un marcador ArUco diferente:

* **ID 10 → Rover 1**
* **ID 11 → Rover 2**

Estos marcadores tienen un tamaño de **40 × 40 mm**, adecuado para colocarlos sobre la parte superior de cada rover.

La cámara puede utilizar estos códigos para determinar continuamente **qué rover está observando, dónde se encuentra y cuál es su orientación**. Esto permite realizar el seguimiento de ambos robots dentro del área del Vision Rover Challenge.

> **Importante:** al imprimir los archivos PDF se recomienda utilizar **tamaño real o escala 100 %**, sin utilizar opciones como “ajustar a página”, para conservar las dimensiones de 10 cm y 40 mm de los marcadores.
