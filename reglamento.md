# Reglamento

## Objetivo del reto

Desarrollar un sistema autónomo compuesto por dos robots tipo rover capaces de coordinarse para navegar una superficie delimitada, identificar objetos cúbicos de un color específico y transportarlos hasta una zona de acopio.

Una cámara superior proporcionará información global sobre la posición y orientación de los robots, los cubos, los obstáculos y las zonas de interés. A partir de esta información, el sistema deberá planificar rutas, distribuir tareas entre ambos robots y corregir sus movimientos durante la ejecución.

La solución deberá integrar robótica móvil, visión por computadora, comunicación inalámbrica, planificación de rutas e inteligencia artificial. Una vez iniciada la prueba, el sistema deberá operar sin intervención humana directa.

## Reglas del reto

### 1. Plataforma robótica

* Cada equipo utilizará los dos robots oficiales entregados por la organización.
* Los robots deberán utilizarse con su configuración física y electrónica original.
* No se permite modificar, sustituir, remover ni agregar componentes físicos o electrónicos.
* No se permite cambiar la tarjeta electrónica principal.
* No se permite sustituir el microcontrolador.
* No se permite utilizar otra tarjeta de desarrollo como controlador principal o auxiliar.
* No se permite modificar el chasis, los motores, las ruedas, los sensores ni el sistema de alimentación.
* No se permite agregar mecanismos de recolección, servomotores, estructuras impresas en 3D ni sensores adicionales.
* No se permite reemplazar los robots entregados por otra plataforma robótica.
* Se permite modificar únicamente el software y la programación de los robots.

### 2. Componentes incluidos en el robot

Cada robot será entregado completamente ensamblado e incluirá:

* Sensor ultrasónico para medición de distancia y detección de obstáculos.
* Acelerómetro para medir aceleraciones y cambios de movimiento.
* Giroscopio para estimar orientación, rotación y cambios angulares.
* Sensor de color para reconocer objetos cercanos.
* Sensores infrarrojos para detección de superficie cuadriculada.
* Motores y sistema de locomoción diferencial.
* Microcontrolador y tarjeta electrónica principal (ESP32 IdeaBoard).
* Sistema de alimentación baterías.
* Sistema de comunicación inalámbrica (capacidad del ESP32).

Los equipos deberán desarrollar sus soluciones utilizando exclusivamente las capacidades disponibles en esta plataforma.

### 3. Entrega de robots y materiales

* La organización entregará a cada equipo dos robots tipo rover sin costo.
* También proporcionará los materiales oficiales necesarios para ejecutar el reto.
* Los equipos no deberán comprar componentes para modificar los robots.
* Los cubos, obstáculos, marcadores visuales y demás elementos del escenario serán suministrados por la organización.
* La participación y el uso de los robots y materiales oficiales no tendrán costo para los equipos.

### 4. Programación de los robots

Los equipos podrán:

* Modificar el código ejecutado por el microcontrolador.
* Programar el movimiento de los motores.
* Procesar las mediciones de los sensores integrados.
* Implementar algoritmos de navegación y corrección de trayectoria.
* Desarrollar protocolos de comunicación entre los robots.
* Programar la recepción automática de instrucciones desde la computadora central.
* Implementar estrategias para empujar, orientar o transportar los cubos utilizando la estructura original del robot.

No se permitirá realizar cambios físicos para facilitar estas tareas.

### 5. Sistema de visión global

* Una cámara superior observará la totalidad de la superficie de competencia.
* El sistema deberá identificar la posición y orientación de cada robot.
* El sistema deberá detectar los cubos, los obstáculos y la zona de acopio.
* Los robots utilizarán marcadores visuales oficiales para diferenciarlos.
* La información visual podrá procesarse en una computadora externa.
* El sistema de visión deberá actualizar la información necesaria para corregir las trayectorias de los robots.

### 6. Computadora externa

Se permite utilizar una laptop, computadora de escritorio o mini PC para:

* Procesar las imágenes de la cámara.
* Construir una representación del entorno.
* Detectar y clasificar objetos.
* Calcular rutas.
* Distribuir tareas entre los robots.
* Evitar colisiones.
* Enviar instrucciones automáticas.
* Verificar y corregir la ejecución.

La computadora podrá utilizar algoritmos clásicos de visión por computadora, modelos de inteligencia artificial, servicios en la nube o modelos ejecutados localmente.

Durante la prueba, todas las decisiones y comunicaciones deberán generarse automáticamente.

### 7. Comunicación

* Los robots podrán comunicarse entre sí mediante el sistema inalámbrico incluido.
* Podrán intercambiar información sobre sus estados, tareas y movimientos.
* Podrán coordinar rutas y evitar colisiones.
* Podrán informar sobre la detección, transporte o entrega de objetos.
* También podrán recibir instrucciones automáticas desde la computadora central.
* No se permite enviar instrucciones manuales durante la ejecución.

### 8. Autonomía

Una vez iniciada la prueba:

* No se permite controlar los robots con teclado, teléfono, control remoto u otro dispositivo.
* No se permite tocar, mover o reorientar los robots.
* No se permite mover los cubos ni los obstáculos.
* No se permite modificar el código.
* No se permite reprogramar o reiniciar selectivamente los robots.
* No se permite enviar instrucciones humanas.
* No se permite corregir manualmente la posición de ningún elemento.

