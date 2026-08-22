# Códigos Ejemplo del CenfoBot Rover

Estos códigos proporcionan ejemplos y componentes base para programar los CenfoBots utilizados en el **Vision Rover Challenge**. Incluyen control de motores, sensores, orientación, comunicación y funciones básicas para construir el sistema autónomo de cada rover.

| Área | Código | Propósito |
| --- | --- | --- |
| **Movimiento básico** | `test_motores.py` | Probar los motores y realizar movimientos básicos como avanzar, retroceder y girar. |
| **Percepción** | `code_4IR.py` | Leer los cuatro sensores infrarrojos del CenfoBot. |
| **Percepción** | `code_ultrasonic.py` | Medir distancias y detectar obstáculos mediante el sensor ultrasónico. |
| **Percepción** | `color_detect.py` | Utilizar el sensor de color para identificar colores de objetos cercanos. |
| **IMU** | `code_acc.py` | Leer aceleración y velocidad angular utilizando el acelerómetro y giroscopio del rover. |
| **Control** | `code_PID.py` | Ejemplo de control PID utilizando la IMU para corregir el movimiento del rover. |
| **Control de trayectoria** | `move_heading.py` | Avanzar intentando mantener una orientación determinada mediante IMU y control PID. |
| **Control de giro** | `turn_angle.py` | Girar aproximadamente un número determinado de grados utilizando el giroscopio. |
| **Calibración** | `motor_calibration.py` | Medir y compensar diferencias de comportamiento entre los motores izquierdo y derecho. |
| **Comunicación Wi-Fi** | `wifi_command_receiver.py` | Recibir comandos automáticamente desde una computadora mediante Wi-Fi y TCP. |
| **Comunicación ESP-NOW** | `espnow_bidirectional.py` | Establecer comunicación bidireccional directa entre los dos rovers mediante ESP-NOW. |
| **Comunicación ESP-NOW** | `ESPNOW/` | Ejemplo introductorio de comunicación ESP-NOW entre dos IdeaBoards. |
| **Protocolo** | `command_protocol.py` | Definir un formato común para órdenes como `STOP`, `MOTOR`, `TURN` y `HEADING`. |
| **Estado del rover** | `robot_state.py` | Mantener estados operativos como `IDLE`, `MOVING`, `TURNING`, `STOPPED`, `ERROR` y `OFFLINE`. |
| **Datos** | `code_storage.py` | Registrar mediciones del rover para analizarlas posteriormente. |
| **Infraestructura** | `ideaboard.py` | Proporcionar las funciones de bajo nivel necesarias para controlar el hardware de la IdeaBoard. |
