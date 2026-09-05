# ¿Qué debe resolver un participante del Vision Rover Challenge?

El **Vision Rover Challenge** consiste en desarrollar el software necesario para controlar y coordinar dos CenfoBots autónomos dentro de un espacio de trabajo observado por una cámara superior.

El reto no consiste únicamente en mover robots. El participante debe construir un sistema capaz de interpretar el estado del entorno, tomar decisiones, coordinar dos rovers y ejecutar acciones hasta completar una tarea física sin intervención humana y sin depender de una computadora externa para decidir o controlar el comportamiento de los robots durante la ronda.

---

## Objetivo general

El sistema debe utilizar dos rovers para localizar objetos dentro del área de competencia, desplazarse hasta ellos, transportarlos y colocarlos en las zonas de destino correspondientes.

Una vez iniciada la prueba, todo el proceso de decisión, planificación, coordinación y control debe realizarse de manera autónoma en los rovers.

La computadora utilizada por la organización para ejecutar el sistema oficial de visión proporciona información del entorno, pero no toma decisiones por los equipos.

---

## Elementos disponibles

Durante el reto se dispone de:

- Dos CenfoBots.
- Una superficie de trabajo.
- Una cámara superior.
- Un sistema oficial de visión global.
- Cubos de diferentes colores.
- Zonas de destino asociadas a los objetos.
- Marcadores visuales para identificar y localizar los rovers.
- Sensores incorporados en los CenfoBots.
- Comunicación inalámbrica.
- Telemetría publicada por el sistema de visión.

El hardware oficial de los rovers no debe ser modificado.

---

# Información proporcionada por el sistema de visión

<p align="center">
  <img src="https://raw.githubusercontent.com/Universidad-Cenfotec/Vision-Rover-Challenge/main/vrc1.jpeg" width="100%">
</p>

El participante no debe desarrollar el sistema de visión global.

El sistema oficial proporcionará información sobre el estado del entorno, incluyendo datos como:

- posición de cada rover;
- orientación de cada rover;
- posición de los cubos;
- identificación de los cubos por color;
- posición de las zonas de destino;
- dimensiones y referencia espacial del área de competencia;
- estado general de la prueba;
- antigüedad de algunas observaciones cuando un objeto queda temporalmente oculto.

Esta información representa una descripción del mundo observado por la cámara.

Los rovers deben utilizarla como entrada para tomar sus propias decisiones.

<p align="center">
  <img src="https://raw.githubusercontent.com/Universidad-Cenfotec/Vision-Rover-Challenge/main/vrc2.jpeg" width="100%">
</p>

La telemetría se publica de acuerdo con el contrato oficial definido en el repositorio. Los equipos deben interpretar ese contrato y trabajar con el estado más reciente disponible, evitando ejecutar decisiones basadas en una cola de estados antiguos.

---

# Problemas que debe resolver el participante

## 1. Interpretar el estado del entorno

Los rovers deben recibir la información proporcionada por la visión global y construir a partir de ella una representación útil del entorno.

Deben poder determinar, entre otros aspectos:

- dónde se encuentran los dos rovers;
- hacia dónde está orientado cada rover;
- dónde están los cubos;
- dónde se encuentran las zonas de destino;
- qué elementos continúan disponibles para ser transportados;
- qué información es reciente y cuál corresponde a una última observación conocida.

La representación del entorno forma parte de la lógica del equipo y debe estar disponible para los rovers durante la ejecución.

---

## 2. Decidir qué debe hacer cada rover

Los dos rovers deben trabajar como parte de un mismo sistema autónomo.

El participante debe decidir cómo distribuir el trabajo entre ellos.

El sistema deberá determinar dinámicamente aspectos como:

- qué rover atenderá cada objeto;
- cuándo debe cambiar una asignación;
- cómo evitar que ambos rovers intenten realizar tareas incompatibles;
- cómo utilizar ambos robots de manera eficiente.

La coordinación entre los rovers forma parte del reto.

Estas decisiones deben generarse en los rovers durante la ronda y no en una computadora externa.

---

## 3. Determinar cómo llegar hasta un objeto

Una vez seleccionado un objeto, el sistema debe determinar cómo llevar el rover desde su posición actual hasta una posición desde la cual pueda interactuar correctamente con ese objeto.

Durante este desplazamiento deberá considerar:

- la posición actual del rover;
- su orientación;
- la posición del objeto;
- el otro rover;
- los límites del área de competencia;
- la zona de destino correspondiente.

La planificación de movimiento debe ejecutarse en los rovers durante la ronda.

---

## 4. Controlar el movimiento del rover

El participante debe transformar las decisiones tomadas por su sistema en movimientos físicos de los CenfoBots.

El rover debe poder realizar movimientos controlados que permitan:

