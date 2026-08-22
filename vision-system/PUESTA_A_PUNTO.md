# Puesta a punto de la cámara

**Guía paso a paso para dejar tu cámara lista para la competencia.**

Si te dieron una cámara y no sabés nada del sistema por dentro, este documento
es para vos. Se sigue de arriba abajo, sin saltar a ningún otro documento
mientras trabajás. Todo lo que tenés que hacer con las manos está acá.

No hace falta que entiendas cómo funciona el sistema por dentro. Al final hay
enlaces por si te da curiosidad.

**Tiempo estimado:** una hora la primera vez, contando la impresión.

---

## Antes de empezar

Repasá esta lista. Si algo falta, resolvelo antes de seguir: cada paso supone
que el anterior salió bien.

| | Qué necesitás | Cómo sabés que está listo |
|---|---|---|
| 1 | **La cámara conectada** por USB | La ves en el sistema operativo |
| 2 | **El sistema instalado** | El paso 0 de acá abajo no da error |
| 3 | **El tablero montado**, con los cuatro marcadores de esquina pegados | Ver [`MONTAJE.md`](MONTAJE.md). Solo hace falta para el paso 5 |
| 4 | **Una impresora** | — |
| 5 | **Una regla o cinta métrica** con milímetros | La vas a usar para comprobar que las hojas salieron del tamaño correcto |
| 6 | **Cartón, cartulina gruesa o una tabla lisa** | Para pegar el patrón y que quede rígido |

### Paso 0 — Comprobar que el sistema anda

Parado en la carpeta `vision-system/`:

```bash
.venv/bin/python -m vision.tools.verificar_geometria
```

Tiene que terminar con:

```
RESULTADO GENERAL: TODO OK
```

Esto no usa la cámara: comprueba que el sistema está bien instalado. Si da
error acá, no sigas: el problema es la instalación, no tu cámara.

> **En Windows** el comando es `.venv\Scripts\python -m vision.tools.verificar_geometria`.
> El resto de los comandos cambia igual: `.venv/bin/python` → `.venv\Scripts\python`.

---

## 1. Qué vas a hacer, y por qué

Toda cámara con lente ancho **curva las líneas rectas**. Es física del lente, no
un defecto: mirá una foto tuya con gran angular y vas a ver los bordes
combados.

Eso es un problema para nosotros, porque el sistema calcula dónde está cada
cosa **suponiendo que las líneas rectas se ven rectas**. Si el lente las curva,
las posiciones salen corridas.

La solución no es cambiar la cámara: es **medir cuánto curva la tuya**, guardar
esa medida, y descontarla en cada imagen. Eso es lo que vas a hacer.

| Paso | Qué hacés | Para qué |
|---|---|---|
| **2** | Imprimir dos hojas | Son las reglas patrón contra las que se mide |
| **3** | Elegir tu cámara | Que el sistema abra la correcta y no la de la laptop |
| **4** | Calibrar | Medir cuánto curva tu lente y guardarlo como **tu perfil** |
| **5** | Verificar a ojo | Confirmar que la corrección funciona de verdad |
| **6** | Medir la precisión | Saber con cuántos milímetros de error ubica tu cámara |

Cada cámara tiene **su propio perfil**. Calibrar la tuya no pisa la de nadie.

---

## 2. Imprimir las hojas

> ### ⚠️ Este es el paso donde más gente se equivoca
>
> Si la hoja sale impresa a un tamaño distinto del que dice, **todo lo demás
> queda mal en silencio**: la calibración va a dar un número que parece bueno y
> va a estar escalado. No hay ningún aviso. Por eso hay que medir con la regla.

Vas a imprimir **dos cosas distintas**.

### 2.1 — El patrón de calibración

```bash
.venv/bin/python -m vision.tools.patron_calibracion --salida patron.pdf
```

Te va a decir exactamente qué generó:

```
  archivo         : .../patron.pdf
  esquinas internas: 13 x 6
  cuadros          : 14 x 7 de 25.0 mm
  patrón completo  : 350 x 175 mm
  papel            : carta horizontal (279 x 216 mm)
  hojas de patrón  : 2 (+1 de instrucciones)
  ATENCIÓN: hay que cortar por la línea gris y pegar a tope.
```

Son **tres páginas**: dos con el ajedrezado y una con las instrucciones
impresas, para que las tengas al lado mientras armás.

### 2.2 — El marcador de prueba

