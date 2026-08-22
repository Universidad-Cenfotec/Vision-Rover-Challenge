# Comunicación ESP-NOW entre dos IdeaBoards

Este ejemplo muestra cómo establecer una comunicación simple mediante **ESP-NOW** entre dos IdeaBoards con ESP32.

ESP-NOW permite que dos dispositivos ESP32 se comuniquen directamente, **sin necesidad de un router Wi-Fi ni conexión a Internet**.

En este ejemplo:

- **IdeaBoard 1** funciona como **emisor**.
- **IdeaBoard 2** funciona como **receptor**.
- El emisor envía el mensaje `"Hola"` cada segundo.

---

## 1. Obtener la dirección MAC del receptor

Primero carga y ejecuta el siguiente código en la **IdeaBoard 2**, que funcionará como receptor.

```python
import network
import espnow

# Activar Wi-Fi
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

# Mostrar la dirección MAC
print("MAC:", wlan.config("mac"))

# Iniciar ESP-NOW
e = espnow.ESPNow()
e.active(True)

while True:
    host, mensaje = e.recv()

    if mensaje:
        print("Recibido:", mensaje.decode())
```

Al ejecutar el programa aparecerá en la consola una dirección similar a esta:

```text
MAC: b'\x24\x6f\x28\x12\x34\x56'
```

Esta dirección identifica a la IdeaBoard receptora.

---

## 2. Configurar la IdeaBoard emisora

Copia la dirección MAC obtenida anteriormente y colócala en la variable `receptor`.

```python
import network
import espnow
from time import sleep

# Activar Wi-Fi
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

# Iniciar ESP-NOW
e = espnow.ESPNow()
e.active(True)

# MAC de la IdeaBoard receptora
receptor = b'\x24\x6f\x28\x12\x34\x56'

# Registrar el receptor
e.add_peer(receptor)

while True:
    e.send(receptor, "Hola")
    print("Mensaje enviado")
    sleep(1)
```

> **Importante:** reemplaza `b'\x24\x6f\x28\x12\x34\x56'` por la dirección MAC de tu IdeaBoard receptora.

---

## 3. Ejecutar los programas

1. Ejecuta primero el programa de la **IdeaBoard receptora**.
2. Verifica y copia su dirección MAC.
3. Coloca esa dirección MAC en el programa de la **IdeaBoard emisora**.
4. Ejecuta el programa del emisor.
5. Observa la consola de ambas IdeaBoards.

En el emisor aparecerá:

```text
Mensaje enviado
Mensaje enviado
Mensaje enviado
```

En el receptor aparecerá:

```text
Recibido: Hola
Recibido: Hola
Recibido: Hola
```

---

## Esquema de comunicación

```text
┌─────────────┐       ESP-NOW        ┌─────────────┐
│ IdeaBoard 1 │ ───────────────────► │ IdeaBoard 2 │
│   Emisor    │       "Hola"         │  Receptor   │
└─────────────┘                       └─────────────┘
```

## ¿Qué está ocurriendo?

ESP-NOW utiliza el hardware Wi-Fi del ESP32, pero **no requiere conectarse a una red Wi-Fi**.

La IdeaBoard emisora utiliza la dirección MAC de la IdeaBoard receptora para enviarle directamente los datos.

Esto permite crear comunicaciones rápidas entre IdeaBoards para proyectos como:

- Robots que intercambian información.
- Control remoto de robots.
- Redes de sensores.
- Comunicación entre varios CenfoBots.
- Coordinación entre robots.
