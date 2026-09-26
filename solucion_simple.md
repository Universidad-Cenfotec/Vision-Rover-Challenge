# Solución Greedy

## Tip: una estrategia básica que funciona

Una forma sencilla de comenzar es usar una estrategia **greedy** o voraz. No necesariamente produce la mejor solución, pero permite tener rápidamente un comportamiento funcional sobre el cual experimentar y mejorar.

### Estrategia básica

```text
MIENTRAS queden cubos fuera de la zona de acopio:

    1. Obtener la posición de los Rovers y de todos los cubos.

    2. Calcular la distancia de cada Rover a cada cubo disponible.

    3. Para cada Rover:
        seleccionar el cubo más cercano.

    4. Verificar que los dos Rovers no hayan seleccionado
       el mismo cubo.

       SI seleccionaron el mismo:
           asignarlo al Rover más cercano
           y hacer que el otro seleccione su siguiente cubo más cercano.

    5. Cada Rover avanza hacia su cubo.

    6. Antes de moverse:
        verificar si su trayectoria puede colisionar
        con el otro Rover.

        SI existe riesgo de colisión:
            modificar la trayectoria,
            reducir la velocidad,
            detener temporalmente uno de los Rovers,
            o darle prioridad a uno de ellos.

    7. Cada Rover lleva su cubo hasta la zona de acopio.

    8. El Rover que termine primero busca el cubo disponible
       más cercano y continúa trabajando.
```

### Algunas variantes para explorar

* **No siempre el cubo más cercano es el mejor.** Consideren también la distancia desde el cubo hasta la zona de acopio.

* Pueden calcular un costo aproximado como

```text
costo = distancia(Rover, cubo) + distancia(cubo, zona_de_acopio)
```

y seleccionar el cubo con menor costo.

* **Dividir el tablero en regiones.** Cada Rover puede encargarse inicialmente de una zona diferente para reducir interferencias.

* **Asignar todos los cubos antes de comenzar.** En lugar de decidir uno por uno, pueden intentar repartir los cubos entre los dos Rovers buscando que ambos tengan una cantidad de trabajo similar.

* **Recalcular después de cada entrega.** Una asignación que parecía buena al inicio puede dejar de serlo cuando cambian las posiciones.

* **Usar prioridades de paso.** Si las trayectorias de los Rovers se cruzan, uno puede tener prioridad mientras el otro espera o toma una ruta diferente.

* **Pensar en tiempo y no solamente en distancia.** Un recorrido ligeramente más largo puede ser mejor si evita giros, obstáculos, colisiones o interferencias con el otro Rover.

> **Reto adicional:** esta estrategia funciona, pero claramente no es óptima. ¿Pueden encontrar una estrategia que minimice el tiempo total necesario para llevar todos los cubos a la zona de acopio?
