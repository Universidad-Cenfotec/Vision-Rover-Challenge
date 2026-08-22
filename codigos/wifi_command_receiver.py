# wifi_command_receiver.py
#
# Recibe comandos desde una computadora mediante Wi-Fi/TCP
# y controla los motores del CenfoBot.
#
# CircuitPython + IdeaBoard
#
# Comandos:
#
# MOTOR <izquierdo> <derecho>
# STOP
# PING
#
# Ejemplos:
#
# MOTOR 0.5 0.5
# MOTOR 0.4 -0.4
# STOP
# PING

import wifi
import socketpool
import time

from ideaboard import IdeaBoard


# --------------------------------------------------
# CONFIGURACION
# --------------------------------------------------

WIFI_SSID = "TU_RED_WIFI"
WIFI_PASSWORD = "TU_PASSWORD"

PORT = 5000

# Si durante este tiempo no se recibe un comando
# de movimiento, el robot se detiene.
WATCHDOG_SECONDS = 0.5


# --------------------------------------------------
# ROBOT
# --------------------------------------------------

ib = IdeaBoard()


def stop():
    """Detiene inmediatamente ambos motores."""
    ib.motor_1.throttle = 0
    ib.motor_2.throttle = 0
    ib.pixel = (255, 0, 0)


def motor(left, right):
    """
    Controla directamente ambos motores.

    left  : -1.0 a 1.0
    right : -1.0 a 1.0
    """

    # Limitar los valores al rango permitido
    left = max(-1.0, min(1.0, left))
    right = max(-1.0, min(1.0, right))

    ib.motor_1.throttle = left
    ib.motor_2.throttle = right

    ib.pixel = (0, 255, 0)


# --------------------------------------------------
# COMANDOS
# --------------------------------------------------

def process_command(command):
    """
    Procesa un comando recibido.

    Retorna True si el comando es válido.
    """

    command = command.strip()

    if not command:
        return False

    print("Comando:", command)

    parts = command.split()

    # ------------------------------
    # STOP
    # ------------------------------

    if parts[0] == "STOP":
        stop()
        return True

    # ------------------------------
    # PING
    # ------------------------------

    if parts[0] == "PING":
        return True

    # ------------------------------
    # MOTOR left right
    # ------------------------------

    if parts[0] == "MOTOR":

        if len(parts) != 3:
            print("Error: MOTOR necesita dos valores")
            return False

        try:
            left = float(parts[1])
            right = float(parts[2])

        except ValueError:
            print("Error: valores de motor invalidos")
            return False

        motor(left, right)

        return True

    print("Comando desconocido")

    return False


# --------------------------------------------------
# WIFI
# --------------------------------------------------

print("Conectando a Wi-Fi...")

wifi.radio.connect(
    WIFI_SSID,
    WIFI_PASSWORD
)

ip = str(wifi.radio.ipv4_address)

print("Wi-Fi conectado")
print("IP:", ip)


# --------------------------------------------------
# SERVIDOR TCP
# --------------------------------------------------

pool = socketpool.SocketPool(wifi.radio)

server = pool.socket(
    pool.AF_INET,
    pool.SOCK_STREAM
)

server.setsockopt(
    pool.SOL_SOCKET,
    pool.SO_REUSEADDR,
    1
)

server.bind(("0.0.0.0", PORT))

server.listen(1)

print("Servidor listo")
print("Esperando comandos en:")
print(ip, ":", PORT)


# --------------------------------------------------
# LOOP PRINCIPAL
# --------------------------------------------------

stop()

while True:

    print("Esperando computadora...")

    client, address = server.accept()

    print("Conexion desde:", address)

    # El socket no debe bloquear el control del robot
    client.setblocking(False)

    # Buffer TCP
    buffer = ""

    last_command = time.monotonic()

    stop()

    try:

        while True:

            # --------------------------------------
            # Recibir datos
            # --------------------------------------

            try:

                data = client.recv(128)

                # La computadora cerró la conexión
                if data == b"":
                    print("Conexion cerrada")
                    break

                if data:

                    buffer += data.decode("utf-8")

                    # TCP puede entregar varios comandos juntos
                    # o dividir un comando entre varios paquetes.

                    while "\n" in buffer:

                        command, buffer = buffer.split("\n", 1)

                        valid = process_command(command)

                        if valid:

                            last_command = time.monotonic()

                            try:
                                client.send(b"OK\n")
                            except OSError:
                                pass

                        else:

                            try:
                                client.send(b"ERROR\n")
                            except OSError:
                                pass

            except OSError:
                # No hay datos disponibles ahora mismo
                pass

            # --------------------------------------
            # WATCHDOG
            # --------------------------------------

            if time.monotonic() - last_command > WATCHDOG_SECONDS:

                stop()

            time.sleep(0.01)

    except Exception as error:

        print("Error:", error)

    finally:

        # Ante cualquier problema:
        # detener siempre el robot.

        stop()

        try:
            client.close()
        except:
            pass

        print("Robot detenido")
