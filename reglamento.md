# Reglamento

## Objetivo del reto

Desarrollar un sistema autónomo compuesto por dos robots tipo rover capaces de coordinarse para navegar una superficie delimitada, identificar objetos cúbicos de un color específico y transportarlos hasta una zona de acopio.

Una cámara superior y el sistema oficial de visión proporcionarán información global sobre la posición y orientación de los robots, la posición de los cubos, las zonas de acopio y el estado general de la prueba. A partir de esta información, los rovers deberán interpretar el entorno, distribuir tareas, planificar sus movimientos, coordinarse y corregir su comportamiento durante la ejecución.

La solución deberá integrar robótica móvil, comunicación inalámbrica, planificación de rutas, coordinación entre robots, control y autonomía.

A partir del cambio del sistema oficial de visión al estado `READY`, los rovers deberán operar sin intervención humana y sin que una computadora externa, servicio en la nube u otro dispositivo externo tome decisiones o modifique su planificación en tiempo real.

# Reglas del reto

## 1. Plataforma robótica

1.1. Cada equipo utilizará los dos robots oficiales entregados por la organización.

1.2. Los robots deberán utilizarse con su configuración física y electrónica original.

1.3. No se permite modificar, sustituir, remover ni agregar componentes físicos o electrónicos.

1.4. No se permite cambiar la tarjeta electrónica principal.

1.5. No se permite sustituir el microcontrolador.

1.6. No se permite utilizar otra tarjeta de desarrollo como controlador principal o auxiliar.

1.7. No se permite modificar el chasis, los motores, las ruedas, los sensores ni el sistema de alimentación.

1.8. No se permite agregar mecanismos de recolección, servomotores, estructuras impresas en 3D ni sensores adicionales.

1.9. No se permite reemplazar los robots entregados por otra plataforma robótica.

1.10. Se permite modificar únicamente el software y la programación de los robots.

---

## 2. Componentes incluidos en los robots

2.1. Cada robot será entregado completamente ensamblado.

2.2. Cada robot incluirá:

2.2.1. Sensor ultrasónico para medición de distancia y detección de obstáculos.

2.2.2. Acelerómetro para medir aceleraciones y cambios de movimiento.

2.2.3. Giroscopio para estimar orientación, rotación y cambios angulares.

2.2.4. Sensor de color para reconocer objetos cercanos.

2.2.5. Sensores infrarrojos para detección de la superficie cuadriculada.

2.2.6. Motores y sistema de locomoción diferencial.

2.2.7. Microcontrolador y tarjeta electrónica principal ESP32 IdeaBoard.

2.2.8. Sistema de alimentación por baterías.

2.2.9. Sistema de comunicación inalámbrica disponible en el ESP32.

2.3. Los equipos deberán desarrollar sus soluciones utilizando exclusivamente las capacidades disponibles en esta plataforma.

---

## 3. Entrega de robots y materiales

3.1. La organización entregará a cada equipo dos robots tipo rover sin costo.

3.2. La organización proporcionará los materiales oficiales necesarios para ejecutar el reto.

3.3. Los equipos no deberán comprar componentes para modificar los robots.

3.4. Los cubos, marcadores visuales, superficie de competencia y demás elementos oficiales del escenario serán suministrados por la organización.

3.5. La participación y el uso de los robots y materiales oficiales no tendrán costo para los equipos.

---

## 4. Programación de los robots

4.1. Los equipos podrán modificar el código ejecutado por el microcontrolador.

4.2. Los equipos podrán:

4.2.1. Programar el movimiento de los motores.

4.2.2. Procesar las mediciones de los sensores integrados.

4.2.3. Recibir y procesar la telemetría publicada por el sistema oficial de visión.

4.2.4. Implementar algoritmos de navegación y corrección de trayectoria.

4.2.5. Implementar algoritmos de asignación de tareas entre los dos rovers.

4.2.6. Desarrollar protocolos de comunicación entre los robots.

4.2.7. Implementar estrategias para evitar colisiones.