```bash
.venv/bin/python -m vision.tools.patron_calibracion --marcador-prueba 20
```

Es una sola hoja con un cuadrado blanco y negro. Lo vas a usar en el paso 6.

### 2.3 — Cómo imprimir, que es lo que importa

En el diálogo de impresión, buscá la opción de escala:

| Poné esto | **Nunca** esto |
|---|---|
| **Escala: 100 %** | ~~Ajustar a la página~~ |
| **Tamaño real** | ~~Encoger para que entre~~ |
| **Sin escalar** | ~~Ajustar al área imprimible~~ |

"Ajustar a la página" suele encoger al 94–97 % **sin avisarte**. Un 3 % de error
acá se convierte en un 3 % de error en todas las posiciones que publique el
sistema.

### 2.4 — Comprobar con la regla, siempre

Cada hoja lleva impresa al pie una **línea de 100 mm**. Medila:

- **Mide 100 mm** → salió bien, seguí.
- **Mide otra cosa** → volvé a imprimir con la escala correcta. No sigas.

Es diez segundos y te ahorra repetir todo el proceso.

> Si tu impresora no logra el 100 % exacto, hay una salida: medí el lado de un
> cuadro del ajedrezado con la regla y anotá ese valor. Después pedí ayuda para
> ajustar `lado_mm` en la configuración. **No sigas con un valor supuesto.**

### 2.5 — Armar el patrón

Las dos hojas del ajedrezado forman **un solo patrón** de 350 × 175 mm:

1. **Cortá** una de las hojas por la línea gris marcada.
2. **Pegá las dos a tope**: los bordes se tocan, no se superponen ni queda
   espacio. Los cuadros tienen que continuar sin escalón.
3. **Pegá todo el conjunto** sobre cartón, cartulina gruesa o una tabla lisa,
   con pegamento en **toda la superficie** y no solo en los bordes.

> ### ⚠️ El patrón tiene que quedar PLANO
>
> Es la condición más importante. La calibración supone que el patrón es un
> plano perfecto: **cada ondulación la interpreta como distorsión de tu lente**,
> y te ensucia la medición sin que nada avise.
>
> Un patrón chico perfectamente plano calibra mejor que uno grande combado.
> Pegado solo por los bordes se va a curvar en el medio: pegalo entero.

**Antes de seguir, verificá:** apoyá el patrón en una mesa y miralo a ras. No
tiene que haber ondas, burbujas ni escalón en el empalme.

### 2.6 — Recortar el marcador de prueba

El marcador se recorta **dejando el borde blanco** que trae alrededor. Ese
borde no es decoración: el detector encuentra el marcador por el contraste
entre el negro y el blanco de alrededor. Si lo recortás al ras del negro,
**el marcador deja de existir para el sistema**.

Pegalo también sobre algo rígido y fino, y que quede plano.

---

## 3. Elegir tu cámara

Si tenés más de una cámara —por ejemplo la webcam USB y la integrada de la
laptop—, el sistema tiene que abrir la correcta.

Para ver cuáles responden:

```bash
.venv/bin/python -m vision.tools.diagnostico_camara --listar
```

Y para probar que la que elegís es la buena:

```bash
.venv/bin/python -m vision.tools.diagnostico_camara
```

Se abre una ventana con el video en vivo. **Mirá la imagen**: si estás viendo
tu propia cara, es la de la laptop; si ves lo que apunta la cámara del tablero,
es la correcta. Cerrá con `Q`.

Si abrió la equivocada, probá con otro número:

```bash
.venv/bin/python -m vision.tools.diagnostico_camara --indice 1
```

> ### ⚠️ El nombre no te dice el número
>
> Podrías pensar que si el sistema lista "Logitech C270" primero, esa es el
> índice 0. **No es así**: el orden en que el sistema operativo lista las
> cámaras y el orden de los números que usa el programa **no coinciden** —lo
> comprobamos, y estaban al revés—.
>
> Por eso el programa te muestra los nombres y los números por separado, y no
> te miente apareándolos. La forma segura de saber cuál es cuál es **mirar la
> imagen**.

Anotá el número que funcionó. Si no es el 0, vas a tener que agregar
`--indice N` a todos los comandos que siguen.

Mientras tenés la ventana abierta, aprovechá y mirá el panel: te dice los
cuadros por segundo reales, qué ajustes aceptó tu cámara y, si la apuntás al
tablero armado, **si ve los cuatro marcadores de esquina**.

---

