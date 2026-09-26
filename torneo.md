# Formato del torneo y clasificación

## 1. Estructura del torneo

1.1. El torneo se desarrollará en **dos rondas**.

1.2. En la primera ronda participarán todos los equipos inscritos.

1.3. Cada equipo tendrá **dos intentos** durante la primera ronda.

1.4. Para efectos de clasificación se utilizará únicamente el **mejor resultado obtenido por cada equipo en sus dos intentos**.

1.5. Los **10 equipos con mejores resultados** clasificarán a la segunda ronda.

1.6. Los 10 equipos clasificados tendrán **dos nuevos intentos** durante la segunda ronda.

1.7. Para la clasificación final se utilizará únicamente el **mejor resultado obtenido por cada equipo durante la segunda ronda**.

1.8. Los resultados obtenidos durante la primera ronda no se acumulan ni se utilizan para determinar las posiciones finales.

1.9. Los equipos que obtengan los **tres mejores resultados de la segunda ronda** ocuparán las tres primeras posiciones del Vision Rover Challenge.

1.10. Cada intento constituye una ejecución independiente. Los resultados de los dos intentos de una misma ronda no se suman ni se promedian.

---

## 2. Orden de participación

2.1. El orden de participación de los equipos será determinado **aleatoriamente por la organización**.

2.2. La organización podrá distribuir los dos intentos de cada equipo a lo largo de la ronda.

2.3. Los dos intentos de un mismo equipo no necesariamente se realizarán de forma consecutiva.

2.4. La distribución aleatoria busca evitar ventajas asociadas al orden de participación y distribuir los intentos de los equipos durante el desarrollo de cada ronda.

2.5. El orden será comunicado por la organización antes del inicio de la ronda correspondiente.

2.6. Los equipos deberán estar preparados para participar cuando sean llamados según el orden establecido.

---

## 3. Preparación del escenario

3.1. Antes de cada intento, la organización restablecerá el escenario de competencia según la configuración oficial correspondiente.

