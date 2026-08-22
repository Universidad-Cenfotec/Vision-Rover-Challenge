# Armado de CenfoBot

Esta guía describe, paso a paso, el proceso de ensamblaje físico de **CenfoBot**, siguiendo el orden mostrado en el video de armado.

> **Importante:** durante el montaje, no apriete completamente tornillos ni tiras plásticas hasta que las piezas estén correctamente alineadas. Esto facilita el ajuste de motores, carcasa y cableado.

---

## 1. Preparar los motores

1. Saque los dos motores de sus bolsas junto con sus tornillos y tuercas.
2. Identifique en el chasis las posiciones marcadas para:
   - **Motor 1**
   - **Motor 2**
3. Coloque cada motor en su posición correspondiente.
4. Utilice el soporte o abrazadera (asa) de plástico para sujetar cada motor contra el chasis.
5. Oriente el soporte correctamente:
   - el **lado largo** de la abrazadera debe quedar hacia afuera del motor.
6. Coloque los dos tornillos y las dos tuercas correspondientes a cada motor.
7. Apriete ligeramente los tornillos.

> **No apriete todavía los motores por completo.** Deben poder moverse un poco para facilitar la alineación antes de soldarlos.

---

## 2. Soldar los motores al chasis

1. Ajuste la posición de cada motor hasta que sus terminales queden correctamente alineados con los pines de conexión del chasis.
2. Caliente el cautín.
3. Coloque la punta del cautín de manera que toque simultáneamente:
   - la terminal metálica del motor;
   - el pin correspondiente del chasis.
4. Aplique la soldadura hasta conseguir una unión firme entre ambas piezas.
5. Repita el procedimiento en las conexiones del segundo motor.
6. Revise visualmente las soldaduras antes de continuar.

> Una buena soldadura debe unir eléctricamente el pin del chasis con la terminal del motor, no solamente cubrir una de las dos superficies.

---

## 3. Ajustar los motores y colocar las ruedas

1. Una vez soldados ambos motores, termine de apretar sus tornillos.
2. No ejerza fuerza excesiva al apretar. Si quedan muy apretados impide el movimiento libre del motor.
3. Compruebe que los motores queden firmes y correctamente alineados.
4. Coloque una rueda en el eje de cada motor.
5. Presione cada rueda hasta que quede bien insertada.
6. Puede apoyar suavemente la rueda contra una superficie plana para ayudar a introducirla completamente en el eje.

Al terminar esta etapa, el chasis debe tener instalados los **dos motores y las dos ruedas**.

---

## 4. Preparar el cableado del chasis

Para esta etapa se utilizan cables jumper.

1. Prepare **6 cables jumper** para las conexiones indicadas en el chasis (sensores infrarojos).
2. Prepare además **dos grupos de 2 cables** para los motores.
3. Localice los conectores identificados como:
   - **Motor 1**
   - **Motor 2**
4. Conecte cada grupo de dos cables en su conector correspondiente.
5. Localice el conector **Qwiic**.
6. Inserte el cable Qwiic respetando la orientación del conector.

> El conector Qwiic tiene una orientación definida. No debe forzarse.

7. Acomode también los cables correspondientes a los sensores infrarrojos.
8. Mantenga los cables dirigidos hacia los lados y hacia abajo para que no interfieran posteriormente con la carcasa.

---

## 5. Preparar el sensor de color

El sensor de color requiere cuatro cables soldados directamente a la placa.

### 5.1 Preparar los cables

1. Separe **4 cables jumper** del grupo.
2. Corte uno de los conectores de cada cable.
3. Conserve:
   - un extremo con conector **Dupont**;
   - un extremo con el conductor expuesto para soldadura.
4. Si es necesario, retire una pequeña cantidad de aislamiento para dejar visible el cobre.

### 5.2 Soldar los cables

1. Introduzca cada extremo de cobre en el orificio correspondiente del sensor.
2. Doble ligeramente el cable hacia un lado para mantenerlo temporalmente en posición.
3. Utilice un soporte o tercera mano si dispone de uno.
4. Coloque el cautín de manera que caliente simultáneamente:
   - el anillo metálico del orificio;
   - el conductor de cobre.
5. Aplique soldadura.
6. Repita el proceso en los cuatro puntos.

Una soldadura correcta debe observarse brillante y formar una pequeña unión alrededor del conductor.

7. Corte los excedentes de cable que sobresalgan por la parte posterior.