## 4. Crear el perfil de tu cámara

Acá se mide cuánto curva tu lente.

```bash
.venv/bin/python -m vision.tools.calibrar_camara --camara "Logitech C270"
```

**Cambiá `"Logitech C270"` por el nombre de tu cámara.** Ese nombre es lo que
decide en qué archivo se guarda tu perfil, así que dos cámaras con nombres
distintos nunca se pisan. Poné algo que reconozcas: la marca y el modelo.

> Si no ponés `--camara`, el programa te lo pregunta antes de guardar. Es lo
> mismo; ponerlo desde el principio es más cómodo.

### 4.1 — Qué vas a ver

Se abre una ventana con el video y un panel arriba a la izquierda:

```
PATRON: DETECTADO
quieto: si

CAPTURAS: 7 de 15
zonas ##.   distancias 2/3   inclinadas 3/4
      .#.
      ..#

> mover el patron a las zonas vacias · inclinarlo mas (3 de 4)

[C] calibrar   [espacio] capturar   [D] borrar ultima   [Q] salir
```

Qué significa cada cosa:

| Línea | Qué te dice |
|---|---|
| `PATRON: DETECTADO` | Está viendo el ajedrezado. Si dice `no se ve`, acercalo o mejorá la luz |
| `quieto: si` | El patrón está firme. Solo captura cuando está quieto |
| `CAPTURAS: 7 de 15` | Cuántas lleva |
| `zonas ##.` (tres filas) | Un mapa de 3×3 del cuadro de la cámara. Cada `#` es una zona ya cubierta, cada `.` una que falta |
| `distancias 2/3` | Si lo mostraste de cerca, a media distancia y de lejos |
| `inclinadas 3/4` | Cuántas vistas tomó con el patrón inclinado |
| `> ...` | **Lo que te falta hacer.** Seguí esta línea |

### 4.2 — Cómo mover el patrón

**No se trata de sacar quince fotos.** Se trata de mostrarle el patrón en
posiciones **variadas**, y el panel te va diciendo cuál falta.

La herramienta **captura sola** cuando ve el patrón, lo ve quieto, y esa
posición aporta algo que todavía no tenía. Vos solo tenés que moverlo y
esperar un segundo en cada posición.

Lo que hay que cubrir:

1. **Las nueve zonas del cuadro.** Llevá el patrón a las esquinas, a los
   costados, arriba, abajo y al centro. Mirá el mapa de `#` y `.` para saber
   cuál falta. Las esquinas son las más importantes: **es donde el lente más
   distorsiona**.
2. **Tres distancias.** Cerca, a media distancia, lejos.
3. **Al menos cuatro vistas inclinadas.** Girá el patrón: que se vea en
   diagonal, no siempre de frente.

> **Por qué importa la variedad.** Quince fotos todas de frente y en el centro
> dan un error que *parece* excelente y una calibración equivocada. Lo medimos:
> ocho vistas frontales daban un error de 0,14 px —buenísimo— con un **20 % de
> desvío** en la distancia focal. El número no delata la falta de variedad; el
> contador del panel sí. **Por eso seguí la línea `>` y no el número de
> capturas.**

Cuando el panel diga:

```
> ya alcanza: apreta C para calibrar
```

apretá **`C`**.

### 4.3 — El resultado

Después de calcular unos segundos, vas a ver:

```
========================================================================
RESULTADO:  error de reproyección 0.206 px   ->   EXCELENTE
========================================================================
  La calibracion es muy buena. Se puede usar tal cual.
```

**Qué hacer según la palabra que aparezca:**

| Veredicto | Qué hacer |
|---|---|
| **EXCELENTE** | Listo. Pasá al paso 5 |
| **BUENA** | Listo. Pasá al paso 5 |
| **ACEPTABLE** | Sirve, pero conviene repetir. Si repetís, ganás precisión |
| **MALA — HAY QUE REPETIRLA** | **No se guarda el perfil.** Hay que rehacerla |

Si sale **MALA**, el programa te imprime las causas más frecuentes en orden. La
número uno, lejos, es **que el patrón no esté plano**. Las otras: fotos
movidas, poca variedad de vistas, o que el tamaño del cuadro impreso no
coincida con el que espera la configuración.

Si salió bien, vas a ver dónde quedó tu perfil:

```
  perfil de "Logitech C270" guardado en: .../vision/calibraciones/logitech_c270.json
```