3.2. Los cubos serán colocados en las condiciones iniciales definidas al azar para cada intento, utilizando el [criterio definido acá](https://github.com/Universidad-Cenfotec/Vision-Rover-Challenge/tree/main/docs). Inicio de rovers, zonas de acopio no cambian.

3.3. Todos los equipos competirán bajo las mismas condiciones oficiales establecidas para la ronda.

3.4. Una vez preparado el escenario, el sistema oficial de visión establecerá el estado `IDLE` durante **1 minuto**.

3.5. Durante el estado `IDLE`, los rovers deberán estar encendidos, programados, conectados al sistema de visión y preparados para ejecutar la prueba.

3.6. Durante este período los equipos podrán realizar únicamente las acciones de preparación permitidas por el reglamento general de la competencia.

3.7. El período de 1 minuto en estado `IDLE` no forma parte del tiempo oficial del intento.

---

## 4. Inicio del intento

4.1. Finalizado el período de 1 minuto en estado `IDLE`, el sistema oficial de visión cambiará al estado `READY`.

4.2. Los rovers deberán detectar el estado `READY` a través de la telemetría oficial.

4.3. La detección del estado `READY` deberá provocar automáticamente el inicio de la estrategia desarrollada por el equipo.

4.4. El cambio del sistema de visión al estado `READY` marca el **inicio oficial del intento y del cronometraje**.

4.5. No se permitirá intervención humana para iniciar los rovers después del cambio a `READY`.

4.6. No se permitirá presionar botones para iniciar la estrategia después del cambio a `READY`.

4.7. La detección de `READY` y el inicio de la ejecución deberán formar parte del software desarrollado por el equipo.

4.8. La secuencia general de inicio será:

**Preparación → `IDLE` durante 1 minuto → `READY` → inicio automático de los rovers**

---

## 5. Duración y finalización del intento

5.1. Cada intento tendrá una duración máxima de **10 minutos**.

5.2. Los 10 minutos se medirán a partir del cambio del sistema oficial de visión al estado `READY`.

5.3. El intento finalizará cuando ocurra alguna de las siguientes condiciones:

5.3.1. Los tres cubos se encuentren correctamente depositados en sus respectivas zonas de acopio.

5.3.2. Se alcance el límite máximo de 10 minutos.

5.3.3. El juez detenga el intento por razones de seguridad.

5.3.4. El juez detenga el intento por incumplimiento del reglamento.

5.3.5. Ocurra una falla de infraestructura que, a criterio del juez, haga imposible continuar el intento en condiciones válidas.

5.4. Si el equipo completa correctamente los tres cubos antes de los 10 minutos, se registrará el tiempo transcurrido desde el cambio a `READY` hasta que el tercer cubo quede correctamente depositado.

---

## 6. Autonomía durante el intento

6.1. La ejecución autónoma comienza formalmente cuando el sistema oficial de visión cambia del estado `IDLE` al estado `READY`.

6.2. A partir de ese momento los rovers deberán ejecutar automáticamente la estrategia desarrollada por el equipo.

6.3. No se permitirá tocar los robots.

6.4. No se permitirá presionar botones para iniciar, reiniciar o modificar su comportamiento.

6.5. No se permitirá modificar el código.

6.6. No se permitirá reiniciar los robots.

6.7. No se permitirá enviar comandos desde una computadora, teléfono u otro dispositivo.

6.8. No se permitirá modificar parámetros o configuraciones.

6.9. No se permitirá controlar manualmente los rovers.

6.10. No se permitirá que una computadora, teléfono, servicio en la nube u otro sistema externo tome decisiones por los rovers.

6.11. No se permitirá mover manualmente los cubos ni ningún otro elemento del escenario.

6.12. Los rovers deberán detectar el estado `READY`, iniciar su estrategia y ejecutar la tarea de manera autónoma.

---

## 7. Validez de los cubos depositados

7.1. Un cubo se considerará correctamente depositado cuando se encuentre **completamente dentro de su zona de acopio correspondiente**.

7.2. El tiempo de depósito de un cubo corresponderá al momento, medido desde el cambio a `READY`, en que el cubo quede correctamente depositado.

7.3. Un cubo correctamente depositado deberá permanecer en una condición válida durante el resto del intento.

7.4. Si posteriormente uno de los rovers retira accidentalmente un cubo de su zona de acopio, el cubo dejará de considerarse correctamente depositado.

7.5. Si un rover provoca que un cubo salga de la superficie de competencia, caiga del tablero o quede fuera del área válida de juego, ese cubo se considerará **no depositado**.

7.6. En los casos establecidos en 7.4 y 7.5, cualquier registro previo de depósito del cubo quedará sin efecto.

7.7. Para efectos de cantidad de cubos completados, tiempo y clasificación, se considerará como si ese cubo **no hubiera sido depositado correctamente durante el intento**.

7.8. Los jueces no recolocarán manualmente un cubo que haya sido desplazado, retirado de su zona de acopio o expulsado de la superficie como consecuencia de las acciones de los rovers.

7.9. Si el cubo permanece dentro del área válida de competencia, los rovers podrán intentar colocarlo nuevamente en su zona de acopio mientras quede tiempo disponible.

7.10. Si el cubo vuelve a ser correctamente depositado, se registrará como tiempo válido el correspondiente a este **nuevo depósito correcto**.

---

## 8. Registro oficial del intento

8.1. Durante cada intento se registrará la cantidad de cubos correctamente depositados.

8.2. Se registrará el tiempo de depósito correcto del primer cubo.

8.3. Se registrará el tiempo de depósito correcto del segundo cubo, cuando corresponda.

8.4. Se registrará el tiempo de depósito correcto del tercer cubo, cuando corresponda.

8.5. Si los tres cubos son completados, el tiempo del tercer cubo constituirá el tiempo total de finalización.

8.6. Todos los tiempos se medirán a partir del momento en que el sistema oficial de visión cambie al estado `READY`.

8.7. Solamente se utilizarán para la clasificación los tiempos correspondientes a cubos que permanezcan válidamente depositados al finalizar el intento.

8.8. Si un cubo pierde posteriormente su condición de depósito válido, su tiempo anterior será eliminado del resultado del intento.

8.9. Si el cubo es depositado correctamente de nuevo durante el mismo intento, se registrará el nuevo tiempo de depósito.

8.10. El cronometraje oficial y la validación de los resultados serán responsabilidad de la organización y de los jueces de la competencia.

---

## 9. Fallos atribuibles al equipo

9.1. Una vez iniciado un intento, no se permitirá reiniciarlo por errores atribuibles al sistema desarrollado por el equipo.

9.2. Se consideran errores atribuibles al equipo, entre otros:

9.2.1. Errores de programación.

9.2.2. Errores de navegación.

9.2.3. Pérdida de coordinación entre los rovers.

9.2.4. Errores en la interpretación de la telemetría.

9.2.5. Problemas en la estrategia desarrollada por el equipo.

9.2.6. Colisiones entre los rovers.

9.2.7. Incapacidad para localizar o transportar un cubo.

9.2.8. Bloqueos del software desarrollado por el equipo.

9.2.9. Decisiones incorrectas tomadas por los rovers.

9.2.10. Que un rover retire accidentalmente un cubo de una zona de acopio.

9.2.11. Que un rover provoque la caída o salida de un cubo de la superficie de competencia.

9.3. Ante cualquiera de estas situaciones, el intento no será reiniciado.

9.4. El cronómetro continuará hasta que se complete la tarea, se alcance el límite de 10 minutos o el juez determine que debe detenerse el intento.

---

## 10. Fallos de infraestructura y alteraciones externas

10.1. Un intento podrá ser repetido cuando el juez determine que ocurrió una falla atribuible a la infraestructura oficial o una alteración del escenario no provocada por los rovers participantes.

10.2. Se consideran posibles fallos de infraestructura oficial:

10.2.1. Fallos del sistema oficial de visión.

10.2.2. Fallos de la cámara superior.

10.2.3. Fallos de la telemetría oficial.

10.2.4. Fallos de la red de comunicación proporcionada por la organización.

10.2.5. Fallos del escenario oficial.

10.2.6. Fallos de los mecanismos utilizados por la organización para iniciar o controlar el estado de la ronda.

10.3. También se considerará una alteración externa cuando un cubo se desplace, caiga o salga de la superficie de competencia debido a:

10.3.1. Vibraciones del tablero no provocadas por los rovers participantes.

10.3.2. Movimiento accidental de la infraestructura.

10.3.3. Intervención externa involuntaria.

10.3.4. Cualquier otra causa que el juez determine que no fue provocada por los rovers participantes.

10.4. Cuando una alteración de este tipo afecte materialmente el desarrollo del intento, el juez podrá detenerlo y ordenar su repetición desde el inicio.

10.5. En caso de repetición, el escenario será restablecido a sus condiciones iniciales.

10.6. El intento afectado por la falla o alteración externa quedará anulado y no será contabilizado como uno de los dos intentos del equipo.

10.7. Una falla atribuible al código, configuración, comunicación, navegación, coordinación o estrategia desarrollada por el equipo no constituye una falla de infraestructura oficial.

10.8. La determinación de si un incidente fue causado por la infraestructura, por un factor externo o por la acción de los rovers corresponderá a los jueces de la competencia.

10.9. La decisión sobre la repetición de un intento corresponderá a los jueces de la competencia.

---

## 11. Selección del mejor intento

11.1. Al finalizar cada ronda, cada equipo tendrá hasta dos resultados correspondientes a sus dos intentos oficiales.

11.2. Para efectos de clasificación se utilizará únicamente el **mejor de los dos intentos**.

11.3. Los resultados de ambos intentos no se sumarán ni se promediarán.

11.4. Para determinar cuál de los dos intentos es mejor se aplicarán los mismos criterios utilizados para la clasificación general.

11.5. Tendrá prioridad el intento con mayor cantidad de cubos correctamente depositados.

11.6. Si ambos intentos tienen la misma cantidad de cubos correctamente depositados, se utilizará el menor tiempo correspondiente al último cubo completado.

---

## 12. Criterios de clasificación

12.1. El objetivo principal será completar correctamente los tres cubos en el menor tiempo posible.

12.2. Los equipos que completen los tres cubos antes del límite de 10 minutos serán ordenados por el tiempo de finalización del tercer cubo.

12.3. Un equipo que complete tres cubos tendrá prioridad sobre cualquier equipo que complete dos, uno o ningún cubo.

12.4. Un equipo que complete dos cubos tendrá prioridad sobre cualquier equipo que complete uno o ningún cubo.

12.5. Un equipo que complete un cubo tendrá prioridad sobre cualquier equipo que no complete ningún cubo.

12.6. Entre equipos con la misma cantidad de cubos correctamente depositados, tendrá prioridad aquel que haya depositado su último cubo válido en menor tiempo.

12.7. La clasificación se determinará de la siguiente manera:

| Cubos completados | Criterio de clasificación                 |
| ----------------- | ----------------------------------------- |
| 3 cubos           | Menor tiempo de depósito del tercer cubo  |
| 2 cubos           | Menor tiempo de depósito del segundo cubo |
| 1 cubo            | Menor tiempo de depósito del primer cubo  |
| 0 cubos           | Sin tiempo de cubo registrado             |

12.8. Si dos equipos completan dos cubos, tendrá mejor resultado el equipo que haya colocado correctamente su segundo cubo en menor tiempo.

12.9. Si dos equipos completan un cubo, tendrá mejor resultado el equipo que haya colocado correctamente ese cubo en menor tiempo.

12.10. Si ningún cubo fue completado, no existirá un tiempo de cubo para utilizar como criterio de clasificación.

---

## 13. Desempates

13.1. Si dos o más equipos tienen la misma cantidad de cubos correctamente depositados y exactamente el mismo tiempo para el último cubo válido, se utilizará como siguiente criterio el tiempo del cubo anterior.

13.2. Para equipos con tres cubos, si existe empate en el tiempo del tercer cubo, se comparará el tiempo del segundo cubo.

13.3. Si persiste el empate, se comparará el tiempo del primer cubo.

13.4. Para equipos con dos cubos, si existe empate en el tiempo del segundo cubo, se comparará el tiempo del primer cubo.

13.5. Si después de aplicar todos los criterios anteriores persiste un empate que afecte la clasificación a la segunda ronda, se realizará un **intento adicional de desempate** entre los equipos involucrados.

13.6. Si después de aplicar todos los criterios anteriores persiste un empate que afecte alguna de las tres posiciones finales, se realizará un **intento adicional de desempate** entre los equipos involucrados.

13.7. El intento de desempate tendrá las mismas condiciones y duración máxima de 10 minutos establecidas para los demás intentos.

13.8. Si persiste el empate después del intento adicional, la organización podrá realizar nuevos intentos de desempate hasta determinar las posiciones correspondientes.

---

## 14. Clasificación de la primera ronda

14.1. Al finalizar la primera ronda, los equipos serán ordenados según los criterios establecidos en las secciones 11, 12 y 13.

14.2. Los **10 equipos con mejores resultados** clasificarán a la segunda ronda.

14.3. Para cada equipo se utilizará exclusivamente el mejor de sus dos intentos.

14.4. Los resultados de la primera ronda determinarán únicamente la clasificación a la segunda ronda.

14.5. Los tiempos y resultados obtenidos en la primera ronda no se trasladarán a la segunda ronda.

---

## 15. Clasificación final

15.1. Los 10 equipos clasificados iniciarán la segunda ronda sin ventaja derivada de los resultados obtenidos en la primera ronda.

15.2. Cada equipo tendrá dos intentos durante la segunda ronda.

15.3. Se utilizará el mejor resultado de los dos intentos de cada equipo.

15.4. Los equipos serán ordenados según los mismos criterios de clasificación y desempate establecidos en este reglamento.

15.5. Los **tres equipos con mejores resultados** ocuparán, respectivamente, el primer, segundo y tercer lugar del Vision Rover Challenge.

---

## 16. Autoridad de los jueces

16.1. El cronometraje y los registros oficiales de cada intento serán responsabilidad de la organización.

16.2. Los jueces determinarán cuándo un cubo se encuentra correctamente depositado.

16.3. Los jueces determinarán si un incidente fue provocado por un rover, por la infraestructura oficial o por un factor externo.

16.4. Los jueces podrán detener un intento por razones de seguridad o por incumplimiento del reglamento.

16.5. Los jueces determinarán cuándo una falla de infraestructura justifica la anulación y repetición de un intento.

16.6. Cualquier situación no contemplada explícitamente en estas reglas será resuelta por los jueces y la organización del Vision Rover Challenge.
