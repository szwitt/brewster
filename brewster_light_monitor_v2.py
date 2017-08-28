#!/usr/bin/python3


import slackweb
import time
import logging
import RPi.GPIO as gpio
from time import sleep

import brewster_log as brewlog
import brewster_slack as brewslack


#  GPIO Settings
gpio.setwarnings(True)
gpio.setmode(gpio.BCM)
gpio.setup(4, gpio.IN)


#  setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


"""
This function will monitor the GPIO with the light sensor to look for changes.  Initial
conditions are brew light is at zero, once the light is turned on the thread will exit 
out and return brewing is in progress. 
"""


def brew_light_counter(light_value):
    global light_count
    light_count += 1
    print("count:%s, value:%s" % light_count, light_value)


"""
Main Function:  There are no initial condition for the main function.  This function will
execute in the following manner.
"""


light_count = 0
# gpio.add_event_detect(4, gpio.RISING, callback=brew_light_counter, bouncetime=300)


def brew_watch():
    global light_count
    pot_count, brew_start, brewing = brewlog.read_brewing_log()
    light_count_check = 0

    while True:
        print('light_count %s\nlight_watch %s' % (light_count, light_count_check))

        if light_count == 0:
            current_epoch = int(time.time())
            print('Not Brewing: -------- Pot Count: %s Not Brewing Check: %s Brewing?: %s'
                  % (pot_count, current_epoch, brewing))
            sleep(2)
            light_count = 1

        elif (light_count > 0) and (light_count_check < light_count) and (brewing is False):
            pot_count, brew_update, brewing = brewlog.update_brewing_log(pot_count)
            light_count_check = light_count
            brewslack.slack_send_message('finished_brewing', pot_count)
            print('Start Brewing: ------ Pot Count: %s Brew Start: %s Brewing?: %s'
                  % (pot_count, brew_update, brewing))
            sleep(5)

        elif (light_count > 0) and (light_count_check < light_count) and (brewing is True):
            light_count_check = light_count
            sleep(5)

        elif light_count_check == light_count:
            pot_count, brew_end, brewing = brewlog.close_brewing_log(pot_count)
            brewslack.slack_send_message('finished_brewing', pot_count)
            print('Finished Brewing: --- Pot Count: %s Brew End: %s Brewing?: %s'
                  % (pot_count, brew_end, brewing))
            light_count = 0
            light_count_check = 0
            sleep(5)

        else:
            print('Something Broke:\nPot Count:%s\nLast Brew\nStart:%s'
                  '\nlight_count:%s\nlight_count_check:%s\nbrewing%s'
                  % (pot_count, brew_start, light_count, light_count_check, brewing))
            sleep(2)

brew_watch()
