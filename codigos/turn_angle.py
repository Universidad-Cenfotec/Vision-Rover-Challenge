# turn_angle.py
#
# Gira el CenfoBot aproximadamente un número
# determinado de grados utilizando el giroscopio.
#
# Convención:
#
#   turn_angle(90)   -> gira 90° en un sentido
#   turn_angle(-90)  -> gira 90° en el sentido contrario
#
# La precisión depende de:
# - calibración del drift
# - velocidad de giro
# - superficie
# - batería
# - inercia del robot

import board
import time
import math

from ideaboard import IdeaBoard
from adafruit_lsm6ds.lsm6ds3trc import LSM6DS3TRC


# --------------------------------------------------
# INICIALIZACION
# --------------------------------------------------

ib = IdeaBoard()

i2c = board.I2C()
sensor = LSM6DS3TRC(i2c, 0x6B)

RAD_TO_DEG = 180 / math.pi


# --------------------------------------------------
# FUNCIONES AUXILIARES
# --------------------------------------------------

def stop():
    """Detiene ambos motores."""
    ib.motor_1.throttle = 0
    ib.motor_2.throttle = 0


def calibrate_drift(sensor, seconds=3):
    """
    Calcula el drift promedio del eje Z del giroscopio.

    El robot debe permanecer completamente quieto
    durante la calibración.
    """

    print("Calibrando giroscopio...")
    print("No mover el robot.")

    total = 0
    samples = 0

    start = time.monotonic()

    while time.monotonic() - start < seconds:

        gyro_z = sensor.gyro[2]

        # Ignorar valores anormales durante calibración
        if abs(gyro_z) < 0.05:
            total += gyro_z
            samples += 1

        time.sleep(0.005)

    if samples == 0:
        return 0

    drift = total / samples

    print("Drift:", drift, "rad/s")

    return drift


# --------------------------------------------------
# TURN ANGLE
# --------------------------------------------------

def turn_angle(
    sensor,
    drift,
    degrees,
    speed=0.30,
    slow_speed=0.15,
    slow_angle=30,
    tolerance=2
):
    """
    Gira el robot aproximadamente 'degrees' grados.

    Parámetros:

    degrees
        Ángulo que se desea girar.

        Ejemplos:
            90
            -90
            180

    speed
        Velocidad normal de giro.

    slow_speed
        Velocidad utilizada cerca del objetivo.

    slow_angle
        Cuando faltan menos de estos grados,
        el robot reduce la velocidad.

    tolerance
        Margen de error permitido.
    """

    if degrees == 0:
        return

    direction = 1 if degrees > 0 else -1

    target = abs(degrees)

    accumulated_angle = 0.0

    previous_time = time.monotonic()

    print("Girando:", degrees, "grados")

    try:

        while accumulated_angle < target - tolerance:

            # --------------------------------------
            # TIEMPO
            # --------------------------------------

            current_time = time.monotonic()

            dt = current_time - previous_time
            previous_time = current_time

            if dt <= 0:
                continue

            # --------------------------------------
            # GIROSCOPIO
            # --------------------------------------

            gyro_z = sensor.gyro[2] - drift

            angular_velocity = gyro_z * RAD_TO_DEG

            delta_angle = angular_velocity * dt

            accumulated_angle += abs(delta_angle)

            # --------------------------------------
            # VELOCIDAD
            # --------------------------------------

            remaining = target - accumulated_angle

            if remaining <= slow_angle:
                current_speed = slow_speed
            else:
                current_speed = speed

            # --------------------------------------
            # MOTORES
            # --------------------------------------

            ib.motor_1.throttle = (
                current_speed * direction
            )

            ib.motor_2.throttle = (
                -current_speed * direction
            )

            # --------------------------------------
            # DEBUG
            # --------------------------------------

            print(
                "Girado:",
                round(accumulated_angle, 1),
                "Restante:",
                round(remaining, 1)
            )

            time.sleep(0.005)

    finally:

        stop()

    print(
        "Giro terminado:",
        round(accumulated_angle, 1),
        "grados"
    )


# --------------------------------------------------
# PROGRAMA PRINCIPAL
# --------------------------------------------------

ib.pixel = (255, 0, 0)

drift = calibrate_drift(
    sensor,
    seconds=3
)

ib.pixel = (0, 255, 0)

# Ejemplo:
# girar aproximadamente 90 grados.

turn_angle(
    sensor,
    drift,
    degrees=90
)

time.sleep(1)

# Girar en sentido contrario

turn_angle(
    sensor,
    drift,
    degrees=-90
)

ib.pixel = (0, 0, 0)