> **Importante:** no deje filamentos ni excesos de conductor que puedan tocar otros contactos y producir un cortocircuito.

---

## 6. Preparar el sensor ultrasónico

El módulo ultrasónico mostrado tiene **5 pines**, pero para este montaje se utilizan solamente **4**.

1. Separe cuatro cables jumper.
2. Identifique los pines del sensor.
3. Conecte los cables correspondientes a:
   - **VCC**
   - **TRIG / Trigger**
   - **ECHO**
   - **GND / Ground**
4. Deje el pin **OUT** sin conectar.

Al finalizar, solamente el pin **OUT** debe quedar libre.

---

## 7. Instalar el sensor de color en la parte frontal

1. Tome la pieza frontal de acrílico de la carcasa.
2. Retire la película protectora del acrílico.
3. Pase los cables del sensor de color por el orificio destinado al cableado.
4. Coloque el sensor en su posición.
5. Localice los dos pequeños orificios destinados a la tira plástica.
6. Introduzca una tira plástica por uno de los orificios.
7. Pásela por detrás del sensor y sáquela por el segundo orificio, como si estuviera hilvanando.
8. Cierre la tira plástica.
9. Apriétela hasta que el sensor quede firme contra la parte frontal.

> La tira debe sostener el sensor firmemente, pero no es necesario ejercer una fuerza excesiva sobre la placa.

---

## 8. Instalar el sensor ultrasónico

1. Inserte el sensor ultrasónico en las aperturas correspondientes de la parte frontal.
2. Oriente el sensor con **los cables hacia abajo**.
3. Verifique que los dos transductores queden hacia el frente.
4. Puede utilizar temporalmente un pequeño trozo de cinta adhesiva para mantener el sensor en posición mientras termina de armar la carcasa.

---

## 9. Preparar las piezas de la carcasa

1. Identifique:
   - pieza superior;
   - pieza frontal;
   - laterales;
   - pieza trasera.
2. Retire las películas protectoras de las piezas de acrílico.
3. Una inicialmente las piezas con tiras plásticas.
4. Pase cada tira por los pares de orificios correspondientes.
5. Cierre las tiras, pero **no las apriete completamente**.

La carcasa debe quedar parcialmente armada, pero todavía flexible.

> Mantener las tiras ligeramente flojas facilita colocar posteriormente la carcasa sobre el chasis.

---

## 10. Armar la parte superior de la carcasa

1. Una la pieza superior con uno de los laterales.
2. Pase una tira plástica por los orificios correspondientes.
3. Cierre la tira sin apretarla demasiado.
4. Repita el procedimiento con el segundo lateral.
5. Coloque la pieza trasera.
6. Utilice nuevamente las tiras plásticas para unirla.
7. Mantenga todas estas uniones ligeramente sueltas.

En este punto, la cubierta debe poder abrirse y moverse ligeramente.

---

## 11. Colocar los soportes internos de acrílico

En el chasis existen ranuras destinadas a dos piezas internas de acrílico.

1. Identifique las dos piezas rectangulares de soporte.
2. Inserte cada pieza en su ranura correspondiente del chasis.
3. Compruebe que queden verticales y correctamente asentadas.

Estas piezas ayudan a:
- mantener la estructura;
- soportar la parte superior;
- delimitar el espacio de la batería.

---

## 12. Instalar la carcasa sobre el chasis

1. Antes de colocar la cubierta, acomode los cables.
2. Pase los cables por las aperturas laterales correspondientes.
3. Evite dejar cables atravesando el espacio central destinado a la batería.
4. Coloque la carcasa sobre el chasis.
5. Alinee las ranuras de la parte superior con los soportes internos de acrílico.
6. Encaje las piezas hasta formar una estructura tipo **sándwich**:
   - chasis en la parte inferior;
   - soportes de acrílico en el centro;
   - cubierta en la parte superior.
7. Verifique que ninguna pieza esté siendo forzada.

---

## 13. Apretar definitivamente la carcasa

Una vez que todas las piezas estén correctamente alineadas:

1. Revise nuevamente la posición de los cables.
2. Asegúrese de que ningún cable quede atrapado por una tira plástica.
3. Apriete las tiras que anteriormente había dejado sueltas.
4. Coloque las tiras que fijan directamente la carcasa al chasis.
5. Apriételas lo suficiente para obtener una estructura firme.
6. Corte con cuidado los extremos sobrantes de las tiras.
7. Repita el procedimiento en la parte trasera.

