# robot_state.py
#
# Mantiene el estado operativo del CenfoBot.
#
# Estados principales:
#
# IDLE      -> esperando instrucciones
# MOVING    -> avanzando o retrocediendo
# TURNING   -> realizando un giro
# STOPPED   -> detenido por una orden
# ERROR     -> ocurrió un problema
# OFFLINE   -> perdió comunicación
#
# Este módulo NO controla motores.
# Solamente mantiene información sobre el estado del rover.

import time


# --------------------------------------------------
# ESTADOS
# --------------------------------------------------

IDLE = "IDLE"
MOVING = "MOVING"
TURNING = "TURNING"
STOPPED = "STOPPED"
ERROR = "ERROR"
OFFLINE = "OFFLINE"


# --------------------------------------------------
# CLASE ROBOT STATE
# --------------------------------------------------

class RobotState:

    def __init__(self, robot_id):

        self.robot_id = robot_id

        self.state = IDLE

        self.previous_state = None

        self.message = ""

        self.last_change = time.monotonic()

        self.error_code = None


    # --------------------------------------------------
    # CAMBIAR ESTADO
    # --------------------------------------------------

    def set_state(self, new_state, message=""):

        if new_state == self.state:
            return

        self.previous_state = self.state

        self.state = new_state

        self.message = message

        self.last_change = time.monotonic()

        print(
            "Estado:",
            self.previous_state,
            "->",
            self.state
        )


    # --------------------------------------------------
    # ESTADOS ESPECIFICOS
    # --------------------------------------------------

    def idle(self):

        self.error_code = None

        self.set_state(
            IDLE,
            "Esperando instrucciones"
        )


    def moving(self, message="Movimiento"):

        self.set_state(
            MOVING,
            message
        )


    def turning(self, message="Girando"):

        self.set_state(
            TURNING,
            message
        )


    def stopped(self, message="Detenido"):

        self.set_state(
            STOPPED,
            message
        )


    def offline(self, message="Sin comunicacion"):

        self.set_state(
            OFFLINE,
            message
        )


    def error(self, code=None, message="Error"):

        self.error_code = code

        self.set_state(
            ERROR,
            message
        )


    # --------------------------------------------------
    # INFORMACION
    # --------------------------------------------------

    def time_in_state(self):

        return (
            time.monotonic()
            - self.last_change
        )


    def is_moving(self):

        return (
            self.state == MOVING
            or self.state == TURNING
        )


    def has_error(self):

        return self.state == ERROR


    # --------------------------------------------------
    # REPRESENTACION
    # --------------------------------------------------

    def to_dict(self):

        return {
            "robot_id": self.robot_id,
            "state": self.state,
            "previous_state": self.previous_state,
            "message": self.message,
            "error_code": self.error_code,
            "time_in_state": round(
                self.time_in_state(),
                2
            )
        }


    def __str__(self):

        return (
            "Robot "
            + str(self.robot_id)
            + " | "
            + self.state
            + " | "
            + self.message
        )


# --------------------------------------------------
# EJEMPLO
# --------------------------------------------------

if __name__ == "__main__":

    robot = RobotState(
        robot_id=10
    )

    print(robot)

    time.sleep(1)

    robot.moving(
        "Avanzando hacia cubo rojo"
    )

    print(robot)

    time.sleep(2)

    robot.turning(
        "Girando 90 grados"
    )

    print(robot)

    time.sleep(1)

    robot.stopped()

    print(robot)

    print(robot.to_dict())