- avanzar;
- cambiar de orientación;
- aproximarse a un objeto;
- detenerse;
- corregir desviaciones;
- ejecutar secuencias de movimiento.

El control del movimiento debe ser suficientemente preciso para interactuar con los objetos del reto.

Los comandos de movimiento deben ser generados por la lógica ejecutada en los rovers, no por una computadora, teléfono o servicio externo durante la ronda.

---

## 5. Manipular y transportar los cubos

Llegar hasta un cubo no completa la tarea.

El rover debe posicionarse de manera adecuada para mover físicamente el objeto y transportarlo hacia su destino.

El participante deberá resolver:

- desde qué posición aproximarse al cubo;
- cómo orientar el rover respecto al objeto;
- cómo iniciar el desplazamiento del cubo;
- cómo mantener control del objeto durante el transporte;
- cómo corregir la trayectoria si el cubo cambia de posición.

El rover debe realizar estas tareas utilizando únicamente su estructura y hardware originales.

---

## 6. Llevar cada cubo a su zona correspondiente

Cada objeto debe terminar en la zona de destino que le corresponde.

Las zonas de destino son definidas por la organización y forman parte de la información oficial del entorno.

El sistema debe determinar cuándo el objeto ha llegado correctamente a su destino.

Un cubo se considera correctamente depositado cuando se encuentra completamente dentro del área definida para su zona de acopio.

Después de completar una entrega, los rovers deberán continuar con las tareas pendientes.

La orientación final del cubo no forma parte del criterio de entrega.

---

## 7. Evitar colisiones entre los dos rovers

El segundo rover también forma parte del entorno dinámico.

Los dos robots pueden encontrarse, cruzar trayectorias o intentar ocupar simultáneamente una misma región.

El participante debe garantizar que su sistema pueda coordinar sus movimientos evitando interferencias y colisiones innecesarias.

La coordinación puede apoyarse tanto en la telemetría global como en la comunicación directa entre los dos rovers.

---

## 8. Utilizar información imperfecta

La información del sistema de visión puede variar durante la ejecución.

Un objeto puede quedar temporalmente oculto por un rover u otro elemento del escenario.

Cuando esto ocurra, el sistema de visión puede conservar la última posición conocida del objeto y aumentar la antigüedad de esa observación.

El sistema debe poder continuar operando de manera razonable cuando alguna información no esté disponible momentáneamente.

También debe reconocer cuándo la información disponible ha cambiado y actualizar sus decisiones.

El participante debe decidir cómo utilizar campos como secuencia, tiempo y antigüedad de observación para determinar si un dato sigue siendo confiable para navegación o control.

---

## 9. Corregir errores durante la ejecución

El comportamiento del mundo físico no es perfectamente predecible.

Un rover puede:

- desviarse de la trayectoria esperada;
- girar más o menos de lo previsto;
- mover un cubo de forma diferente a la esperada;
- encontrar al otro rover en una posición inesperada.

El sistema debe observar continuamente el estado actualizado del entorno y ser capaz de modificar sus decisiones cuando sea necesario.

La capacidad de corregir errores durante la ejecución debe estar implementada en los rovers y formar parte de la estrategia autónoma del equipo.

---

# Autonomía

Una vez iniciada la prueba no se permite intervención humana para dirigir los robots.

Tampoco se permite que una computadora externa, teléfono, servicio en la nube u otro dispositivo tome decisiones, calcule nuevas rutas, distribuya tareas o genere comandos de movimiento durante una ronda oficial.

Los rovers deben encargarse automáticamente de:

1. recibir el estado del entorno;
2. interpretarlo;
3. decidir qué hacer;
4. coordinarse entre ellos;
5. ejecutar movimientos;
6. verificar el resultado de esas acciones;
7. corregir el comportamiento cuando sea necesario;
8. continuar hasta completar el objetivo.

Antes de iniciar la prueba sí pueden utilizarse computadoras y otras herramientas para desarrollo, simulación, configuración, depuración, análisis y generación de planes o parámetros que luego sean cargados en los rovers.

---

# Comunicación

El participante deberá utilizar los mecanismos de comunicación disponibles para conectar los componentes permitidos de su sistema.

Durante la ejecución puede ser necesario intercambiar información entre:

- el sistema oficial de visión y los rovers;
- los dos rovers.

El sistema de visión publica información del entorno y los rovers la consumen.

Los rovers pueden comunicarse entre sí utilizando los mecanismos inalámbricos disponibles en el hardware oficial.

La comunicación debe formar parte del funcionamiento autónomo del sistema.

Una computadora externa no debe utilizarse durante la ronda como intermediario para tomar decisiones, calcular rutas, asignar tareas o enviar comandos de movimiento.

---

# Uso de los sensores del rover

Cada CenfoBot dispone además de sensores locales.

El participante puede decidir cuándo y cómo utilizar esta información como parte de su sistema.

