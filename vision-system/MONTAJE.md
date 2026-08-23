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

**Cuánto margen:** la regla es **un 20 % del lado del marcador** por cada
costado. Las medidas concretas de esta cancha:

| Marcador | Lado (negro) | Blanco por costado | Total impreso |
|---|---|---|---|
| **De esquina** (los cuatro) | **100 mm** | **20 mm** | 140 × 140 mm |
| **Del rover** | 40 mm | 5 mm | 50 × 50 mm |

Esto aplica a **todos** los marcadores: los cuatro de esquina y los de los
rovers.

> **El marcador del rover todavía es provisional.** Los 40 mm salen del espacio
> disponible en el robot (50 × 70 mm) y **falta comprobar** que se detecte de
> forma estable desde la cámara montada a 2,1 m. Si no alcanza, hay lugar para
> 60 mm usando el lado largo. Las dos medidas viven en
> [`vision/config_vision.json`](vision/config_vision.json), cada una con su
> estado; ahí manda la configuración y no este documento.

### Al pegar, verificar que cada marcador:

- [ ] Queda **plano** contra la superficie, sin arrugas ni burbujas
- [ ] Está **completo**, sin ninguna esquina cortada o tapada
- [ ] Conserva su **margen blanco** libre en los cuatro lados
- [ ] **No queda pisado** por cinta, cables ni el borde del tablero
- [ ] Está **bien iluminado**, sin un reflejo fuerte encima

---

## 3. Dos números distintos: el tablero y la cancha

> ### ⚠️ Si medís el tablero y contás 50, y en la configuración ves 43, **la configuración NO está mal**
>
> Son dos cosas distintas y hay que tenerlas separadas en la cabeza.

**El tablero físico mide 50 × 50 cuadros. La cancha efectiva del sistema es de
43 × 43 celdas.**

Los marcadores no van en el borde exacto del tablero, sino **hacia adentro**, y
la cancha del sistema es el área **entre sus centros**. En esta cancha eso da
43 × 43 cuadros = **860 × 860 mm**. Los 7 cuadros restantes —3,5 por lado— son
el margen donde están pegados los marcadores.

**Ese margen es borde muerto: no se usa para nada.** Las zonas de acopio, la
salida, los cubos y los robots viven todos dentro del área de 43 × 43.

```
   ┌───────────────────────────────────────────────┐ ← tablero físico: 50 × 50 cuadros
   │        margen muerto: 3,5 cuadros por lado    │
   │    ▣ ─────────────────────────────────── ▣    │ ← marcadores ID 0 y ID 1
   │    │                                     │    │
   │    │      CANCHA EFECTIVA: 43 × 43       │    │ ← 860 × 860 mm entre centros
   │    │      todo el juego vive acá         │    │
   │    │                                     │    │
   │    ▣ ─────────────────────────────────── ▣    │ ← marcadores ID 3 e ID 2
   │                                               │
   └───────────────────────────────────────────────┘
```

| Número | Qué es | Se usa para |
|---|---|---|
| **50 × 50 cuadros** | el tablero físico impreso | nada del sistema |
| **43 × 43 celdas** | entre centros de marcadores | **todo**: coordenadas, zonas, cubos, robots |
| 7 cuadros | margen donde van pegados los marcadores | borde muerto |

**Medido y verificado** el 4 de agosto de 2026, contando cuadros entre centros
en las dos dimensiones. Antes la configuración decía 50 —un valor nominal sin
confirmar— y eso hacía que **todas las coordenadas publicadas salieran un 16,5 %
estiradas**, sin ningún error que lo delatara. Lo detectó
`vision/tools/precision_ubicacion.py`, que reportaba 233 mm sobre
desplazamientos reales de 200 mm.

## 3b. Si montás OTRA cancha: cómo medirla

El número 43 vale para **esta** cancha. Con otro tablero o los marcadores
pegados en otro lado, va a ser otro, y hay que medirlo igual:

### Después del montaje:

1. Contar los **cuadros de la cuadrícula entre los centros** de los marcadores,
   en los dos ejes. Contar es exacto y no necesita regla: cada cuadro son 20 mm.
2. Verificarlo con cinta métrica: cuadros × 20 mm tiene que dar esa distancia.
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
  reancla solo a los marcadores en el cuadro siguiente.

> ### Si se pierde un marcador durante la ronda
>
> **Con tres, el sistema sigue funcionando con la misma precisión.** Conserva la
> geometría del último cuadro bueno —la cámara está atornillada, así que sigue
> siendo válida— y usa los tres visibles para comprobar en cada cuadro que la
> cámara no se movió. Si se despega un marcador a mitad de ronda, no se pierde
> la ronda.
>
> **Con dos o menos, se queda sin coordenadas.** No hay con qué comprobar nada,
> así que conserva el último estado bueno y le hace crecer la edad hasta que
> vuelva a ver tres.
>
> Igual, **montar los cuatro bien sigue siendo el trabajo**: con tres el sistema
> aguanta, no funciona mejor. Y si alguien mueve la cámara mientras falta uno, se
> detiene y avisa, porque ahí sí las coordenadas dejarían de valer.

---

## 6. Comprobación antes de la primera ronda

Cuando la cancha esté montada y la cámara puesta:

1. **Los cuatro marcadores se detectan.** El sistema tiene que encontrar los IDs
   0, 1, 2 y 3. Si falta alguno, avisa con un mensaje que dice cuáles vio.
   Arrancar con tres **no alcanza**: para conservar la geometría hace falta
   haberla establecido antes con los cuatro.
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

- **Con la cancha ya montada, el paso siguiente es dejar la cámara lista:**
  [`PUESTA_A_PUNTO.md`](PUESTA_A_PUNTO.md). Ahí está el procedimiento completo
  —imprimir el patrón, calibrar la distorsión y medir la precisión—, incluida
  la comprobación con cinta del paso 4 de acá arriba, que la herramienta de
  precisión hace sola y con más cuidado.
- Las reglas completas del proyecto: [`CLAUDE.md`](CLAUDE.md), sección 5.
- Cómo el sistema usa los marcadores:
  [`vision/geometry/README.md`](vision/geometry/README.md).
- El formato que reciben los equipos:
  [`contrato/CONTRATO.md`](contrato/CONTRATO.md).