4.2.8. Implementar estrategias para empujar, orientar o transportar los cubos utilizando la estructura original del robot.

4.2.9. Utilizar los lenguajes, bibliotecas y herramientas de software que consideren apropiados, siempre que sean compatibles con el hardware oficial y respeten las condiciones de autonomía del reto.

4.3. La lógica necesaria para tomar decisiones durante un intento deberá estar cargada y ejecutarse en los rovers.

4.4. No se permitirá realizar cambios físicos para facilitar estas tareas.

---

## 5. Sistema de visión global

5.1. Una cámara superior observará la superficie de competencia.

5.2. El sistema oficial de visión será proporcionado por la organización.

5.3. El sistema de visión determinará la posición y orientación de cada rover.

5.4. El sistema de visión determinará la posición de los cubos y proporcionará las zonas de acopio definidas para el intento.

5.5. Los rovers utilizarán marcadores visuales oficiales para ser identificados por el sistema.

5.6. El sistema de visión publicará telemetría en tiempo real para que los rovers puedan conocer el estado global del entorno.

5.7. El sistema oficial de visión no deberá ser modificado por los equipos durante la competencia.

5.8. La telemetría deberá interpretarse según el contrato oficial publicado en el repositorio del Vision Rover Challenge.

5.9. El sistema de visión proporciona percepción global del entorno, pero no proporciona la estrategia, las rutas ni las decisiones de los equipos.

5.10. El sistema oficial de visión también proporcionará los estados utilizados para controlar el inicio de cada intento, incluyendo `IDLE` y `READY`.

---

## 6. Uso de computadoras externas y servicios en la nube

6.1. Durante el desarrollo y preparación, los equipos podrán utilizar laptops, computadoras de escritorio, mini PC, servicios en la nube, modelos de inteligencia artificial, simuladores y otras herramientas.

6.2. Estas herramientas podrán utilizarse para:

6.2.1. Desarrollar y depurar código.

6.2.2. Simular escenarios.

6.2.3. Analizar datos.

6.2.4. Diseñar y evaluar estrategias.

6.2.5. Generar planes o parámetros que posteriormente sean cargados en los rovers.

6.2.6. Configurar direcciones IP, direcciones MAC y parámetros de comunicación.

6.2.7. Verificar el funcionamiento de los robots y su conexión con el sistema de visión.

6.3. Una vez que el sistema oficial de visión cambie al estado `READY`:

6.3.1. No se permite que una computadora externa calcule nuevas rutas para los robots.

6.3.2. No se permite que una computadora externa distribuya o reasigne tareas entre los robots.

6.3.3. No se permite que una computadora externa tome decisiones de navegación.

6.3.4. No se permite que una computadora externa genere comandos de movimiento.

6.3.5. No se permite que un servicio en la nube modifique la estrategia o planificación de los robots en tiempo real.

6.3.6. No se permite enviar cambios de planificación desde un dispositivo externo.

6.3.7. No se permite utilizar una computadora, teléfono u otro dispositivo como sistema de control remoto, aunque los comandos sean generados automáticamente.

6.4. La computadora utilizada por la organización para ejecutar el sistema oficial de visión no se considera parte del sistema de control del equipo.

6.5. Su función será observar el entorno, publicar telemetría y gestionar los estados oficiales del intento.

---

## 7. Comunicación

7.1. Los rovers recibirán información del sistema oficial de visión mediante la red definida por la organización y de acuerdo con el contrato de telemetría.

7.2. Los robots podrán comunicarse entre sí mediante los mecanismos inalámbricos disponibles en el hardware oficial.

7.3. Los rovers podrán intercambiar información sobre sus estados, tareas y movimientos.

7.4. Los rovers podrán coordinar rutas y evitar colisiones.

7.5. Los rovers podrán informar entre ellos sobre la detección, transporte o entrega de objetos.

7.6. Las decisiones de coordinación deberán producirse de manera autónoma en los rovers.

7.7. No se permite enviar instrucciones humanas durante la ejecución.

