# Reglamento

## Objetivo del reto

Desarrollar un sistema autónomo compuesto por dos robots tipo rover capaces de coordinarse para navegar una superficie delimitada, identificar objetos cúbicos de un color específico y transportarlos hasta una zona de acopio.

Una cámara superior y el sistema oficial de visión proporcionarán información global sobre la posición y orientación de los robots, la posición de los cubos, las zonas de acopio y el estado general de la prueba. A partir de esta información, los rovers deberán interpretar el entorno, distribuir tareas, planificar sus movimientos, coordinarse y corregir su comportamiento durante la ejecución.

La solución deberá integrar robótica móvil, comunicación inalámbrica, planificación de rutas, coordinación entre robots, control y autonomía. Una vez iniciada la prueba, los rovers deberán operar sin intervención humana y sin que una computadora externa, servicio en la nube u otro dispositivo externo tome decisiones o modifique su planificación en tiempo real.

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
* Sensores infrarrojos para detección de la superficie cuadriculada.
* Motores y sistema de locomoción diferencial.
* Microcontrolador y tarjeta electrónica principal ESP32 IdeaBoard.
* Sistema de alimentación por baterías.
* Sistema de comunicación inalámbrica disponible en el ESP32.

Los equipos deberán desarrollar sus soluciones utilizando exclusivamente las capacidades disponibles en esta plataforma.

### 3. Entrega de robots y materiales

* La organización entregará a cada equipo dos robots tipo rover sin costo.
* También proporcionará los materiales oficiales necesarios para ejecutar el reto.
* Los equipos no deberán comprar componentes para modificar los robots.
* Los cubos, marcadores visuales, superficie de competencia y demás elementos oficiales del escenario serán suministrados por la organización.
* La participación y el uso de los robots y materiales oficiales no tendrán costo para los equipos.

### 4. Programación de los robots

Los equipos podrán:

* Modificar el código ejecutado por el microcontrolador.
* Programar el movimiento de los motores.
* Procesar las mediciones de los sensores integrados.
* Recibir y procesar la telemetría publicada por el sistema oficial de visión.
* Implementar algoritmos de navegación y corrección de trayectoria.
* Implementar algoritmos de asignación de tareas entre los dos rovers.
* Desarrollar protocolos de comunicación entre los robots.
* Implementar estrategias para evitar colisiones.
* Implementar estrategias para empujar, orientar o transportar los cubos utilizando la estructura original del robot.
* Utilizar los lenguajes, bibliotecas y herramientas de software que consideren apropiados, siempre que sean compatibles con el hardware oficial y respeten las condiciones de autonomía del reto.

La lógica necesaria para tomar decisiones durante una ronda deberá estar cargada y ejecutarse en los rovers.

No se permitirá realizar cambios físicos para facilitar estas tareas.

### 5. Sistema de visión global

* Una cámara superior observará la superficie de competencia.
* El sistema oficial de visión será proporcionado por la organización.
* El sistema de visión determinará la posición y orientación de cada rover.
* El sistema de visión determinará la posición de los cubos y proporcionará las zonas de acopio definidas para la ronda.
* Los rovers utilizarán marcadores visuales oficiales para ser identificados por el sistema.
* El sistema de visión publicará telemetría en tiempo real para que los rovers puedan conocer el estado global del entorno.
* El sistema oficial de visión no deberá ser modificado por los equipos durante la competencia.
* La telemetría deberá interpretarse según el contrato oficial publicado en el repositorio del Vision Rover Challenge.

El sistema de visión proporciona percepción global del entorno, pero no proporciona la estrategia, las rutas ni las decisiones de los equipos.

### 6. Uso de computadoras externas y servicios en la nube

Durante el desarrollo, preparación y pruebas, los equipos podrán utilizar laptops, computadoras de escritorio, mini PC, servicios en la nube, modelos de inteligencia artificial, simuladores y otras herramientas para:

* Desarrollar y depurar código.
* Simular escenarios.
* Analizar datos.
* Diseñar y evaluar estrategias.
* Generar planes o parámetros que posteriormente sean cargados en los rovers.
* Configurar direcciones IP, direcciones MAC y parámetros de comunicación.
* Verificar el funcionamiento de los robots y su conexión con el sistema de visión.

Una vez iniciada una ronda oficial:

* No se permite que una computadora externa calcule nuevas rutas para los robots.
* No se permite que una computadora externa distribuya o reasigne tareas entre los robots.
* No se permite que una computadora externa tome decisiones de navegación.
* No se permite que una computadora externa genere comandos de movimiento.
* No se permite que un servicio en la nube modifique la estrategia o planificación de los robots en tiempo real.
* No se permite enviar cambios de planificación desde un dispositivo externo.
* No se permite utilizar una computadora, teléfono u otro dispositivo como sistema de control remoto, aunque los comandos sean generados automáticamente.