> Si ya existía un perfil con ese nombre, te avisa qué contiene y te pregunta
> antes de pisarlo. Ante la duda, contestá que no y usá otro nombre.

---

## 5. Verificar la corrección con los ojos

El número del paso anterior **puede mentir**: si el patrón estaba mal impreso,
la calibración es coherente consigo misma y el error sale bajo igual. Por eso
hay que mirar.

```bash
.venv/bin/python -m vision.tools.calibrar_camara --verificar --camara "Logitech C270"
```

Se abre una ventana partida en dos: a la izquierda la imagen **original**, a la
derecha la **corregida**. Encima hay una rejilla de líneas naranjas que son
**perfectamente rectas**.

**Apuntá la cámara a algo que sepas que es recto**: el borde del tablero, las
líneas de la cancha, el marco de una puerta.

### Qué tenés que ver

Lo que a la **izquierda** se ve combado —sobre todo cerca de los bordes— a la
**derecha** tiene que verse recto, alineado con las líneas naranjas.

Si además ponés el patrón de calibración a la vista, el panel agrega la medida
numérica:

```
Rectitud    curvatura de las filas: 4.89 px → 0.001 px
```

Ese es el resultado que buscás: un número grande a la izquierda de la flecha y
casi cero a la derecha.

### Los avisos del panel

| Lo que dice | Qué significa | Qué hacer |
|---|---|---|
| **El perfil CORRIGE** | Las líneas rectas quedan rectas | Todo bien. Seguí |
| **EL PERFIL NO CORRESPONDE** | El perfil que se cargó **no es de esta cámara** | Ver abajo |

Si aparece **EL PERFIL NO CORRESPONDE**, casi siempre es porque se cargó el
perfil de otra cámara. Volvé a correr el comando poniendo tu nombre exacto en
`--camara`. Si tu nombre no aparece, es que todavía no calibraste esa cámara:
volvé al paso 4.

> Este aviso **avisa pero no bloquea**: podés seguir mirando. A veces uno quiere
> aplicar a propósito el perfil de otra cámara justamente para ver qué pasa.

Teclas: `R` prende y apaga la rejilla · `A` cambia el recorte · `G` guarda una
captura de pantalla · `Q` sale.

---

## 6. Medir la precisión de ubicación

Ya sabés que la corrección funciona. Falta el número que de verdad importa:
**¿con cuántos milímetros de error ubica tu cámara los objetos?**

Para esto **el tablero tiene que estar montado** con sus cuatro marcadores de
esquina ([`MONTAJE.md`](MONTAJE.md)), y la cámara puesta en su posición
definitiva.

```bash
.venv/bin/python -m vision.tools.precision_ubicacion --camara "Logitech C270"
```

Arriba de todo te imprime el criterio con el que se va a juzgar y los datos de
la prueba. Leelo antes de empezar.

### 6.1 — Cómo se mide, y por qué así

No se mide "dónde está" el marcador, sino **cuánto se movió**.

Ponés el marcador de prueba en un punto, lo capturás, lo corrés una cantidad
exacta de cuadros de la cuadrícula, y lo capturás de nuevo. El sistema compara
la distancia que él calcula contra la distancia real, que vos sabés con
exactitud porque **contaste cuadros** y cada cuadro mide 20 mm.

> **Por qué un desplazamiento y no una posición.** Medir una posición absoluta
> exigiría ubicar el origen con precisión de milímetros, y eso mete de vuelta el
> error humano que queremos evitar. Una distancia no necesita saber dónde está
> el origen: se cancela al restar.

### 6.2 — El recorrido

La herramienta te guía por **cinco zonas** —el centro y las cuatro esquinas de
la cancha— y en cada una mide en **horizontal y vertical**. En pantalla vas a
ver:

```
Precisión de ubicación · paso 3 de 10

1) Alineá el marcador a la cuadrícula en esta zona
2) ESPACIO para capturar el punto A
3) Movelo 10 cuadros hacia DERECHA = 200 mm
4) ESPACIO para capturar el punto B
```

Seguí los cuatro pasos en orden. Teclas: `ESPACIO` captura · `R` reinicia la
zona si te equivocaste · `S` la saltea · `Q` termina.

### 6.3 — Colocar el marcador y contar los cuadros

La cuadrícula del tablero es tu regla: cada cuadro mide exactamente 20 mm, así
que **contar cuadros te da la distancia real** sin necesidad de medir nada.