Estos sensores pueden proporcionar información complementaria al estado global proporcionado por la cámara.

Por ejemplo, los sensores locales pueden utilizarse para:

- corregir movimientos;
- detectar proximidad;
- mantener orientación;
- identificar colores cercanos;
- verificar condiciones físicas que no se observan con suficiente precisión desde la cámara.

---

# Superficie y sistema de coordenadas

La superficie física de competencia es aproximadamente de 1 m × 1 m y está formada por una cuadrícula de celdas de 20 mm.

Sin embargo, el área lógica utilizada por el sistema de visión está determinada por los marcadores visuales oficiales colocados en las esquinas.

Por esta razón, el número de filas y columnas efectivamente utilizado por el sistema puede ser menor que el número total de cuadros físicos del tablero.

Los participantes no deben asumir dimensiones fijas en su código.

Los rovers deben utilizar los valores proporcionados por la telemetría oficial, incluyendo:

- cantidad de filas;
- cantidad de columnas;
- tamaño de celda;
- posición de salida;
- posición de las zonas de acopio.

---

# Inicio y finalización de la ronda

El inicio de cada ronda será indicado por un juez.

Los rovers deberán estar previamente encendidos, programados y preparados para ejecutar su estrategia.

El equipo puede utilizar el botón de arranque disponible en la IdeaBoard para iniciar la ejecución cuando el juez dé la señal oficial.

A partir de ese momento se aplican todas las condiciones de autonomía del reto.

La ronda finalizará cuando:

- todos los cubos requeridos se encuentren correctamente depositados;
- se alcance el tiempo máximo definido por la organización;
- el juez detenga la ronda por razones de seguridad o por incumplimiento del reglamento.

La posición final de los rovers no afecta la condición de éxito cuando todos los cubos requeridos ya fueron depositados correctamente.

El tiempo máximo de cada ronda será comunicado oficialmente por la organización.

---

# Lo que NO forma parte del reto

El participante no necesita desarrollar:

- el hardware del CenfoBot;
- el sistema de cámara superior;
- el reconocimiento visual básico de los rovers;
- el sistema oficial de detección del entorno;
- el protocolo utilizado para recibir el estado global del entorno.

Estos elementos forman parte de la infraestructura proporcionada por la organización.

Tampoco forma parte del reto reemplazar el sistema de visión oficial por uno desarrollado por el equipo.

---

# Lo que SÍ forma parte del reto

El participante debe desarrollar la inteligencia necesaria para transformar la información disponible en comportamiento autónomo ejecutado por los rovers.

En términos generales, deberá resolver:

| Problema | Responsabilidad |
| --- | --- |
| **Percepción del estado** | Interpretar la información proporcionada por el sistema de visión |
| **Representación del entorno** | Mantener un estado útil y actualizado del mundo |
| **Asignación de tareas** | Decidir qué debe hacer cada rover |
| **Planificación de movimiento** | Determinar cómo desplazarse por el entorno |
| **Control del rover** | Convertir decisiones en movimiento físico |
| **Coordinación** | Evitar conflictos entre los dos robots |
| **Manipulación** | Transportar físicamente los cubos |
| **Evitación** | Evitar colisiones |
| **Corrección** | Adaptarse a errores y cambios en el entorno |
| **Comunicación** | Intercambiar información entre los rovers y recibir telemetría |
| **Autonomía** | Completar la tarea sin intervención humana ni control externo |

---

# Condición de éxito

Una ejecución exitosa requiere que los dos rovers trabajen autónomamente para transportar correctamente los objetos hasta sus destinos.

Un cubo se considera correctamente entregado cuando se encuentra completamente dentro del área definida para su zona de acopio correspondiente.

El reto se completa cuando todos los cubos requeridos han sido entregados correctamente.

La posición final de los rovers no forma parte de la condición de éxito.

El desempeño se valorará principalmente por:

- cantidad de objetos correctamente transportados;
- tiempo utilizado para completar la tarea.

El cronometraje oficial será supervisado por los jueces de la competencia.

---

# La esencia del reto

El Vision Rover Challenge plantea un problema de **robótica autónoma distribuida en un entorno físico**.

El sistema oficial de visión proporciona percepción global del entorno, pero no proporciona estrategia.

Los rovers reciben información sobre el mundo, pero deben decidir por sí mismos qué hacer con ella.

El desafío para el participante consiste precisamente en construir el software capaz de convertir:

**estado del mundo → decisiones → coordinación → movimiento → resultado físico**

hasta completar la misión utilizando los dos rovers de manera autónoma.

Una forma útil de entender la arquitectura del reto es:

**sistema oficial de visión → telemetría → rovers → decisiones → coordinación → control → movimiento**

con comunicación directa entre los dos rovers cuando sea necesaria.
