# publish/

**Consumidor.** Publica el estado del mundo por TCP/NDJSON (un JSON por línea)
según el contrato. Buffer de un mensaje por cliente: el último valor gana y nunca
se encola telemetría vieja. Corre por temporizador, desacoplado del procesamiento.