7.8. No se permite utilizar una computadora externa como intermediario para tomar decisiones o controlar los rovers durante un intento.

7.9. Los equipos deberán trabajar con el estado más reciente disponible de la telemetría y evitar ejecutar decisiones basadas en una cola de estados antiguos.

7.10. Los campos de secuencia, tiempo y antigüedad definidos en el contrato de telemetría podrán utilizarse para determinar la vigencia de los datos recibidos.

---

## 8. Preparación de un intento

8.1. Antes de cada intento, la organización restablecerá el escenario de competencia según la configuración oficial correspondiente.

8.2. Los robots, cubos, zonas de acopio y demás elementos serán colocados en las condiciones iniciales definidas para el intento.

8.3. Todos los equipos competirán bajo las mismas condiciones oficiales establecidas para la ronda.

8.4. Una vez preparado el escenario, el sistema oficial de visión establecerá el estado `IDLE` durante **1 minuto**.

8.5. Durante el estado `IDLE`, los rovers deberán estar encendidos, programados, conectados al sistema de visión y preparados para ejecutar la prueba.

8.6. Antes del cambio a `READY` se permitirá:

8.6.1. Calibrar los sensores.

8.6.2. Verificar la comunicación.

8.6.3. Ajustar los parámetros del sistema.

8.6.4. Comprobar el funcionamiento de los robots.

8.6.5. Configurar direcciones IP, direcciones MAC u otros parámetros de red.

8.6.6. Cargar el software y los planes previamente desarrollados en los rovers.

8.6.7. Colocar los robots en la posición inicial establecida.

8.7. El período de 1 minuto en estado `IDLE` no forma parte del tiempo oficial del intento.

---

## 9. Inicio del intento

9.1. Finalizado el período de 1 minuto en estado `IDLE`, el sistema oficial de visión cambiará al estado `READY`.

9.2. Los rovers deberán detectar el estado `READY` mediante la telemetría oficial.

9.3. La detección del estado `READY` deberá provocar automáticamente el inicio de la estrategia desarrollada por el equipo.

9.4. El cambio a `READY` marca el **inicio oficial del intento y del cronometraje**.

9.5. No se permitirá intervención humana para iniciar los rovers después del cambio a `READY`.

9.6. No se permitirá presionar botones para iniciar la estrategia después del cambio a `READY`.

9.7. La detección de `READY` y el inicio de la ejecución deberán formar parte del software desarrollado por el equipo.

9.8. La secuencia general de inicio será:

**Preparación → `IDLE` durante 1 minuto → `READY` → inicio automático de los rovers**

---

## 10. Duración y finalización del intento

10.1. Cada intento tendrá una duración máxima de **10 minutos**.

10.2. Los 10 minutos se medirán a partir del cambio del sistema oficial de visión al estado `READY`.

10.3. El intento finalizará cuando ocurra alguna de las siguientes condiciones:

10.3.1. Los tres cubos se encuentren correctamente depositados en sus respectivas zonas de acopio.

10.3.2. Se alcance el límite máximo de 10 minutos.

10.3.3. El juez detenga el intento por razones de seguridad.

10.3.4. El juez detenga el intento por incumplimiento del reglamento.

10.3.5. Ocurra una falla de infraestructura que, a criterio del juez, haga imposible continuar el intento en condiciones válidas.

10.4. Si el equipo completa correctamente los tres cubos antes de los 10 minutos, se registrará el tiempo transcurrido desde el cambio a `READY` hasta que el tercer cubo quede correctamente depositado.

10.5. La posición final de los rovers no forma parte de la condición de éxito una vez que los tres cubos hayan sido depositados correctamente.

---

## 11. Autonomía durante el intento

11.1. La ejecución autónoma comienza formalmente cuando el sistema oficial de visión cambia del estado `IDLE` al estado `READY`.

11.2. A partir de ese momento:

11.2.1. Los rovers deberán iniciar automáticamente su estrategia.

11.2.2. No se permitirá tocar, mover o reorientar los robots.

11.2.3. No se permitirá presionar botones para iniciar, reiniciar o modificar su comportamiento.

