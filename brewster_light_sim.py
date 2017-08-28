#!/usr/bin/python3

import time
import RPi.GPIO as GPIO

LED = 21

GPIO.setmode(GPIO.BCM)
GPIO.setup(LED, GPIO.OUT)

for i in range(0, 50):
    GPIO.output(LED, True)
    time.sleep(.5)
    GPIO.output(LED, False)
    time.sleep(.5)
    print ("Blink %s" % i)

GPIO.output(LED, False)
