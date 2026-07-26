# Montaje físico de la cancha

**Guía para quien arma la cancha el día de la competencia.**

Este documento no es sobre código: es sobre **dónde pegar cosas**. Lo que decida
acá una persona con una cinta y un rollo de cinta adhesiva determina si todas las
coordenadas que publica el sistema tienen sentido o no.

> ### ⚠️ La advertencia principal
>
> Los cuatro marcadores de esquina definen el sistema de coordenadas completo.
> **Si se pegan en el orden equivocado, TODAS las coordenadas salen rotadas o
> espejadas** —los rovers van a ir al lugar contrario— y **el sistema no se va a
> quejar**: va a publicar números perfectamente válidos y perfectamente mal.
>
> Es un error silencioso. Por eso vale la pena verificarlo dos veces antes de
> pegar, y correr la comprobación del final antes de la primera ronda.

---

## 1. Los cuatro marcadores de esquina

### Qué son

Cuatro marcadores **ArUco** del diccionario **`DICT_4X4_50`**, con los **IDs 0,
1, 2 y 3**. Van pegados **planos sobre el tablero**, uno en cada esquina.

Los IDs 0 a 3 están **reservados** para las esquinas. Los marcadores de los
rovers usan otros números (por ejemplo 10 y 11).

### Dónde va cada uno

**El ID 0 va en la esquina de salida de los robots.** Esa esquina es el origen
de todo: la coordenada (0, 0).

Parado mirando la cancha desde arriba, **con el marcador 0 arriba a la
izquierda**, los otros tres van **en sentido horario**:

```
              col ────────────────────────────►
                                                    
   ID 0  ┌──────────────────────────────────┐  ID 1
   (0,0) │                                  │  (cols, 0)
     │   │                                  │
     │   │                                  │
    row  │            C A N C H A            │
     │   │                                  │
     │   │                                  │
     ▼   │                                  │
   ID 3  └──────────────────────────────────┘  ID 2
   (0, rows)                                   (cols, rows)

   ▲
   └── esquina de SALIDA DE LOS ROBOTS = origen (0,0) = marcador ID 0
```

| Marcador | Va en | Coordenada de su centro |
|---|---|---|
| **ID 0** | esquina de **salida de los robots** | `(0, 0)` — el origen |
| **ID 1** | siguiente en sentido horario | `(cols, 0)` |
| **ID 2** | diagonal opuesta al origen | `(cols, rows)` |
| **ID 3** | última en sentido horario | `(0, rows)` |

### El origen es el CENTRO del marcador, no su esquina

La coordenada (0, 0) es el **centro** del marcador ID 0.

Se eligió el centro porque es lo único que se puede medir **sin ambigüedad**,
tanto en una imagen como con una cinta métrica sobre la cancha. "El centro del
marcador" no admite discusión; "su esquina superior izquierda" sí, y con la
cámara mirando de costado, menos todavía.

**Consecuencia práctica:** la cancha útil es el área **entre los centros** de los
cuatro marcadores, no el tablero físico completo. Ver la sección 3.

---

## 2. El margen blanco alrededor de cada marcador

> ### ⚠️ Sin margen blanco, el marcador es invisible
>
> No importa lo bien impreso o lo bien pegado que esté.

Cada marcador impreso tiene que llevar una **zona blanca alrededor de todo su
contorno**, sin nada encima.

**Por qué:** el detector de ArUco encuentra los marcadores buscando el contraste
entre el borde negro del marcador y lo que hay alrededor. Si el marcador queda
al ras del borde del tablero, tapado por una cinta, o pegado justo contra una
zona oscura, el detector no ve ese contraste y **el marcador sencillamente no
existe** para el sistema.

**Cuánto margen:** como referencia, la configuración del proyecto usa un borde
blanco de aproximadamente **un 20 % del lado del marcador** por cada costado. Un
marcador de 6 cm de lado lleva algo más de 1 cm de blanco alrededor.

Esto aplica a **todos** los marcadores: los cuatro de esquina y los de los
rovers.

### Al pegar, verificar que cada marcador:

- [ ] Queda **plano** contra la superficie, sin arrugas ni burbujas
- [ ] Está **completo**, sin ninguna esquina cortada o tapada
- [ ] Conserva su **margen blanco** libre en los cuatro lados
- [ ] **No queda pisado** por cinta, cables ni el borde del tablero
- [ ] Está **bien iluminado**, sin un reflejo fuerte encima

---

## 3. Medir la cancha después de pegar

La cancha efectiva es el área **entre los centros de los cuatro marcadores**, y
va a ser **menor** que el tablero físico: los marcadores se pegan con algo de
margen hacia adentro.

El valor nominal es **50 × 50 celdas de 20 mm** (1000 × 1000 mm), pero **es un
valor a confirmar**. Si los marcadores quedan a 3 cm de cada borde, la cancha
real pasa a ser de unas 47 × 47 celdas.

### Después del montaje:

1. Medir la distancia **entre centros de marcadores**, en milímetros, en los dos
   ejes.
2. Dividir por 20 mm para obtener el número de celdas.
3. Actualizar `cols` y `rows` en **los dos** archivos de configuración:
   - [`vision/config_vision.json`](vision/config_vision.json) → `tablero`
   - [`contrato/config_simulador.json`](contrato/config_simulador.json) → `grid`

Los dos tienen que decir lo mismo. El sistema publica ese valor en cada mensaje,
y los equipos lo leen del mensaje en vez de suponerlo, así que un cambio acá no
les rompe el código; pero si los dos archivos no coinciden, el simulador y la
cancha real se van a comportar distinto.

---

## 4. Las tres zonas de acopio

Hay **tres zonas de acopio**, una por color (**verde**, **azul**, **rojo**), en
las **tres esquinas que no son la de salida**. Cada cubo va a la zona de su
color.

**Qué color va en qué esquina es una decisión del montaje.** Lo que se decida
físicamente tiene que quedar reflejado en la configuración, en la lista `depots`
de [`contrato/config_simulador.json`](contrato/config_simulador.json).

Los equipos **no suponen** qué color va dónde: lo leen del mensaje. Pero si la
configuración no coincide con la cancha real, van a llevar los cubos al lugar
equivocado sin que nada avise.

---

## 5. La cámara

- **Cenital**, mirando la cancha desde arriba. No hace falta que esté
  perfectamente perpendicular —el sistema corrige la perspectiva—, pero sí que
  **vea los cuatro marcadores completos**.
- **Exposición, enfoque y balance de blancos FIJOS.** Nunca en automático: un
  ajuste que se mueve solo cambia los colores a mitad de ronda y rompe la
  detección de los cubos.
- **Enfoque manual**, ajustado y luego dejado quieto.
- Si se mueve la cámara después de calibrar, no pasa nada grave: el sistema se
  reancla solo a los marcadores en el cuadro siguiente. Lo que **no** puede pasar
  es que deje de ver alguno de los cuatro.

---

## 6. Comprobación antes de la primera ronda

Cuando la cancha esté montada y la cámara puesta:

1. **Los cuatro marcadores se detectan.** El sistema tiene que encontrar los IDs
   0, 1, 2 y 3. Si falta alguno, avisa con un mensaje que dice cuáles vio.
2. **El origen está donde debe.** Poner algo en la esquina de salida y confirmar
   que el sistema lo reporta cerca de `col ≈ 0, row ≈ 0`.
3. **La orientación no está espejada.** Mover un objeto **hacia la derecha** y
   confirmar que `col` **aumenta**. Después moverlo **hacia abajo** y confirmar
   que `row` **aumenta**.
4. **Las medidas coinciden.** Medir una distancia conocida con la cinta y
   comparar contra lo que reporta el sistema. Una celda son 20 mm.

> El paso 3 es el que atrapa el error de montaje más probable: marcadores
> pegados en orden antihorario en vez de horario. Con los cuatro detectados y
> las coordenadas espejadas, todo *parece* funcionar hasta que un rover sale
> para el lado contrario.

---

## Referencias

- Las reglas completas del proyecto: [`CLAUDE.md`](CLAUDE.md), sección 5.
- Cómo el sistema usa los marcadores:
  [`vision/geometry/README.md`](vision/geometry/README.md).
- El formato que reciben los equipos:
  [`contrato/CONTRATO.md`](contrato/CONTRATO.md).