11.2.4. No se permitirá modificar el código.

11.2.5. No se permitirá reprogramar o reiniciar los robots.

11.2.6. No se permitirá enviar instrucciones humanas.

11.2.7. No se permitirá enviar comandos desde una computadora, teléfono u otro dispositivo.

11.2.8. No se permitirá modificar parámetros o configuraciones.

11.2.9. No se permitirá mover manualmente los cubos ni otros elementos del escenario.

11.2.10. No se permitirá corregir manualmente la posición de ningún elemento.

11.2.11. No se permitirá modificar externamente la estrategia, asignación de tareas, rutas o comandos de movimiento.

11.2.12. No se permitirá utilizar lógica externa en una laptop, computadora, teléfono o servicio en la nube para alterar el comportamiento de los rovers en tiempo real.

11.3. Los rovers deberán ejecutar completamente la tarea de manera autónoma.

---

## 12. Ejecución de la tarea

12.1. Los robots deberán iniciar desde la zona establecida.

12.2. Durante el intento deberán:

12.2.1. Interpretar la información recibida del sistema oficial de visión.

12.2.2. Identificar los objetos que deben transportar.

12.2.3. Relacionar cada cubo con su zona de acopio correspondiente.

12.2.4. Navegar en la superficie.

12.2.5. Coordinar sus movimientos.

12.2.6. Distribuir las tareas entre ambos rovers.

12.2.7. Evitar colisiones entre ellos.

12.2.8. Localizar y aproximarse a los cubos.

12.2.9. Empujar o transportar los cubos utilizando la estructura original del robot.

12.2.10. Llevar los objetos hasta la zona de acopio correspondiente.

12.2.11. Corregir sus trayectorias utilizando la información de la cámara y de sus sensores integrados.

12.2.12. Continuar operando de forma razonable cuando un objeto quede temporalmente oculto y la telemetría conserve su última posición conocida.

12.3. La orientación de los cubos no forma parte de la información requerida para completar la tarea.

12.4. La posición y el color son suficientes para identificar cada cubo dentro del contrato de telemetría.

---

## 13. Validez de los cubos depositados

13.1. Un cubo se considerará correctamente depositado cuando se encuentre **completamente dentro de su zona de acopio correspondiente**.

13.2. El tiempo de depósito de un cubo corresponderá al momento, medido desde el cambio a `READY`, en que el cubo quede correctamente depositado.

13.3. Un cubo correctamente depositado deberá permanecer en una condición válida durante el resto del intento.

13.4. Si posteriormente uno de los rovers retira accidentalmente un cubo de su zona de acopio, el cubo dejará de considerarse correctamente depositado.

13.5. Si un rover provoca que un cubo salga de la superficie de competencia, caiga del tablero o quede fuera del área válida de juego, ese cubo se considerará **no depositado**.

13.6. En los casos establecidos en 13.4 y 13.5, cualquier registro previo de depósito del cubo quedará sin efecto.

13.7. Para efectos de cantidad de cubos completados, tiempo y clasificación, se considerará como si ese cubo no hubiera sido depositado correctamente durante el intento.

13.8. Los jueces no recolocarán manualmente un cubo que haya sido desplazado, retirado de su zona de acopio o expulsado de la superficie como consecuencia de las acciones de los rovers.

13.9. Si el cubo permanece dentro del área válida de competencia, los rovers podrán intentar colocarlo nuevamente en su zona de acopio mientras quede tiempo disponible.

13.10. Si el cubo vuelve a ser correctamente depositado, se registrará como tiempo válido el correspondiente al nuevo depósito correcto.

---

## 14. Registro oficial de tiempos

14.1. Durante cada intento se registrará la cantidad de cubos correctamente depositados.

14.2. Se registrará el tiempo de depósito correcto del primer cubo.

14.3. Se registrará el tiempo de depósito correcto del segundo cubo, cuando corresponda.

14.4. Se registrará el tiempo de depósito correcto del tercer cubo, cuando corresponda.

