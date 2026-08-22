# command_protocol.py
#
# Protocolo común de comandos para el Vision Rover Challenge.
#
# No controla motores, sensores ni comunicaciones.
# Solamente:
#
# - construye comandos
# - interpreta comandos
# - valida parámetros
#
# Formato general:
#
#   COMANDO|parametro|parametro...
#
# Ejemplos:
#
#   PING
#   STOP
#   MOTOR|0.5|0.5
#   TURN|90|0.30
#   HEADING|0|0.5|3
#
# El mismo formato puede utilizarse sobre:
#
# - TCP / Wi-Fi
# - ESP-NOW
# - puerto serial
# - archivos de prueba


# --------------------------------------------------
# COMANDOS
# --------------------------------------------------

PING = "PING"
STOP = "STOP"
MOTOR = "MOTOR"
TURN = "TURN"
HEADING = "HEADING"


# --------------------------------------------------
# FUNCIONES AUXILIARES
# --------------------------------------------------

def limit(value, minimum, maximum):
    return max(
        minimum,
        min(maximum, value)
    )


def valid_motor_speed(value):
    """
    Verifica que una velocidad esté
    entre -1.0 y 1.0.
    """

    return -1.0 <= value <= 1.0


# --------------------------------------------------
# CONSTRUIR COMANDOS
# --------------------------------------------------

def cmd_ping():
    return "PING"


def cmd_stop():
    return "STOP"


def cmd_motor(left, right):
    """
    Control directo de ambos motores.

    Ejemplo:

        MOTOR|0.5|0.5
    """

    left = limit(
        float(left),
        -1.0,
        1.0
    )

    right = limit(
        float(right),
        -1.0,
        1.0
    )

    return (
        "MOTOR|"
        + str(left)
        + "|"
        + str(right)
    )


def cmd_turn(angle, speed=0.30):
    """
    Solicita girar cierta cantidad de grados.

    Ejemplo:

        TURN|90|0.3
    """

    speed = abs(float(speed))

    speed = limit(
        speed,
        0.0,
        1.0
    )

    return (
        "TURN|"
        + str(float(angle))
        + "|"
        + str(speed)
    )


def cmd_heading(
    heading,
    speed=0.5,
    duration=1.0
):
    """
    Avanza manteniendo un heading relativo.

    Ejemplo:

        HEADING|0|0.5|3

    significa:

        mantener heading 0°
        velocidad 0.5
        durante 3 segundos
    """

    speed = limit(
        float(speed),
        -1.0,
        1.0
    )

    duration = max(
        0,
        float(duration)
    )

    return (
        "HEADING|"
        + str(float(heading))
        + "|"
        + str(speed)
        + "|"
        + str(duration)
    )


# --------------------------------------------------
# INTERPRETAR COMANDOS
# --------------------------------------------------

def parse_command(message):
    """
    Interpreta un mensaje recibido.

    Retorna un diccionario.

    Ejemplo:

        MOTOR|0.5|0.4

    retorna:

        {
            "valid": True,
            "command": "MOTOR",
            "left": 0.5,
            "right": 0.4
        }
    """

    if message is None:

        return {
            "valid": False,
            "error": "Mensaje vacio"
        }


    message = message.strip()

    if not message:

        return {
            "valid": False,
            "error": "Mensaje vacio"
        }


    parts = message.split("|")

    command = parts[0].upper()


    # --------------------------------------------------
    # PING
    # --------------------------------------------------

    if command == PING:

        if len(parts) != 1:

            return {
                "valid": False,
                "error": "PING no utiliza parametros"
            }

        return {
            "valid": True,
            "command": PING
        }


    # --------------------------------------------------
    # STOP
    # --------------------------------------------------

    if command == STOP:

        if len(parts) != 1:

            return {
                "valid": False,
                "error": "STOP no utiliza parametros"
            }

        return {
            "valid": True,
            "command": STOP
        }


    # --------------------------------------------------
    # MOTOR
    # --------------------------------------------------

    if command == MOTOR:

        if len(parts) != 3:

            return {
                "valid": False,
                "error": (
                    "MOTOR requiere: "
                    "MOTOR|left|right"
                )
            }

        try:

            left = float(parts[1])
            right = float(parts[2])

        except ValueError:

            return {
                "valid": False,
                "error": "Velocidad de motor invalida"
            }


        if not valid_motor_speed(left):

            return {
                "valid": False,
                "error": (
                    "left debe estar "
                    "entre -1.0 y 1.0"
                )
            }


        if not valid_motor_speed(right):

            return {
                "valid": False,
                "error": (
                    "right debe estar "
                    "entre -1.0 y 1.0"
                )
            }


        return {
            "valid": True,
            "command": MOTOR,
            "left": left,
            "right": right
        }


    # --------------------------------------------------
    # TURN
    # --------------------------------------------------

    if command == TURN:

        if len(parts) != 3:

            return {
                "valid": False,
                "error": (
                    "TURN requiere: "
                    "TURN|angle|speed"
                )
            }

        try:

            angle = float(parts[1])
            speed = float(parts[2])

        except ValueError:

            return {
                "valid": False,
                "error": "Parametros TURN invalidos"
            }


        if speed < 0 or speed > 1:

            return {
                "valid": False,
                "error": (
                    "speed debe estar "
                    "entre 0 y 1"
                )
            }


        return {
            "valid": True,
            "command": TURN,
            "angle": angle,
            "speed": speed
        }


    # --------------------------------------------------
    # HEADING
    # --------------------------------------------------

    if command == HEADING:

        if len(parts) != 4:

            return {
                "valid": False,
                "error": (
                    "HEADING requiere: "
                    "HEADING|heading|speed|duration"
                )
            }

        try:

            heading = float(parts[1])
            speed = float(parts[2])
            duration = float(parts[3])

        except ValueError:

            return {
                "valid": False,
                "error": "Parametros HEADING invalidos"
            }


        if not valid_motor_speed(speed):

            return {
                "valid": False,
                "error": (
                    "speed debe estar "
                    "entre -1.0 y 1.0"
                )
            }


        if duration <= 0:

            return {
                "valid": False,
                "error": (
                    "duration debe ser "
                    "mayor que 0"
                )
            }


        return {
            "valid": True,
            "command": HEADING,
            "heading": heading,
            "speed": speed,
            "duration": duration
        }


    # --------------------------------------------------
    # DESCONOCIDO
    # --------------------------------------------------

    return {
        "valid": False,
        "error": (
            "Comando desconocido: "
            + command
        )
    }


# --------------------------------------------------
# EJEMPLO
# --------------------------------------------------

if __name__ == "__main__":

    examples = [

        cmd_ping(),

        cmd_stop(),

        cmd_motor(
            0.5,
            0.5
        ),

        cmd_turn(
            90,
            0.3
        ),

        cmd_heading(
            0,
            0.5,
            3
        )
    ]


    for message in examples:

        print()
        print("Mensaje:")
        print(message)

        result = parse_command(
            message
        )

        print("Interpretado:")
        print(result)
