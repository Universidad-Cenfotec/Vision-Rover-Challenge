# motor_calibration.py
#
# Calcula una compensación entre los dos motores del CenfoBot.
#
# El robot intenta avanzar recto mientras la IMU mide
# cuánto cambia su orientación.
#
# Como el CenfoBot no tiene encoders, esta calibración
# mide el efecto final de las diferencias entre:
#
# - motores
# - reductores
# - ruedas
# - fricción
#
# El resultado es un factor RIGHT_GAIN que puede utilizarse
# posteriormente en drive.py, move_heading.py, etc.
#
# IMPORTANTE:
# Ejecutar sobre una superficie plana y con espacio suficiente.


import board
import time
import math

from ideaboard import IdeaBoard
from adafruit_lsm6ds.lsm6ds3trc import LSM6DS3TRC


# --------------------------------------------------
# CONFIGURACION
# --------------------------------------------------

TEST_SPEED = 0.35
TEST_DURATION = 1.0

# Cambio intencional que utilizamos para descubrir
# cómo responde el robot al modificar motor_2.
PROBE_GAIN = 0.10

MIN_GAIN = 0.70
MAX_GAIN = 1.30

RAD_TO_DEG = 180 / math.pi


# --------------------------------------------------
# HARDWARE
# --------------------------------------------------

ib = IdeaBoard()

i2c = board.I2C()
sensor = LSM6DS3TRC(i2c, 0x6B)


# --------------------------------------------------
# FUNCIONES AUXILIARES
# --------------------------------------------------

def limit(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def stop():

    ib.motor_1.throttle = 0
    ib.motor_2.throttle = 0


# --------------------------------------------------
# CALIBRACION DEL GIROSCOPIO
# --------------------------------------------------

def calibrate_gyro_drift(sensor, seconds=3):

    print("Calibrando giroscopio...")
    print("No mover el robot.")

    total = 0
    samples = 0

    start = time.monotonic()

    while time.monotonic() - start < seconds:

        gyro_z = sensor.gyro[2]

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
# PRUEBA DE MOVIMIENTO
# --------------------------------------------------

def straight_test(
    speed,
    duration,
    drift,
    right_gain=1.0
):

    """
    Hace avanzar el robot durante un tiempo determinado
    y devuelve cuánto cambió su orientación.

    motor_1 se utiliza como referencia.

    motor_2 se multiplica por right_gain.
    """

    heading_change = 0.0

    left_speed = speed
    right_speed = speed * right_gain

    left_speed = limit(left_speed, -1, 1)
    right_speed = limit(right_speed, -1, 1)

    print()
    print("Prueba")
    print("Motor 1:", round(left_speed, 3))
    print("Motor 2:", round(right_speed, 3))

    previous_time = time.monotonic()
    start_time = previous_time

    try:

        ib.motor_1.throttle = left_speed
        ib.motor_2.throttle = right_speed

        while time.monotonic() - start_time < duration:

            current_time = time.monotonic()

            dt = current_time - previous_time
            previous_time = current_time

            gyro_z = sensor.gyro[2] - drift

            angular_velocity = (
                gyro_z * RAD_TO_DEG
            )

            heading_change += (
                angular_velocity * dt
            )

            time.sleep(0.005)

    finally:

        stop()

    print(
        "Desviacion:",
        round(heading_change, 2),
        "grados"
    )

    return heading_change


# --------------------------------------------------
# CALIBRACION DE MOTORES
# --------------------------------------------------

def calibrate_motors(
    sensor,
    drift,
    speed=TEST_SPEED,
    duration=TEST_DURATION
):

    print()
    print("============================")
    print("CALIBRACION DE MOTORES")
    print("============================")

    # --------------------------------------------------
    # PRUEBA 1
    #
    # Ambos motores reciben exactamente
    # la misma potencia.
    # --------------------------------------------------

    print()
    print("PRUEBA 1 - Sin compensacion")

    error_1 = straight_test(
        speed,
        duration,
        drift,
        right_gain=1.0
    )

    time.sleep(1)


    # --------------------------------------------------
    # PRUEBA 2
    #
    # Incrementamos ligeramente motor_2.
    #
    # Esto permite medir cuánto cambia la trayectoria
    # cuando modificamos ese motor.
    # --------------------------------------------------

    probe_gain = 1.0 + PROBE_GAIN

    print()
    print("PRUEBA 2 - Midiendo respuesta")

    error_2 = straight_test(
        speed,
        duration,
        drift,
        right_gain=probe_gain
    )

    time.sleep(1)


    # --------------------------------------------------
    # CALCULAR RESPUESTA DEL ROBOT
    # --------------------------------------------------

    change = error_2 - error_1

    if abs(change) < 0.5:

        print()
        print("No se pudo calcular una compensacion confiable.")
        print("La diferencia entre las pruebas fue muy pequena.")

        return 1.0


    # Cuántos grados cambia la desviación
    # por unidad de gain.

    slope = change / PROBE_GAIN


    # Queremos encontrar el gain que produzca:
    #
    # error = 0
    #
    # aproximando localmente:
    #
    # error(gain) =
    # error_1 + slope * (gain - 1)
    #
    # resolvemos para error = 0

    right_gain = (
        1.0 - error_1 / slope
    )

    right_gain = limit(
        right_gain,
        MIN_GAIN,
        MAX_GAIN
    )


    print()
    print("============================")
    print("COMPENSACION CALCULADA")
    print("============================")

    print(
        "RIGHT_GAIN =",
        round(right_gain, 4)
    )


    # --------------------------------------------------
    # PRUEBA 3
    #
    # Verificar la compensación calculada.
    # --------------------------------------------------

    time.sleep(1)

    print()
    print("PRUEBA 3 - Verificacion")

    final_error = straight_test(
        speed,
        duration,
        drift,
        right_gain=right_gain
    )


    # --------------------------------------------------
    # RESULTADO
    # --------------------------------------------------

    print()
    print("============================")
    print("RESULTADO")
    print("============================")

    print(
        "Sin compensacion:",
        round(error_1, 2),
        "grados"
    )

    print(
        "Con compensacion:",
        round(final_error, 2),
        "grados"
    )

    print()

    print("Utilizar:")

    print(
        "LEFT_GAIN = 1.0"
    )

    print(
        "RIGHT_GAIN =",
        round(right_gain, 4)
    )

    return right_gain


# --------------------------------------------------
# PROGRAMA PRINCIPAL
# --------------------------------------------------

stop()

ib.pixel = (255, 0, 0)

drift = calibrate_gyro_drift(
    sensor,
    seconds=3
)

ib.pixel = (0, 255, 0)

right_gain = calibrate_motors(
    sensor,
    drift
)

stop()

ib.pixel = (0, 0, 255)

print()
print("Calibracion terminada.")
