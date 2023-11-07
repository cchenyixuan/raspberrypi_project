import time
from gpiozero.pins.pigpio import PiGPIOFactory
from gpiozero import AngularServo
import time
import os


#  run "sudo pigpiod" to start hardware-pwm


class CloudPlatform:
    def __init__(self, host="172.25.25.25", port=8888):
        factory = PiGPIOFactory()
        self.servo_motor1 = AngularServo(
            pin=23,
            initial_angle=0.0,
            min_angle=-90,
            max_angle=90,
            min_pulse_width=1/1000,
            max_pulse_width=2/1000,
            frame_width=20/1000,
            pin_factory=factory
        )