14.5. Si los tres cubos son completados, el tiempo del tercer cubo constituirá el tiempo total de finalización.

14.6. Todos los tiempos se medirán a partir del momento en que el sistema oficial de visión cambie al estado `READY`.

14.7. Solamente se utilizarán para la clasificación los tiempos correspondientes a cubos que permanezcan válidamente depositados al finalizar el intento.

14.8. Si un cubo pierde posteriormente su condición de depósito válido, su tiempo anterior será eliminado del resultado del intento.

14.9. Si el cubo es depositado correctamente nuevamente durante el mismo intento, se registrará el nuevo tiempo de depósito.

14.10. El cronometraje oficial y la validación de los resultados serán responsabilidad de la organización y de los jueces de la competencia.

---

## 15. Fallos atribuibles al equipo

15.1. Una vez iniciado un intento, no se permitirá reiniciarlo por errores atribuibles al sistema desarrollado por el equipo.

15.2. Se consideran errores atribuibles al equipo, entre otros:

15.2.1. Errores de programación.

15.2.2. Errores de navegación.

15.2.3. Pérdida de coordinación entre los rovers.

15.2.4. Errores en la interpretación de la telemetría.

15.2.5. Problemas en la estrategia desarrollada por el equipo.

15.2.6. Colisiones entre los rovers.

15.2.7. Incapacidad para localizar o transportar un cubo.

15.2.8. Bloqueos del software desarrollado por el equipo.

15.2.9. Decisiones incorrectas tomadas por los rovers.

15.2.10. Que un rover retire accidentalmente un cubo de una zona de acopio.

15.2.11. Que un rover provoque la caída o salida de un cubo de la superficie de competencia.

15.3. Ante cualquiera de estas situaciones, el intento no será reiniciado.

15.4. El cronómetro continuará hasta que se complete la tarea, se alcance el límite de 10 minutos o el juez determine que debe detenerse el intento.

---

## 16. Fallos de infraestructura y alteraciones externas

16.1. Un intento podrá ser repetido cuando el juez determine que ocurrió una falla atribuible a la infraestructura oficial o una alteración del escenario no provocada por los rovers participantes.

16.2. Se consideran posibles fallos de infraestructura oficial:

16.2.1. Fallos del sistema oficial de visión.

16.2.2. Fallos de la cámara superior.

16.2.3. Fallos de la telemetría oficial.

16.2.4. Fallos de la red de comunicación proporcionada por la organización.

16.2.5. Fallos del escenario oficial.

16.2.6. Fallos de los mecanismos utilizados por la organización para iniciar o controlar el estado del intento.

16.3. También se considerará una alteración externa cuando un cubo se desplace, caiga o salga de la superficie de competencia debido a:

16.3.1. Vibraciones del tablero no provocadas por los rovers participantes.

16.3.2. Movimiento accidental de la infraestructura.

16.3.3. Intervención externa involuntaria.

16.3.4. Cualquier otra causa que el juez determine que no fue provocada por los rovers participantes.

16.4. Cuando una alteración de este tipo afecte materialmente el desarrollo del intento, el juez podrá detenerlo y ordenar su repetición desde el inicio.

16.5. En caso de repetición, el escenario será restablecido a sus condiciones iniciales.

16.6. El intento afectado por la falla o alteración externa quedará anulado y no será contabilizado como uno de los dos intentos del equipo.

16.7. Una falla atribuible al código, configuración, comunicación, navegación, coordinación o estrategia desarrollada por el equipo no constituye una falla de infraestructura oficial.

16.8. La determinación de si un incidente fue causado por la infraestructura, por un factor externo o por la acción de los rovers corresponderá a los jueces de la competencia.

16.9. La decisión sobre la repetición de un intento corresponderá a los jueces de la competencia.

---

## 17. Superficie y sistema de coordenadas

17.1. La superficie física de competencia es aproximadamente de **1 m × 1 m** y está formada por una cuadrícula de celdas de 20 mm.