> No es necesario apretar las tiras hasta deformar el acrílico. La estructura debe quedar firme, no tensionada excesivamente.

---

## 14. Organizar el cableado interno

Antes de instalar el microcontrolador:

1. Dirija los cables hacia los laterales.
2. Mantenga libre el espacio central.
3. Acueste los cables internos contra las paredes laterales de la carcasa.
4. Compruebe que la batería pueda entrar y salir sin empujar los conectores.

Este paso es importante porque una batería introducida a presión puede:
- desconectar cables;
- doblar conectores;
- dañar una soldadura;
- dificultar el mantenimiento posterior.

---

## 15. Instalar el microcontrolador

1. Coloque la tarjeta del microcontrolador sobre la parte superior del robot.
2. El kit incluye cuatro posiciones de montaje.
3. En esta etapa, utilice solamente **dos tornillos**.
4. Colóquelos en posiciones diagonalmente opuestas.
5. Deje libres las otras dos posiciones.

Las dos posiciones restantes se utilizarán para instalar separadores (**standoffs**) de aproximadamente **2 cm**.

---

## 16. Instalar los standoffs

1. Localice los dos standoffs de aproximadamente 2 cm incluidos en el kit.
2. Instálelos en los dos puntos de montaje que quedaron libres.
3. Verifique que queden verticales.
4. No los apriete excesivamente.

Estos separadores sostienen una pequeña placa superior de acrílico.

---

## 17. Realizar las conexiones electrónicas

Una vez instalado el microcontrolador:

1. Conecte los motores.
2. Conecte los sensores infrarrojos.
3. Conecte el sensor ultrasónico.
4. Conecte el sensor de color.
5. Conecte el cable Qwiic y cualquier otro periférico correspondiente.
6. Verifique cuidadosamente:
   - orientación;
   - polaridad;
   - posición de cada pin;
   - firmeza de los conectores.

> Las conexiones específicas de cada sensor deben realizarse [siguiendo el diagrama de conexiones del proyecto](https://github.com/Universidad-Cenfotec/Vision-Rover-Challenge/blob/main/conexiones/README.md).

---

## 18. Sujetar el cableado

Después de comprobar las conexiones:

1. Utilice las tiras plásticas sobrantes para agrupar o sujetar los cables.
2. Manténgalos hacia los laterales del robot.
3. Compruebe nuevamente que el espacio de la batería permanezca libre.
4. Evite doblar los cables directamente sobre los conectores.
5. Corte los excesos de las tiras plásticas.

---

## 19. Instalar la placa superior

1. Tome la pequeña placa de acrílico destinada a la parte superior.
2. Colóquela sobre los standoffs.
3. Utilice los dos tornillos restantes.
4. Colóquelos en las posiciones correspondientes.
5. Apriete solamente hasta que la placa quede firme.

Esta superficie queda disponible para colocar el elemento o módulo indicado para la parte superior del CenfoBot.

---

## 20. Verificación final

Antes de utilizar el robot, revise el montaje completo.

1. Compruebe que los motores estén firmes.
2. Verifique que las ruedas estén completamente insertadas.
3. Revise visualmente las soldaduras.
4. Compruebe que no existan:
   - cables de cobre expuestos;
   - restos de conductor;
   - soldaduras uniendo contactos vecinos.
5. Verifique que el sensor de color esté firme.
6. Compruebe que el sensor ultrasónico esté orientado hacia el frente.
7. Revise que la carcasa esté firmemente unida al chasis.
8. Compruebe que todos los cables estén fuera del espacio de la batería.
9. Revise los conectores antes de energizar el robot.
10. Confirme que la estructura completa se sienta sólida y que ninguna pieza quede suelta.

Una vez completadas estas verificaciones, **CenfoBot queda listo para continuar con la configuración, programación y pruebas de funcionamiento**.

---

## Recomendaciones de montaje

- No apriete completamente las piezas durante las primeras etapas del armado.
- Haga primero los ajustes de posición y luego el apriete definitivo.
- Mantenga el cautín en contacto tanto con el terminal como con el pin antes de aplicar soldadura.
- Evite acumulaciones excesivas de soldadura.
- Corte todos los extremos de cable y de tiras plásticas que puedan interferir con otros componentes.
- Mantenga siempre libre el espacio destinado a la batería.
- Nunca fuerce un conector que no entre fácilmente.
- Antes de energizar el robot, haga una inspección visual completa del cableado.

