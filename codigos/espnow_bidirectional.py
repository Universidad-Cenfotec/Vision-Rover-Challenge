# espnow_bidirectional.py
#
# Comunicación ESP-NOW bidireccional entre dos CenfoBots.
#
# Ambos robots pueden:
#
# - enviar mensajes
# - recibir mensajes
# - responder PING/PONG
# - compartir estado
#
# CircuitPython + IdeaBoard
#
# IMPORTANTE:
# Cambiar ROBOT_ID y PEER_MAC en cada rover.


import time
import wifi
import espnow


# --------------------------------------------------
# CONFIGURACION
# --------------------------------------------------

ROBOT_ID = 10

# MAC del OTRO rover.
#
# Ejemplo:
# "24:6F:28:12:34:56"
#
PEER_MAC = "AA:BB:CC:DD:EE:FF"

# Canal ESP-NOW.
#
# Los dos rovers deben utilizar el mismo canal.
CHANNEL = 6

# Cada cuánto enviar heartbeat
HEARTBEAT_SECONDS = 2.0


# --------------------------------------------------
# FUNCIONES AUXILIARES
# --------------------------------------------------

def mac_from_string(mac_string):
    """
    Convierte:
        "AA:BB:CC:DD:EE:FF"

    en:
        b'\\xaa\\xbb\\xcc\\xdd\\xee\\xff'
    """

    return bytes(
        int(part, 16)
        for part in mac_string.split(":")
    )


def mac_to_string(mac):
    """
    Convierte una MAC en bytes a texto legible.
    """

    return ":".join(
        "{:02X}".format(byte)
        for byte in mac
    )


# --------------------------------------------------
# CONFIGURAR RADIO
# --------------------------------------------------

# Se utiliza temporalmente un Access Point
# para colocar la radio en el canal deseado.
#
# No se utiliza realmente como red Wi-Fi.

wifi.radio.start_ap(
    " ",
    "",
    channel=CHANNEL,
    max_connections=0
)

wifi.radio.stop_ap()


# --------------------------------------------------
# MOSTRAR MAC DEL ROVER
# --------------------------------------------------

MY_MAC = wifi.radio.mac_address

print()
print("================================")
print("ESP-NOW CenfoBot")
print("================================")

print("Robot ID:", ROBOT_ID)

print(
    "Mi MAC:",
    mac_to_string(MY_MAC)
)

print("Canal:", CHANNEL)


# --------------------------------------------------
# CREAR ESP-NOW
# --------------------------------------------------

esp = espnow.ESPNow()


# --------------------------------------------------
# REGISTRAR EL OTRO ROVER
# --------------------------------------------------

peer_mac_bytes = mac_from_string(
    PEER_MAC
)

peer = espnow.Peer(
    mac=peer_mac_bytes,
    channel=CHANNEL
)

esp.peers.append(peer)

print(
    "Peer:",
    PEER_MAC
)


# --------------------------------------------------
# ENVIAR MENSAJE
# --------------------------------------------------

def send(message):
    """
    Envía un mensaje al otro rover.
    """

    # Añadir ID del robot emisor
    packet = (
        str(ROBOT_ID)
        + "|"
        + message
    )

    try:

        esp.send(
            packet.encode("utf-8"),
            peer
        )

        print(
            "TX:",
            packet
        )

        return True

    except Exception as error:

        print(
            "Error enviando:",
            error
        )

        return False


# --------------------------------------------------
# PROCESAR MENSAJE
# --------------------------------------------------

def process_message(message):
    """
    Procesa un mensaje recibido.

    Formato:

        ROBOT_ID|COMANDO|DATOS

    Ejemplos:

        10|PING
        10|STATE|MOVING
        11|TASK|RED
    """

    parts = message.split("|")

    if len(parts) < 2:
        return

    sender_id = parts[0]
    command = parts[1]

    # ----------------------------------------------
    # PING
    # ----------------------------------------------

    if command == "PING":

        print(
            "PING recibido de robot",
            sender_id
        )

        send("PONG")

        return


    # ----------------------------------------------
    # PONG
    # ----------------------------------------------

    if command == "PONG":

        print(
            "PONG recibido de robot",
            sender_id
        )

        return


    # ----------------------------------------------
    # STATE
    # ----------------------------------------------

    if command == "STATE":

        if len(parts) >= 3:

            state = parts[2]

            print(
                "Robot",
                sender_id,
                "estado:",
                state
            )

        return


    # ----------------------------------------------
    # TASK
    # ----------------------------------------------

    if command == "TASK":

        if len(parts) >= 3:

            task = parts[2]

            print(
                "Robot",
                sender_id,
                "tarea:",
                task
            )

        return


    # ----------------------------------------------
    # MENSAJE DESCONOCIDO
    # ----------------------------------------------

    print(
        "Mensaje no reconocido:",
        message
    )


# --------------------------------------------------
# RECIBIR
# --------------------------------------------------

def receive():
    """
    Revisa si llegó un mensaje.

    No bloquea el programa.

    Retorna el mensaje si existe,
    o None si no hay ninguno.
    """

    packet = esp.read()

    if packet is None:
        return None

    try:

        message = packet.msg.decode(
            "utf-8"
        )

    except Exception:

        print(
            "Mensaje no valido"
        )

        return None


    print()
    print(
        "RX desde:",
        mac_to_string(packet.mac)
    )

    print(
        "RSSI:",
        packet.rssi,
        "dBm"
    )

    print(
        "Mensaje:",
        message
    )

    process_message(message)

    return message


# --------------------------------------------------
# FUNCIONES DE ALTO NIVEL
# --------------------------------------------------

def send_state(state):
    """
    Comparte el estado del rover.

    Ejemplo:
        send_state("MOVING")
    """

    send(
        "STATE|" + state
    )


def send_task(task):
    """
    Comparte una tarea.

    Ejemplo:
        send_task("RED")
    """

    send(
        "TASK|" + task
    )


def ping():
    """
    Comprueba si el otro rover responde.
    """

    send("PING")


# --------------------------------------------------
# LOOP PRINCIPAL
# --------------------------------------------------

print()
print("ESP-NOW listo")
print()


last_heartbeat = time.monotonic()


while True:

    # ----------------------------------------------
    # RECIBIR
    # ----------------------------------------------

    receive()


    # ----------------------------------------------
    # HEARTBEAT
    # ----------------------------------------------

    if (
        time.monotonic()
        - last_heartbeat
        >= HEARTBEAT_SECONDS
    ):

        ping()

        last_heartbeat = time.monotonic()


    time.sleep(0.01)
