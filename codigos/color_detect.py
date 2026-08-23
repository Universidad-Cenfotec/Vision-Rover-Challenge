import board
import neopixel
import analogio
import keypad
from time import sleep
from ideaboard import IdeaBoard

# ==========================
# CONFIGURACIÓN
# ==========================

# Calibración del sensor
MIN_LUZ = 2819
MAX_LUZ = 62238

ib = IdeaBoard()
ib.brightness = 0.2

# NeoPixel externo (iluminador)
pixel = neopixel.NeoPixel(
    board.IO4,      # Cambiar si usas otro pin
    1,
    brightness=1,
    auto_write=True
)

# Sensor de luz
luz = analogio.AnalogIn(board.IO39)

# Botón BOOT
boton = keypad.Keys(
    (board.IO0,),
    value_when_pressed=False,
    pull=True
)

# ==========================
# FUNCIONES
# ==========================

def normalizar_lectura(valor):
    """
    Convierte una lectura del sensor
    al rango 0-255.

    2819  -> 255
    62238 -> 0
    """

    valor = max(MIN_LUZ, min(MAX_LUZ, valor))

    return int(
        (MAX_LUZ - valor) * 255 /
        (MAX_LUZ - MIN_LUZ)
    )


def medir_color(color):
    """
    Enciende el LED del color indicado
    y retorna el promedio de la lectura.
    """

    pixel[0] = color

    sleep(0.2)

    total = 0

    for _ in range(20):
        total += luz.value
        sleep(0.005)

    pixel[0] = (0, 0, 0)

    return total / 20


# ==========================
# PROGRAMA PRINCIPAL
# ==========================

print("Listo. Presione BOOT.")

while True:

    evento = boton.events.get()

    if evento and evento.released:

        # Lecturas crudas
        rojo_raw = medir_color((255, 0, 0))
        verde_raw = medir_color((0, 255, 0))
        azul_raw = medir_color((0, 0, 255))

        print(f"RAW: <{int(rojo_raw)},{int(verde_raw)},{int(azul_raw)}>")

        # Detectar el color (la menor lectura)
        if rojo_raw <= verde_raw and rojo_raw <= azul_raw:
            print("Color detectado: ROJO")
            ib.pixel = (255, 0, 0)

        elif verde_raw <= rojo_raw and verde_raw <= azul_raw:
            print("Color detectado: VERDE")
            ib.pixel = (0, 255, 0)

        else:
            print("Color detectado: AZUL")
            ib.pixel = (0, 0, 255)

        sleep(0.5)
