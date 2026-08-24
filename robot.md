<img src="https://github.com/Universidad-Cenfotec/Vision-Rover-Challenge/blob/main/Cenfobot_Rover.jpeg" alt="Robot del proyecto" width="900">

## Que se les entrega

<p align="center">
  <a href="https://youtu.be/GQzHki5-4RM">
    <img src="https://img.youtube.com/vi/GQzHki5-4RM/maxresdefault.jpg" width="600">
  </a>
  <br>
  <a href="https://youtu.be/GQzHki5-4RM"><b>▶ Ver video en YouTube</b></a>
</p>

- 2 kits de CenfoBot
- 3 cubos (rojo, azul y verde)
- Webcam
- Superficie cuadriculada de 1m x 1m

## Componetes del kit de CenfoBot

<p align="center">
  <a href="https://youtu.be/gN2MMhoahYY">
    <img src="https://img.youtube.com/vi/gN2MMhoahYY/maxresdefault.jpg" width="600">
  </a>
  <br>
  <a href="https://youtu.be/gN2MMhoahYY"><b>▶ Ver video en YouTube</b></a>
</p>

## Especificaciones de los robots

Cada equipo participante recibirá **dos robots tipo rover**, construidos a partir de una versión modificada de la plataforma educativa Sumobot. Ambos robots deberán trabajar de manera coordinada para localizar, recolectar y transportar objetos cúbicos dentro del espacio de competencia.

### Plataforma base

Los robots utilizarán la plataforma oficial Sumobot proporcionada por la organización. La tarjeta electrónica principal y el microcontrolador incluidos en el robot deberán mantenerse como el núcleo del sistema de control.

No se permite:

* Sustituir la tarjeta electrónica principal.
* Cambiar el microcontrolador original.
* Utilizar otra tarjeta de desarrollo como controlador principal.
* Reemplazar completamente la plataforma por otro robot comercial o construido desde cero.

Solamente se permite modificar el código.

### Capacidades de movimiento

Cada robot contará con un sistema de locomoción diferencial compuesto por dos motores independientes. Esto permitirá ejecutar movimientos como:

* Avance y retroceso.
* Giro sobre su propio eje.
* Correcciones de trayectoria.
* Aproximación a objetos.
* Transporte o empuje de cubos.
* Navegación coordinada con el segundo robot.

Los equipos deberán desarrollar el software de control necesario para convertir las instrucciones generadas por el sistema de navegación en movimientos precisos del rover.

### Comunicación inalámbrica

Los robots podrán comunicarse entre sí mediante **ESP-NOW** u otro mecanismo inalámbrico compatible con la plataforma oficial.

La comunicación podrá utilizarse para:

* Distribuir tareas entre los robots.
* Compartir estados y posiciones.
* Evitar colisiones.
* Informar sobre objetos localizados.
* Confirmar la recolección o entrega de un objeto.
* Coordinar movimientos simultáneos.


### Identificación mediante visión global

Cada rover contará un marcador visual que permita al sistema de visión global determinar:

* La identidad del robot.
* Su posición dentro de la superficie.
* Su orientación.
* Su trayectoria.
* Su cercanía a obstáculos, cubos y otros robots.

### Sistema de recolección

El rover cuenta con dos paletas laterales que permiten arrastrar y mover los objetos lateralmente

### Sensores y componentes adicionales

El robot cuenta con:

* Sensores ultrasónicos.
* Sensores infrarrojos.
* Sensores de color.
* Acelerómetro y giroscopio

### Procesamiento externo

La universidad CENFOTEC creará el sistema de visión por computadora y publicará los detalles en este repositorio. Los participantes utilizarán este sistema y este no puede ser modificado.

### Autonomía

Una vez iniciada la prueba, los robots deberán operar de manera completamente autónoma.

No se permitirá:

* Controlar los robots con teclado, teléfono o control remoto.
* Mover manualmente los robots.
* Reubicar objetos durante la ejecución.
* Enviar instrucciones humanas.
* Modificar o reprogramar el sistema después de iniciar la prueba.

Antes de la competencia se permitirá realizar procesos de calibración, verificación de comunicación y ajuste del sistema de visión.

## Entrega de robots y materiales

La organización entregará a cada equipo participante, **sin costo**, los robots y los materiales base necesarios para desarrollar el reto.

El kit podrá incluir:

* Dos robots tipo rover basados en la plataforma Sumobot.
* Cámara web
* Superficie de navegación

Los equipos no deberán pagar por la inscripción, los robots ni los materiales oficiales entregados para participar.

## Responsabilidad de los equipos

Cada equipo será responsable de:

* Programar los dos robots.
* Diseñar la estrategia de coordinación.
* Mantener un registro del costo de los componentes adicionales.
* Entregar el código fuente y la documentación técnica.
* Presentar una demostración autónoma y funcional.

Los robots y materiales proporcionados deberán utilizarse exclusivamente para el desarrollo y ejecución del reto, siguiendo las normas de seguridad y uso definidas por la organización.