17.2. El área efectiva utilizada por el sistema de visión está determinada por los marcadores visuales oficiales colocados en las esquinas.

17.3. Las dimensiones lógicas de la cancha pueden ser menores que las dimensiones físicas completas de la superficie.

17.4. Los equipos no deberán asumir en su código un número fijo de filas o columnas.

17.5. Los equipos deberán utilizar los valores publicados por el sistema oficial de visión, incluyendo:

17.5.1. Cantidad de columnas.

17.5.2. Cantidad de filas.

17.5.3. Tamaño de cada celda.

17.5.4. Posición de salida.

17.5.5. Posición de las zonas de acopio.

---

## 18. Restricciones técnicas

18.1. No se permite modificar físicamente los rovers.

18.2. No se permite:

18.2.1. Agregar o retirar sensores.

18.2.2. Agregar actuadores.

18.2.3. Agregar mecanismos de recolección.

18.2.4. Cambiar motores, ruedas o baterías.

18.2.5. Alterar el chasis.

18.2.6. Incorporar tarjetas electrónicas adicionales.

18.2.7. Sustituir la electrónica principal.

18.2.8. Utilizar otro robot o plataforma.

18.2.9. Dañar, perforar, cortar o alterar permanentemente los robots entregados.

18.2.10. Utilizar hardware externo como controlador auxiliar durante un intento.

18.2.11. Ejecutar planificación o control en tiempo real desde una computadora externa durante un intento.

18.3. Cualquier modificación física o electrónica no autorizada será motivo de descalificación técnica.

---

# Formato del torneo

## 19. Estructura del torneo

19.1. El torneo se desarrollará en **dos rondas**.

19.2. En la primera ronda participarán todos los equipos inscritos.

19.3. Cada equipo tendrá **dos intentos** durante la primera ronda.

19.4. Para efectos de clasificación se utilizará únicamente el **mejor resultado obtenido por cada equipo en sus dos intentos**.

19.5. Los **10 equipos con mejores resultados** clasificarán a la segunda ronda.

19.6. Los 10 equipos clasificados tendrán **dos nuevos intentos** durante la segunda ronda.

19.7. Para la clasificación final se utilizará únicamente el **mejor resultado obtenido por cada equipo durante la segunda ronda**.

19.8. Los resultados obtenidos durante la primera ronda no se acumulan ni se utilizan para determinar las posiciones finales.

19.9. Los equipos que obtengan los **tres mejores resultados de la segunda ronda** ocuparán las tres primeras posiciones del Vision Rover Challenge.

19.10. Cada intento constituye una ejecución independiente. Los resultados de los dos intentos de una misma ronda no se suman ni se promedian.

---

## 20. Orden de participación

20.1. El orden de participación de los equipos será determinado **aleatoriamente por la organización**.

20.2. La organización podrá distribuir los dos intentos de cada equipo a lo largo de la ronda.

20.3. Los dos intentos de un mismo equipo no necesariamente se realizarán de forma consecutiva.

20.4. La distribución aleatoria busca evitar ventajas asociadas al orden de participación.

20.5. El orden será comunicado por la organización antes del inicio de la ronda correspondiente.

20.6. Los equipos deberán estar preparados para participar cuando sean llamados según el orden establecido.

---

## 21. Selección del mejor intento

21.1. Al finalizar cada ronda, cada equipo tendrá hasta dos resultados correspondientes a sus dos intentos oficiales.

21.2. Para efectos de clasificación se utilizará únicamente el **mejor de los dos intentos**.

21.3. Los resultados de ambos intentos no se sumarán ni se promediarán.

21.4. Para determinar cuál de los dos intentos es mejor se aplicarán los mismos criterios utilizados para la clasificación general.

21.5. Tendrá prioridad el intento con mayor cantidad de cubos correctamente depositados.

21.6. Si ambos intentos tienen la misma cantidad de cubos correctamente depositados, tendrá prioridad el intento con el menor tiempo correspondiente al último cubo completado.

---

## 22. Criterios de clasificación

22.1. El objetivo principal será completar correctamente los tres cubos en el menor tiempo posible.

