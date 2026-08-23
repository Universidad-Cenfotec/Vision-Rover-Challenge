# move_heading.py
#
# Avanza manteniendo una orientación utilizando
# el giroscopio de la IMU y un controlador PID.
#
# El ángulo es RELATIVO a la orientación inicial:
#
#   heading = 0°  -> dirección inicial
#
# Ejemplo:
#
#   move_heading(
#       sensor,
#       drift,
#       speed=0.5,
#       duration=5,
#       heading_target=0
#   )
#
# hará avanzar el CenfoBot durante 5 segundos
# intentando mantener la dirección inicial.

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


def limit(value, minimum, maximum):
    """Limita un valor a un rango."""
    return max(minimum, min(maximum, value))


def normalize_angle(angle):
    """
    Convierte un ángulo al rango -180 a +180 grados.
    """

    while angle > 180:
        angle -= 360

    while angle < -180:
        angle += 360

    return angle


# --------------------------------------------------
# CALIBRACION DEL GIROSCOPIO
# --------------------------------------------------

def calibrate_drift(sensor, seconds=3):
    """
    Calcula el drift promedio del giroscopio.

    El robot debe permanecer completamente quieto
    durante esta calibración.
    """

    print("Calibrando giroscopio...")
    print("No mover el robot.")

    total = 0
    samples = 0

    start = time.monotonic()

    while time.monotonic() - start < seconds:

        gyro_z = sensor.gyro[2]

        # Ignorar lecturas claramente anormales
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
# MOVE HEADING
# --------------------------------------------------

def move_heading(
    sensor,
    drift,
    speed=0.5,
    duration=3,
    heading_target=0,
    Kp=0.015,
    Ki=0.0005,
    Kd=0.002,
    max_correction=0.30
):

    """
    Mueve el rover intentando mantener una orientación.

    Parámetros:

    speed
        Velocidad base de los motores.
        Rango: -1.0 a 1.0.

    duration
        Tiempo de movimiento en segundos.

    heading_target
        Orientación relativa deseada en grados.
        0 significa mantener la dirección inicial.

    Kp, Ki, Kd
        Parámetros del controlador PID.

    max_correction
        Máxima diferencia que puede introducir
        el controlador en los motores.
    """

    speed = limit(speed, -1.0, 1.0)

    # Nuestra estimación inicial del heading es 0 grados.
    heading = 0.0

    integral = 0.0
    previous_error = 0.0

    start_time = time.monotonic()
    previous_time = start_time

    print("Iniciando movimiento")
    print("Heading objetivo:", heading_target)

    try:

        while time.monotonic() - start_time < duration:

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

            # rad/s -> grados/s
            angular_velocity = gyro_z * RAD_TO_DEG

            # Integrar para estimar orientación
            heading += angular_velocity * dt

            heading = normalize_angle(heading)

            # --------------------------------------
            # ERROR ANGULAR
            # --------------------------------------

            error = normalize_angle(
                heading - heading_target
            )

            # --------------------------------------
            # PID
            # --------------------------------------

            integral += error * dt

            # Evitar integral excesiva
            integral = limit(
                integral,
                -100,
                100
            )

            derivative = (
                error - previous_error
            ) / dt

            correction = (
                Kp * error
                + Ki * integral
                + Kd * derivative
            )

            correction = limit(
                correction,
                -max_correction,
                max_correction
            )

            previous_error = error

            # --------------------------------------
            # MOTORES
            # --------------------------------------

            motor_1 = speed + correction
            motor_2 = speed - correction

            motor_1 = limit(motor_1, -1.0, 1.0)
            motor_2 = limit(motor_2, -1.0, 1.0)

            ib.motor_1.throttle = motor_1
            ib.motor_2.throttle = motor_2

            # --------------------------------------
            # DEBUG
            # --------------------------------------

            print(
                "Heading:",
                round(heading, 1),
                "Error:",
                round(error, 1),
                "Correction:",
                round(correction, 3)
            )

            time.sleep(0.01)

    finally:

        stop()

        print("Movimiento terminado")
        print("Heading final:", round(heading, 1))


# --------------------------------------------------
# PROGRAMA PRINCIPAL
# --------------------------------------------------

ib.pixel = (255, 0, 0)

drift = calibrate_drift(
    sensor,
    seconds=3
)

ib.pixel = (0, 255, 0)

# Avanzar 5 segundos intentando
# mantener exactamente la orientación inicial.

move_heading(
    sensor,
    drift,
    speed=0.5,
    duration=5,
    heading_target=0
)

ib.pixel = (0, 0, 0)