El sistema solamente podrá detenerse por razones de seguridad o por indicación de la organización.

Antes de iniciar la prueba se permitirá:

* Calibrar la cámara y los sensores.
* Verificar la comunicación.
* Ajustar los parámetros del sistema.
* Comprobar el funcionamiento de los robots.
* Colocar los robots en la posición inicial establecida.

### 9. Ejecución de la tarea

Los robots deberán:

* Iniciar desde la zona establecida.
* Identificar los objetos del color asignado.
* Navegar en la superficie.
* Coordinar sus movimientos.
* Evitar colisiones entre ellos.
* Localizar y aproximarse a los cubos.
* Empujar o transportar los cubos utilizando la estructura original del robot.
* Llevar los objetos hasta la zona de acopio.
* Corregir sus trayectorias utilizando la información de la cámara y de sus sensores integrados.

### 10. Restricciones técnicas

No se permite:

* Modificar físicamente los robots.
* Agregar o retirar sensores.
* Agregar actuadores.
* Agregar mecanismos de recolección.
* Cambiar motores, ruedas o baterías.
* Alterar el chasis.
* Incorporar tarjetas electrónicas adicionales.
* Sustituir la electrónica principal.
* Utilizar otro robot o plataforma.
* Dañar, perforar, cortar o alterar permanentemente los robots entregados.

Cualquier modificación física o electrónica no autorizada será motivo de descalificación técnica.

### 11. Penalizaciones y descalificación

Podrán aplicarse penalizaciones por:

* Intervención manual durante la prueba.
* Salida de la superficie de competencia.
* Incumplimiento de las condiciones de autonomía.

Serán causas de descalificación:

* Modificar física o electrónicamente un robot.
* Agregar o sustituir componentes.
* Cambiar el microcontrolador o la tarjeta principal.
* Utilizar una plataforma robótica diferente.
* Controlar manualmente los robots durante la ejecución.
* Incumplir las condiciones técnicas establecidas por la organización.


### 12. Criterio de éxito

El reto se considerará completado cuando los dos robots logren identificar, transportar y depositar correctamente los objetos asignados en la zona de acopio, utilizando únicamente su configuración original y operando de manera coordinada y autónoma.

Se valorará principalmente:

* El tiempo de ejecución.
* La cantidad de objetos correctamente entregados.

## Resumen de lo que NO se puede hacer

| Área                 | ❌ Lo que NO se puede hacer                         | Ejemplo                                            |
| -------------------- | -------------------------------------------------- | -------------------------------------------------- |
| **Hardware**         | Modificar físicamente los rovers                   | Cortar, perforar o alterar el robot                |
| **Chasis**           | Modificar el chasis original                       | Agregar una pala para empujar cubos                |
| **Componentes**      | Agregar componentes físicos                        | Añadir piezas impresas en 3D                       |
| **Componentes**      | Retirar componentes                                | Quitar un sensor para reducir peso                 |
| **Electrónica**      | Modificar la electrónica                           | Alterar la tarjeta principal                       |
| **Microcontrolador** | Sustituir el microcontrolador                      | Cambiar el ESP32 por otro controlador              |
| **Controladores**    | Agregar tarjetas de desarrollo                     | Incorporar Raspberry Pi, Arduino, otro ESP32, etc. |
| **Sensores**         | Agregar sensores                                   | Añadir LiDAR, cámara, ToF, encoders, etc.          |
| **Sensores**         | Sustituir sensores                                 | Cambiar el ultrasónico por otro modelo             |
| **Actuadores**       | Agregar actuadores                                 | Incorporar servomotores                            |
| **Manipulación**     | Agregar mecanismos de recolección                  | Pinzas, brazos, palas móviles                      |
| **Motores**          | Cambiar los motores                                | Instalar motores más rápidos                       |
| **Ruedas**           | Cambiar las ruedas                                 | Usar ruedas de mayor diámetro                      |
| **Baterías**         | Cambiar el sistema de alimentación                 | Usar una batería diferente                         |
| **Robot**            | Utilizar otra plataforma                           | Competir con un rover diseñado por el equipo       |
| **Control humano**   | Controlar manualmente los robots durante la prueba | Teclado, joystick, teléfono o control remoto       |
| **Intervención**     | Tocar los robots durante la ejecución              | Reorientar un rover que quedó mal colocado         |
| **Objetos**          | Mover manualmente cubos u otros elementos          | Corregir la posición de un cubo                    |
| **Software**         | Modificar el código durante la prueba              | Corregir un programa después de iniciar            |
| **Robot**            | Reprogramarlo durante la prueba                    | Subir nuevo firmware al ESP32                      |
| **Robot**            | Reiniciarlo selectivamente durante la ejecución    | Resetear un rover que dejó de responder            |
| **Comandos**         | Enviar instrucciones humanas                       | Decidir manualmente que Rover 1 vaya al cubo rojo  |
| **Autonomía**        | Tomar decisiones humanas después de iniciar        | Cambiar rutas o asignaciones manualmente           |