La computadora utilizada por la organización para ejecutar el sistema oficial de visión no se considera parte del sistema de control del equipo. Su función es únicamente observar el entorno y publicar telemetría.

### 7. Comunicación

* Los rovers recibirán información del sistema oficial de visión mediante la red definida por la organización y de acuerdo con el contrato de telemetría.
* Los robots podrán comunicarse entre sí mediante los mecanismos inalámbricos disponibles en el hardware oficial.
* Los rovers podrán intercambiar información sobre sus estados, tareas y movimientos.
* Podrán coordinar rutas y evitar colisiones.
* Podrán informar entre ellos sobre la detección, transporte o entrega de objetos.
* Las decisiones de coordinación deberán producirse de manera autónoma en los rovers.
* No se permite enviar instrucciones humanas durante la ejecución.
* No se permite utilizar una computadora externa como intermediario para tomar decisiones o controlar los rovers durante una ronda.

Los equipos deberán trabajar con el estado más reciente disponible de la telemetría y evitar ejecutar decisiones basadas en una cola de estados antiguos. Los campos de secuencia, tiempo y antigüedad definidos en el contrato de telemetría pueden utilizarse para determinar la vigencia de los datos recibidos.

### 8. Autonomía

Una vez iniciada la prueba:

* No se permite controlar los robots con teclado, teléfono, control remoto u otro dispositivo.
* No se permite tocar, mover o reorientar los robots.
* No se permite mover manualmente los cubos ni otros elementos del escenario.
* No se permite modificar el código.
* No se permite reprogramar o reiniciar selectivamente los robots.
* No se permite enviar instrucciones humanas.
* No se permite corregir manualmente la posición de ningún elemento.
* No se permite modificar externamente la estrategia, asignación de tareas, rutas o comandos de movimiento.
* No se permite utilizar lógica externa en una laptop, computadora, teléfono o servicio en la nube para alterar el comportamiento de los rovers en tiempo real.

El sistema solamente podrá detenerse por razones de seguridad o por indicación de la organización.

Antes de iniciar la prueba se permitirá:

* Calibrar la cámara y los sensores.
* Verificar la comunicación.
* Ajustar los parámetros del sistema.
* Comprobar el funcionamiento de los robots.
* Configurar direcciones IP, direcciones MAC u otros parámetros de red.
* Cargar el software y los planes previamente desarrollados en los rovers.
* Colocar los robots en la posición inicial establecida.

### 9. Inicio y finalización de la ronda

El inicio de cada ronda será indicado por un juez.

Los robots deberán estar previamente encendidos, programados y preparados para iniciar la ejecución. El equipo podrá utilizar el botón de arranque disponible en la IdeaBoard para iniciar la ejecución al recibir la señal del juez, evitando reiniciar innecesariamente el intérprete o el microcontrolador.

A partir de la señal oficial de inicio se aplican todas las restricciones de autonomía definidas en este reglamento.

La ronda finalizará cuando:

* el último cubo requerido se encuentre completamente dentro de su zona de acopio correspondiente;
* se alcance el tiempo máximo definido por la organización;
* el juez detenga la ronda por razones de seguridad o por incumplimiento del reglamento.

La posición final de los rovers no forma parte de la condición de éxito una vez que todos los cubos requeridos hayan sido depositados correctamente.

El tiempo máximo disponible para cada ronda será comunicado oficialmente por la organización antes de la competencia.

### 10. Ejecución de la tarea

Los robots deberán:

* Iniciar desde la zona establecida.
* Interpretar la información recibida del sistema oficial de visión.
* Identificar los objetos que deben transportar.
* Relacionar cada cubo con su zona de acopio correspondiente.
* Navegar en la superficie.
* Coordinar sus movimientos.
* Distribuir las tareas entre ambos rovers.
* Evitar colisiones entre ellos.
* Localizar y aproximarse a los cubos.
* Empujar o transportar los cubos utilizando la estructura original del robot.
* Llevar los objetos hasta la zona de acopio correspondiente.
* Corregir sus trayectorias utilizando la información de la cámara y de sus sensores integrados.
* Continuar operando de forma razonable cuando un objeto quede temporalmente oculto y la telemetría conserve su última posición conocida.

La orientación de los cubos no forma parte de la información requerida para completar la tarea. La posición y el color son suficientes para identificar cada cubo dentro del contrato de telemetría.

### 11. Superficie y sistema de coordenadas

La superficie física de competencia es aproximadamente de 1 m × 1 m y está formada por una cuadrícula de celdas de 20 mm.

El área efectiva utilizada por el sistema de visión está determinada por los marcadores visuales oficiales colocados en las esquinas. Por esta razón, las dimensiones lógicas de la cancha pueden ser menores que las dimensiones físicas completas de la superficie.

