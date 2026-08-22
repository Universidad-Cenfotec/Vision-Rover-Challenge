# ¿Qué debe resolver un participante del Vision Rover Challenge?

El **Vision Rover Challenge** consiste en desarrollar el software necesario para controlar y coordinar dos CenfoBots autónomos dentro de un espacio de trabajo observado por una cámara superior.

El reto no consiste únicamente en mover robots. El participante debe construir un sistema capaz de interpretar el estado del entorno, tomar decisiones, coordinar dos rovers y ejecutar acciones hasta completar una tarea física sin intervención humana.

---

## Objetivo general

El sistema debe utilizar dos rovers para localizar objetos dentro del área de competencia, desplazarse hasta ellos, transportarlos y colocarlos en las zonas de destino correspondientes.

Una vez iniciada la prueba, todo el proceso debe realizarse de manera autónoma.

---

## Elementos disponibles

Durante el reto se dispone de:

- Dos CenfoBots.
- Una superficie de trabajo.
- Una cámara superior.
- Un sistema de visión global.
- Cubos de diferentes colores.
- Zonas de destino asociadas a los objetos.
- Obstáculos dentro del área de competencia.
- Marcadores visuales para identificar y localizar los rovers.
- Sensores incorporados en los CenfoBots.
- Comunicación inalámbrica.

El hardware oficial de los rovers no debe ser modificado.

---

# Información proporcionada por el sistema de visión

El participante no debe desarrollar el sistema de visión global.

El sistema oficial proporcionará información sobre el estado del entorno, incluyendo datos como:

- posición de cada rover;
- orientación de cada rover;
- posición de los cubos;
- identificación de los cubos por color;
- posición de obstáculos;
- posición de las zonas de destino;
- dimensiones y referencia espacial del área de competencia;
- estado general de la prueba.

Esta información representa una descripción del mundo observado por la cámara.

El participante debe utilizarla para tomar decisiones.

---

# Problemas que debe resolver el participante

## 1. Interpretar el estado del entorno

El sistema debe recibir la información proporcionada por la visión global y construir a partir de ella una representación útil del entorno.

Debe poder determinar, entre otros aspectos:

- dónde se encuentran los dos rovers;
- hacia dónde está orientado cada rover;
- dónde están los cubos;
- dónde están los obstáculos;
- dónde se encuentran las zonas de destino;
- qué elementos continúan disponibles para ser transportados.

---

## 2. Decidir qué debe hacer cada rover

Los dos rovers deben trabajar como parte de un mismo sistema.

El participante debe decidir cómo distribuir el trabajo entre ellos.

El sistema deberá determinar dinámicamente aspectos como:

- qué rover atenderá cada objeto;
- cuándo debe cambiar una asignación;
- cómo evitar que ambos rovers intenten realizar tareas incompatibles;
- cómo utilizar ambos robots de manera eficiente.

La coordinación entre los rovers forma parte del reto.

---

## 3. Determinar cómo llegar hasta un objeto

Una vez seleccionado un objeto, el sistema debe determinar cómo llevar el rover desde su posición actual hasta una posición desde la cual pueda interactuar correctamente con ese objeto.

Durante este desplazamiento deberá considerar:

- la posición actual del rover;
- su orientación;
- la posición del objeto;
- los obstáculos;
- el otro rover;
- los límites del área de competencia.

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

---

## 6. Llevar cada cubo a su zona correspondiente

Cada objeto debe terminar en la zona de destino que le corresponde.

El sistema debe determinar cuándo el objeto ha llegado correctamente a su destino y cuándo la tarea puede considerarse completada.

Después deberá continuar con las tareas pendientes.

---

## 7. Evitar obstáculos

Los rovers no pueden desplazarse suponiendo que el espacio está libre.

El sistema debe tomar en cuenta los obstáculos presentes en el escenario y evitar colisiones durante:

- el desplazamiento hacia los cubos;
- el transporte de los objetos;
- el desplazamiento hacia nuevas tareas.

---

## 8. Evitar colisiones entre los dos rovers

El segundo rover también forma parte del entorno dinámico.