22.2. Los equipos que completen los tres cubos antes del límite de 10 minutos serán ordenados por el tiempo de depósito del tercer cubo.

22.3. Un equipo que complete tres cubos tendrá prioridad sobre cualquier equipo que complete dos, uno o ningún cubo.

22.4. Un equipo que complete dos cubos tendrá prioridad sobre cualquier equipo que complete uno o ningún cubo.

22.5. Un equipo que complete un cubo tendrá prioridad sobre cualquier equipo que no complete ningún cubo.

22.6. Entre equipos con la misma cantidad de cubos correctamente depositados, tendrá prioridad aquel que haya depositado su último cubo válido en menor tiempo.

22.7. La clasificación se determinará de la siguiente manera:

| Cubos completados | Criterio de clasificación                 |
| ----------------- | ----------------------------------------- |
| 3 cubos           | Menor tiempo de depósito del tercer cubo  |
| 2 cubos           | Menor tiempo de depósito del segundo cubo |
| 1 cubo            | Menor tiempo de depósito del primer cubo  |
| 0 cubos           | Sin tiempo de cubo registrado             |

22.8. Si dos equipos completan dos cubos, tendrá mejor resultado el equipo que haya colocado correctamente su segundo cubo en menor tiempo.

22.9. Si dos equipos completan un cubo, tendrá mejor resultado el equipo que haya colocado correctamente ese cubo en menor tiempo.

22.10. Si ningún cubo fue completado, no existirá un tiempo de cubo para utilizar como criterio de clasificación.

---

## 23. Desempates

23.1. Si dos o más equipos tienen la misma cantidad de cubos correctamente depositados y exactamente el mismo tiempo para el último cubo válido, se utilizará como siguiente criterio el tiempo del cubo anterior.

23.2. Para equipos con tres cubos, si existe empate en el tiempo del tercer cubo, se comparará el tiempo del segundo cubo.

23.3. Si persiste el empate, se comparará el tiempo del primer cubo.

23.4. Para equipos con dos cubos, si existe empate en el tiempo del segundo cubo, se comparará el tiempo del primer cubo.

23.5. Si después de aplicar todos los criterios anteriores persiste un empate que afecte la clasificación a la segunda ronda, se realizará un **intento adicional de desempate** entre los equipos involucrados.

23.6. Si después de aplicar todos los criterios anteriores persiste un empate que afecte alguna de las tres posiciones finales, se realizará un **intento adicional de desempate** entre los equipos involucrados.

23.7. El intento de desempate tendrá las mismas condiciones y duración máxima de 10 minutos establecidas para los demás intentos.

23.8. Si persiste el empate después del intento adicional, la organización podrá realizar nuevos intentos de desempate hasta determinar las posiciones correspondientes.

---

## 24. Clasificación de la primera ronda

24.1. Al finalizar la primera ronda, los equipos serán ordenados según los criterios establecidos en este reglamento.

24.2. Los **10 equipos con mejores resultados** clasificarán a la segunda ronda.

24.3. Para cada equipo se utilizará exclusivamente el mejor de sus dos intentos.

24.4. Los resultados de la primera ronda determinarán únicamente la clasificación a la segunda ronda.

24.5. Los tiempos y resultados obtenidos en la primera ronda no se trasladarán a la segunda ronda.

---

## 25. Clasificación final

25.1. Los 10 equipos clasificados iniciarán la segunda ronda sin ventaja derivada de los resultados obtenidos en la primera ronda.

25.2. Cada equipo tendrá dos intentos durante la segunda ronda.

25.3. Se utilizará el mejor resultado de los dos intentos de cada equipo.

25.4. Los equipos serán ordenados según los criterios de clasificación y desempate establecidos en este reglamento.

25.5. Los **tres equipos con mejores resultados** ocuparán, respectivamente, el primer, segundo y tercer lugar del Vision Rover Challenge.

---

## 26. Penalizaciones y descalificación

26.1. Podrán aplicarse penalizaciones por:

