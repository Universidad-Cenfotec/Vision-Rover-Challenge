# detectors/

**Productor.** Encuentra qué hay en la cancha y dónde. **Solo detecta; no
decide**: informa lo que ve, sin interpretar ni corregir.

## Estado: vacío

**Todavía no hay código acá.** El sistema de coordenadas de
[`../geometry/`](../geometry/README.md) ya está listo, que es el requisito
previo: sin saber convertir píxeles a celdas, detectar algo no serviría de mucho.

## Lo que va a existir

### Detección de rovers

Los dos robots son **negros e idénticos**: lo único que los distingue es el
**marcador ArUco** pegado encima. Ese ID es su identidad, y no se infiere nunca
de la posición ni del orden en una lista.

Además de dónde está, hay que deducir **hacia dónde apunta**, que sale de la
orientación del marcador.

### Detección de cubos y obstáculos por color

- **Cubos:** 6 cm, identidad por **color** (`green`, `blue`, `red`). No hay dos
  del mismo color, así que el color alcanza para identificarlos.
- **Obstáculos:** bloques **amarillos** de 10 cm. El **amarillo está reservado**:
  un objeto amarillo nunca es un cubo.

El método decidido: **segmentar por saturación** y clasificar en espacio **Lab**,
no HSV.

**Por qué saturación:** el tablero es acromático —grises, blancos, negros—, así
que cualquier cosa con color saturado es, por definición, un objeto de interés.
Es un filtro que separa el fondo del contenido casi gratis.

**Por qué Lab y no HSV:** el matiz de HSV se vuelve inestable justo donde más
importa —con poca saturación o poca luz— y da saltos entre valores extremos. Lab
separa la luminosidad del color de forma más pareja, así que un cubo rojo a la
sombra se sigue pareciendo a un cubo rojo.
