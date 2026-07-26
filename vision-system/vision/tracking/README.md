# tracking/

**Productor.** Le da continuidad en el tiempo a lo que los detectores ven cuadro
por cuadro, y arma el **estado del mundo** que consumen `publish/` y `record/`.

## Estado: vacío

**Todavía no hay código acá.** Depende de [`../detectors/`](../detectors/README.md),
que tampoco existe aún.

## Lo que va a existir

### Identidad entre cuadros

Un detector mira **un** cuadro y no sabe nada del anterior. Esta pieza es la que
sabe que el rover que aparece ahora es el mismo que estaba hace un instante un
poco más allá.

Para los rovers es directo, porque el ID de su marcador ArUco es su identidad.
Para los cubos también, porque el color los identifica y no hay dos iguales.

### Oclusión y edad — la regla que no se negocia

Cuando un objeto se tapa —un rover que pasa por encima de un cubo, un reflejo
sobre un marcador— **no desaparece del estado del mundo**. Se conserva su última
posición conocida y se le hace crecer un campo de **edad** (`age_ms`).

**Nunca** se hace parpadear un objeto entre existir y no existir. Un consumidor
no puede distinguir "se lo llevaron" de "no lo veo en este cuadro", así que
tendría que adivinar. Un dato viejo **marcado como viejo** siempre es mejor que
un agujero.

### El estado del mundo, inmutable

El resultado es una **foto completa de la cancha en un instante**, que no se
modifica: cada cuadro produce una nueva. Es lo único que cruza de los productores
a los consumidores, y por eso los dos lados pueden correr a ritmos distintos sin
pisarse.