Los equipos no deberán asumir en su código un número fijo de filas o columnas. Deberán utilizar los valores publicados por el sistema oficial de visión, incluyendo:

* cantidad de columnas;
* cantidad de filas;
* tamaño de cada celda;
* posición de salida;
* posición de las zonas de acopio.

### 12. Restricciones técnicas

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
* Utilizar hardware externo como controlador auxiliar durante una ronda.
* Ejecutar planificación o control en tiempo real desde una computadora externa durante una ronda.

Cualquier modificación física o electrónica no autorizada será motivo de descalificación técnica.

### 13. Penalizaciones y descalificación

Podrán aplicarse penalizaciones por:

* Intervención manual durante la prueba.
* Salida de la superficie de competencia.
* Incumplimiento de las condiciones de autonomía.
* Incumplimiento de las condiciones de inicio o ejecución definidas por la organización.

Serán causas de descalificación:

* Modificar física o electrónicamente un robot.
* Agregar o sustituir componentes.
* Cambiar el microcontrolador o la tarjeta principal.
* Utilizar una plataforma robótica diferente.
* Controlar manualmente los robots durante la ejecución.
* Utilizar una computadora, teléfono, servicio en la nube u otro sistema externo para tomar decisiones o controlar los rovers durante una ronda.
* Incumplir las condiciones técnicas establecidas por la organización.

### 14. Criterio de éxito

El reto se considerará completado cuando los dos robots logren transportar y depositar correctamente todos los objetos requeridos en sus respectivas zonas de acopio, utilizando únicamente su configuración física original y operando de manera coordinada y autónoma.

Un objeto se considerará correctamente depositado cuando se encuentre completamente dentro del área definida para su zona de acopio.

Se valorará principalmente:

* La cantidad de objetos correctamente entregados.
* El tiempo total de ejecución.

El cronometraje oficial será supervisado por los jueces de la competencia.

## Resumen de lo que NO se puede hacer

| Área | ❌ Lo que NO se puede hacer | Ejemplo |
| --- | --- | --- |
| **Hardware** | Modificar físicamente los rovers | Cortar, perforar o alterar el robot |
| **Chasis** | Modificar el chasis original | Agregar una pala para empujar cubos |
| **Componentes** | Agregar componentes físicos | Añadir piezas impresas en 3D |
| **Componentes** | Retirar componentes | Quitar un sensor para reducir peso |
| **Electrónica** | Modificar la electrónica | Alterar la tarjeta principal |
| **Microcontrolador** | Sustituir el microcontrolador | Cambiar el ESP32 por otro controlador |
| **Controladores** | Agregar tarjetas de desarrollo | Incorporar Raspberry Pi, Arduino, otro ESP32, etc. |
| **Sensores** | Agregar sensores | Añadir LiDAR, cámara, ToF, encoders, etc. |
| **Sensores** | Sustituir sensores | Cambiar el ultrasónico por otro modelo |
| **Actuadores** | Agregar actuadores | Incorporar servomotores |
| **Manipulación** | Agregar mecanismos de recolección | Pinzas, brazos, palas móviles |
| **Motores** | Cambiar los motores | Instalar motores más rápidos |
| **Ruedas** | Cambiar las ruedas | Usar ruedas de mayor diámetro |
| **Baterías** | Cambiar el sistema de alimentación | Usar una batería diferente |
| **Robot** | Utilizar otra plataforma | Competir con un rover diseñado por el equipo |
| **Control humano** | Controlar manualmente los robots durante la prueba | Teclado, joystick, teléfono o control remoto |
| **Intervención** | Tocar los robots durante la ejecución | Reorientar un rover que quedó mal colocado |
| **Objetos** | Mover manualmente cubos u otros elementos | Corregir la posición de un cubo |
| **Software** | Modificar el código durante la prueba | Corregir un programa después de iniciar |
| **Robot** | Reprogramarlo durante la prueba | Subir nuevo firmware al ESP32 |
| **Robot** | Reiniciarlo selectivamente durante la ejecución | Resetear un rover que dejó de responder |
| **Comandos** | Enviar instrucciones humanas | Decidir manualmente que Rover 1 vaya al cubo rojo |
| **Autonomía** | Tomar decisiones humanas después de iniciar | Cambiar rutas o asignaciones manualmente |
| **Computadora externa** | Calcular rutas o asignar tareas durante una ronda | Ejecutar el planificador en una laptop |
| **Control externo** | Enviar comandos automáticos desde una computadora durante una ronda | Una laptop calcula y ordena `TURN` o `MOVE` |
| **Nube** | Utilizar un servicio externo para modificar decisiones en tiempo real | Consultar un modelo o servidor para decidir la siguiente acción |