Los dos robots pueden encontrarse, cruzar trayectorias o intentar ocupar simultáneamente una misma región.

El participante debe garantizar que su sistema pueda coordinar sus movimientos evitando interferencias y colisiones innecesarias.

---

## 9. Utilizar información imperfecta

La información del sistema de visión puede variar durante la ejecución.

Un objeto puede quedar temporalmente oculto por un rover u otro elemento del escenario.

El sistema debe poder continuar operando de manera razonable cuando alguna información no esté disponible momentáneamente.

También debe reconocer cuándo la información disponible ha cambiado y actualizar sus decisiones.

---

## 10. Corregir errores durante la ejecución

El comportamiento del mundo físico no es perfectamente predecible.

Un rover puede:

- desviarse de la trayectoria esperada;
- girar más o menos de lo previsto;
- mover un cubo de forma diferente a la esperada;
- encontrar al otro rover en una posición inesperada.

El sistema debe observar continuamente el estado actualizado del entorno y ser capaz de modificar sus decisiones cuando sea necesario.

---

# Autonomía

Una vez iniciada la prueba no se permite intervención humana para dirigir los robots.

El sistema debe encargarse automáticamente de:

1. observar el estado del entorno;
2. decidir qué hacer;
3. enviar instrucciones a los rovers;
4. verificar el resultado de esas acciones;
5. corregir el comportamiento cuando sea necesario;
6. continuar hasta completar el objetivo.

---

# Comunicación

El participante deberá utilizar los mecanismos de comunicación disponibles para conectar los diferentes componentes de su sistema.

Puede ser necesario intercambiar información entre:

- el sistema de visión y el software del equipo;
- la computadora y los rovers;
- los dos rovers.

La comunicación debe formar parte del funcionamiento autónomo del sistema.

---

# Uso de los sensores del rover

Cada CenfoBot dispone además de sensores locales.

El participante puede decidir cuándo y cómo utilizar esta información como parte de su sistema.

Estos sensores pueden proporcionar información complementaria al estado global proporcionado por la cámara.

---

# Lo que NO forma parte del reto

El participante no necesita desarrollar:

- el hardware del CenfoBot;
- el sistema de cámara superior;
- el reconocimiento visual básico de los rovers;
- el protocolo utilizado para recibir el estado global del entorno.

Estos elementos forman parte de la infraestructura proporcionada por la organización.

---

# Lo que SÍ forma parte del reto

El participante debe desarrollar la inteligencia necesaria para transformar la información disponible en comportamiento autónomo.

En términos generales, deberá resolver:

| Problema | Responsabilidad |
| --- | --- |
| **Percepción del estado** | Interpretar la información proporcionada por el sistema de visión |
| **Asignación de tareas** | Decidir qué debe hacer cada rover |
| **Planificación de movimiento** | Determinar cómo desplazarse por el entorno |
| **Control del rover** | Convertir decisiones en movimiento físico |
| **Coordinación** | Evitar conflictos entre los dos robots |
| **Manipulación** | Transportar físicamente los cubos |
| **Evitación** | Evitar obstáculos y colisiones |
| **Corrección** | Adaptarse a errores y cambios en el entorno |
| **Comunicación** | Mantener conectados los diferentes componentes |
| **Autonomía** | Completar la tarea sin intervención humana |

---

# Condición de éxito

Una ejecución exitosa requiere que los dos rovers trabajen autónomamente para transportar correctamente los objetos hasta sus destinos.

El desempeño puede depender de aspectos como:

- cantidad de objetos correctamente transportados;
- precisión en la colocación;
- tiempo utilizado;
- ausencia de colisiones;
- capacidad de recuperación ante errores;
- coordinación entre ambos rovers.

---

# La esencia del reto

El Vision Rover Challenge plantea un problema de **robótica autónoma distribuida en un entorno físico**.

El sistema recibe información sobre el mundo, pero no recibe las decisiones que debe tomar.

El desafío para el participante consiste precisamente en construir el software capaz de convertir:

**estado del mundo → decisiones → coordinación → movimiento → resultado físico**

hasta completar la misión utilizando los dos rovers de manera autónoma.
