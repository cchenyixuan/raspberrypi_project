import time
import traceback
from typing import List

from gpiozero.pins.pigpio import PiGPIOFactory
from gpiozero import AngularServo
import time
import os


#  run "sudo pigpiod" to start hardware-pwm


class CloudPlatform:
    def __init__(self, host="172.25.25.25", port=8888, motor_x_pin=12, motor_y_pin=13):
        factory = PiGPIOFactory()
        self.servo_motor1 = AngularServo(
            pin=motor_x_pin,
            initial_angle=0.0,
            min_angle=-90,
            max_angle=90,
            min_pulse_width=0.5/1000,
            max_pulse_width=2.5/1000,
            frame_width=20/1000,
            pin_factory=factory
        )
        self.servo_motor2 = AngularServo(
            pin=motor_y_pin,
            initial_angle=0.0,
            min_angle=-90,
            max_angle=40,
            min_pulse_width=0.5 / 1000,
            max_pulse_width=1.94444 / 1000,
            frame_width=20 / 1000,
            pin_factory=factory
        )

    def __call__(self, degree: List):
        self.servo_motor1.angle = degree[0]
        self.servo_motor2.angle = degree[1]


if __name__ == "__main__":
    plm = CloudPlatform()
    while True:
        d = input("Input Degree: ")
        try:
            d = d.split(" ")
            d = [float(_) for _ in d]
            plm(d)
        except (IndexError, ValueError) as error:
            traceback.print_exc()
            plm([0, 0])
            time.sleep(2)
            break


