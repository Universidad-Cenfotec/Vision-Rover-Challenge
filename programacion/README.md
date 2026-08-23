
# Programación del CenfoBot

El CenfoBot se programa en CircuitPython, ya sea mediante una plataforma web que no requiere instalación, usando bloques o utilizando Thonny.
> [Este video explica](https://youtu.be/lS5O-A5Uo8o?si=VfWL0nDUsuCoXepT)


## Plataforma web para programar el CenfoBot en CircuitPython

<a href="https://ideacode.crcibernetica.com/" target="_blank">
  <img src="https://github.com/Universidad-Cenfotec/Sumobot/blob/main/imagenes/IdeaCode.png" width="600">
</a>

[En este link, pueden utilizar la plataforma web de programación en CircuitPython del CenfoBot](https://ideacode.crcibernetica.com/).  No requiere instalación. Pronto publicaremos una guía básica


## Software para programar el CenfoBot en CircuitPython

<img src="https://github.com/Universidad-Cenfotec/Sumobot/blob/main/imagenes/Thonny_Sumobot.png" width="600">

Para programar el CenfoBot se utiliza Thonny, el cual se puede descargar desde este [enlace](https://thonny.org/).

### Instrucciones Rápidas:
- Descargar la última versión de Thonny.
- Instalar.
- Una vez instalado, ir al menú "Herramientas > Opciones" o "Tools > Options" en inglés.
- En la pestaña "Intérprete" (o "Interpreter" en inglés), seleccionar "CircuitPython (Generic)".
- ¡Listo!
- [Video con detalles](https://youtu.be/Zc3oaAbVAdc)

### Instruciones más detalladas:
- [Ver este enlace](https://github.com/Universidad-Cenfotec/Sumobot/blob/main/instala_thonny.md)

### Iniciar Thonny
- [Seguir intrucciones acá](https://github.com/Universidad-Cenfotec/Sumobot/blob/main/uso_thonny.md)
- [Ver video explicativo](https://youtu.be/EOnnslZhL2c?si=IYAHV_utJocjeJvx)

## Programación del CenfoBot en C/C++

El CenfoBot también puede programarse en **C/C++** utilizando el entorno de desarrollo de Arduino. Esta opción permite trabajar directamente con las capacidades del microcontrolador ESP32 de la IdeaBoard y utilizar las bibliotecas disponibles para esta plataforma.

### Instalar Arduino IDE

1. Descargar e instalar la versión más reciente de [Arduino IDE](https://www.arduino.cc/en/software).

2. Abrir Arduino IDE y entrar en:

   `File > Preferences`

   o, en español:

   `Archivo > Preferencias`

3. En **Additional Boards Manager URLs** agregar la siguiente dirección:

   `https://espressif.github.io/arduino-esp32/package_esp32_index.json`

4. Ir a:

   `Tools > Board > Boards Manager`

5. Buscar:

   `esp32`

6. Instalar el paquete **esp32 by Espressif Systems**.

### Seleccionar la tarjeta

Conectar el CenfoBot mediante USB y seleccionar una tarjeta ESP32 compatible desde:

`Tools > Board > esp32`

Luego seleccionar el puerto correspondiente desde:

`Tools > Port`

Dependiendo de la versión de la IdeaBoard, puede ser necesario seleccionar específicamente el modelo de ESP32 correspondiente a la placa.

### Programa básico

Para comprobar que el entorno funciona correctamente se puede comenzar con un programa sencillo:

```cpp
void setup() {
  Serial.begin(115200);
}

void loop() {
  Serial.println("Hola CenfoBot");
  delay(1000);
}
```

Presione **Upload** para compilar y transferir el programa al CenfoBot.

Puede abrir el monitor serial desde:

`Tools > Serial Monitor`

y configurarlo a:

`115200 baud`

### Importante

Cuando se programa la IdeaBoard utilizando Arduino/C++, el firmware de CircuitPython instalado en la placa es reemplazado por el programa compilado.

Si posteriormente desea volver a utilizar CircuitPython, deberá volver a instalarlo utilizando el procedimiento de flasheo descrito en la sección **Resetear (Flashear) el IdeaBoard**.

### Alternativa con PlatformIO

También es posible programar el CenfoBot utilizando **PlatformIO** con Visual Studio Code. Esta alternativa es útil para proyectos más grandes, ya que facilita la administración de bibliotecas, dependencias, compilación y organización del código C/C++.

[PlatformIO](https://platformio.org/)


##  Resetear (Flashear) el IdeaBoard

Para resetear el IdeaBoard, se hace fácilmente a través de esta página:  [IdeaBoard Flasher](https://crcibernetica.github.io/ideaboard-terminal/) Asegurese que Thonny esté CERRADO, cuando intente reflashear o el flasher no va a encontrar el puerto cn el IdeaBoard.

En [este link hay un video que explica como hacerlo](https://youtu.be/sa7HqL8b7Vo?si=5yNcEPUFerEBaM1g)


## Código


El código `code.py` está desarrollado en CircuitPython. CircuitPython es una implementación de Python diseñada para microcontroladores y facilita la programación de dispositivos como el ESP32. El CenfoBot está preparado para trabajar con CircuitPython. Si por alguna razón se debe "reflashear" el IdeaBoard, siga las instrucciones en este [enlace](https://github.com/CRCibernetica/circuitpython-ideaboard/wiki/3.-Installation).

---

## Videos Instructivos de Programación

Constantemente estaremos actualizando links cuando se vayan creando más videos:

- [Instalación de Thonny](https://youtu.be/Zc3oaAbVAdc?si=447Po0KyL_0hDAhJ)