26.1.1. Intervención manual durante el intento.

26.1.2. Salida de un rover de la superficie de competencia.

26.1.3. Incumplimiento de las condiciones de autonomía.

26.1.4. Incumplimiento de las condiciones de inicio o ejecución definidas por la organización.

26.2. Serán causas de descalificación:

26.2.1. Modificar física o electrónicamente un robot.

26.2.2. Agregar o sustituir componentes.

26.2.3. Cambiar el microcontrolador o la tarjeta principal.

26.2.4. Utilizar una plataforma robótica diferente.

26.2.5. Controlar manualmente los robots durante la ejecución.

26.2.6. Utilizar una computadora, teléfono, servicio en la nube u otro sistema externo para tomar decisiones o controlar los rovers durante un intento.

26.2.7. Incumplir las condiciones técnicas establecidas por la organización.

---

## 27. Autoridad de los jueces

27.1. El cronometraje y los registros oficiales de cada intento serán responsabilidad de la organización.

27.2. Los jueces determinarán cuándo un cubo se encuentra correctamente depositado.

27.3. Los jueces determinarán si un incidente fue provocado por un rover, por la infraestructura oficial o por un factor externo.

27.4. Los jueces podrán detener un intento por razones de seguridad o por incumplimiento del reglamento.

27.5. Los jueces determinarán cuándo una falla de infraestructura justifica la anulación y repetición de un intento.

27.6. Cualquier situación no contemplada explícitamente en estas reglas será resuelta por los jueces y la organización del Vision Rover Challenge.

---

# Resumen de lo que NO se puede hacer

| Área                    | ❌ Lo que NO se puede hacer                                  | Ejemplo                                                |
| ----------------------- | ----------------------------------------------------------- | ------------------------------------------------------ |
| **Hardware**            | Modificar físicamente los rovers                            | Cortar, perforar o alterar el robot                    |
| **Chasis**              | Modificar el chasis original                                | Agregar una pala para empujar cubos                    |
| **Componentes**         | Agregar componentes físicos                                 | Añadir piezas impresas en 3D                           |
| **Componentes**         | Retirar componentes                                         | Quitar un sensor                                       |
| **Electrónica**         | Modificar la electrónica                                    | Alterar la tarjeta principal                           |
| **Microcontrolador**    | Sustituir el microcontrolador                               | Cambiar el ESP32 por otro controlador                  |
| **Controladores**       | Agregar tarjetas de desarrollo                              | Incorporar Raspberry Pi, Arduino u otro ESP32          |
| **Sensores**            | Agregar sensores                                            | Añadir LiDAR, cámara, ToF o encoders                   |
| **Sensores**            | Sustituir sensores                                          | Cambiar el ultrasónico por otro modelo                 |
| **Actuadores**          | Agregar actuadores                                          | Incorporar servomotores                                |
| **Manipulación**        | Agregar mecanismos de recolección                           | Pinzas, brazos o palas móviles                         |
| **Motores**             | Cambiar los motores                                         | Instalar motores diferentes                            |
| **Ruedas**              | Cambiar las ruedas                                          | Usar ruedas de otro diámetro                           |
| **Baterías**            | Cambiar el sistema de alimentación                          | Utilizar baterías diferentes                           |
| **Control externo**     | Controlar los rovers durante el intento                     | Teclado, teléfono o control remoto                     |
| **Computadora externa** | Tomar decisiones durante el intento                         | Calcular rutas desde una laptop                        |
| **Nube**                | Utilizar servicios externos para decidir durante el intento | Enviar telemetría a un servicio que determine acciones |
| **Intervención humana** | Tocar o corregir los robots durante el intento              | Reorientar manualmente un rover                        |
| **Cubos**               | Mover manualmente los objetos durante el intento            | Recolocar un cubo desplazado                           |
| **Código**              | Modificar el programa después de `READY`                    | Cambiar parámetros o cargar código nuevo               |
| **Inicio**              | Iniciar manualmente después de `READY`                      | Presionar el botón de la IdeaBoard                     |