- **Alineá un borde** del marcador con una línea de la cuadrícula, y usá ese
  mismo borde como referencia en los dos puntos, el A y el B.
- **Contá los cuadros** que te indica la pantalla y corré el marcador esa
  distancia, en la dirección que te pide.
- El marcador tiene que quedar **plano sobre el tablero**, con sus cuatro
  esquinas a la vista de la cámara.

### 6.4 — Mensajes que pueden aparecer

| Mensaje | Qué pasa | Qué hacer |
|---|---|---|
| `faltan marcadores de esquina: no se puede medir` | No ve los cuatro marcadores | Revisá que estén completos, iluminados y sin nada encima |
| `no se pudo ver el marcador el tiempo suficiente` | No detecta el marcador de prueba | Mejorá la luz, evitá reflejos, comprobá que quedó plano |
| `demasiado cerca de un marcador de esquina` | El punto está muy al borde | Corré el marcador hacia adentro de la cancha |

### 6.5 — Leer el resultado

Al terminar vas a ver una tabla por zona y un resumen:

```
  error máximo : 1.01 mm   (en superior-derecha, horizontal)
  error medio  : 0.47 mm
  ruido típico : 0.17 mm   (repetibilidad de la cámara)
```

**El número que decide es el error máximo**, comparado contra el criterio que
la herramienta imprimió al principio. Si el máximo está por debajo, tu cámara
sirve.

Para comparar todas las cámaras que se hayan medido:

```bash
.venv/bin/python -m vision.tools.precision_ubicacion --comparar
```

```
  cámara                 resolución    err. máx   err. med     ruido  veredicto
  ArgomTech CAM40        1920x1080      1.58 mm    0.75 mm   0.16 mm  SIRVE
  Logitech C270          1280x720       1.01 mm    0.47 mm   0.17 mm  SIRVE
```

Muestra **la última medición de cada cámara, no la mejor**: quedarse con la
mejor escondería una cámara que falla seguido. Las anteriores no se borran; se
ven con `--historial`.

> **Un dato que te puede tranquilizar:** las dos cámaras medidas quedaron muy
> por debajo del criterio, y la de menor resolución dio **mejor** resultado que
> la de más. La resolución no es lo que limita: importa más que esté bien
> calibrada y bien puesta.

---

## 7. Si algo sale mal

| Síntoma | Causa más probable | Qué hacer |
|---|---|---|
| El paso 0 da error | El sistema no está bien instalado | Pedí ayuda; no es tu cámara |
| Se abre la cámara equivocada | El número de índice | Probá `--indice 1`, `--indice 2`… mirando la imagen |
| `PATRON: no se ve` | Poca luz, reflejo, o el patrón muy lejos | Más luz difusa, sin brillo directo; acercalo |
| Nunca dice `quieto: si` | Te tiembla el pulso | Apoyá el patrón o los codos en algo |
| La calibración da **MALA** | El patrón no está plano | Repegalo entero sobre cartón rígido |
| La calibración da **MALA** y el patrón está plano | Poca variedad de vistas | Repetí cubriendo las nueve zonas y las cuatro inclinaciones |
| A la derecha se ve **peor** que a la izquierda | Cargaste el perfil de otra cámara | Poné tu nombre exacto en `--camara` |
| `faltan marcadores de esquina` | Uno tapado, cortado o mal iluminado | Ver [`MONTAJE.md`](MONTAJE.md), sección 2 |

**Regla general:** si un paso no da lo que este manual dice que tiene que dar,
**no sigas al siguiente**. Cada paso se apoya en el anterior, y un error
arrastrado es mucho más difícil de encontrar después.

---

## Para entender más

Nada de esto hace falta para completar la puesta a punto. Está por si te da
curiosidad o si algo no salió como esperabas.

| Si querés saber… | Leé |
|---|---|
| Dónde va cada marcador y por qué el orden importa | [`MONTAJE.md`](MONTAJE.md) |
| Todas las opciones de cada herramienta, y el porqué de cada decisión | [`vision/tools/README.md`](vision/tools/README.md) |
| Cómo funciona por dentro el sistema de perfiles y la corrección del lente | [`vision/geometry/README.md`](vision/geometry/README.md) |
| Cómo elige el sistema qué cámara abrir | [`vision/sources/README.md`](vision/sources/README.md) |
| Cómo está armado el sistema completo | [`README.md`](README.md) |
| El formato de datos que consume tu rover | [`contrato/CONTRATO.md`](contrato/CONTRATO.md) |
