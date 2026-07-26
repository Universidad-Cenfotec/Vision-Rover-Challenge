# record/

**Consumidor.** Guarda a disco lo que el sistema vio, para poder revisarlo
después. **Solo lee** el estado del mundo; nunca lo modifica.

## Estado: vacío

**Todavía no hay código acá.**

## Lo que va a existir

### Grabación del estado del mundo

Guardar la secuencia de estados de una sesión para poder **repetirla** más tarde,
sin cámara y sin cancha.

Sirve para dos cosas concretas:

- **Depurar sin montar todo.** Si algo falló en una ronda, se vuelve a correr esa
  grabación tantas veces como haga falta, con el mismo resultado cada vez.
- **Probar cambios contra datos reales.** Un ajuste en la detección se puede
  medir contra una sesión grabada, en vez de contra una corrida nueva que nunca
  es igual a la anterior.

Es un consumidor independiente de `publish/`: que la grabación falle o se apague
no debe afectar en nada a la telemetría que reciben los equipos.
