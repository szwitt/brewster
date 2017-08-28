#!/usr/bin/python3


import slackweb
import boto3
import datetime
import time
import decimal
import logging
import RPi.GPIO as gpio
from time import sleep


#  GPIO Settings
gpio.setwarnings(True)
gpio.setmode(gpio.BCM)
gpio.setup(4, gpio.IN)


#  Globals for Production
slack = slackweb.Slack(url="xxxxxx")

#  Globals for Test - This is for messages directly into TonkaToy
#  slack = slackweb.Slack(url="xxxxxx")

light_count = 0


#  setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb',
                          aws_access_key_id='xxxxxx',
                          aws_secret_access_key='xxxxxxx',
                          region_name='xxxxxx')
table = dynamodb.Table('xxxxxx')

"""
This function will handle the direct messaging to a slack webhook notifying
users 1) Pot #x of the day is brewing, or if one was found as empty.
"""


def slack_send_message(message, pots):

    pot_count = int(pots)
    cups_brewed = pot_count * 8.5

    first_pot = '*First pot of the day is brewing* :coffee:'
    started_brewing = 'Pot %s Brewing: :woohoo:' % pot_count
    brewing_consumed = 'Pot %s Brewing: :woohoo:' % pot_count
    finished_brewing = 'Pot %s Finished: %s :coffee: Cups brewed today.' % (pot_count, cups_brewed)

    if message == 'started_brewing':
        if pot_count == 1:
            slack.notify(text=first_pot)
            print('Slack:FirstBrew')

        elif pot_count <= 2:
            slack.notify(text=started_brewing)
            print('Slack:NewBrew')

        else:
            slack.notify(text=brewing_consumed)
            print('Slack:NewBrewConsumed')

    elif message == 'finished_brewing':
        slack.notify(text=finished_brewing)
        print('Slack:FinishedBrew')

    else:
        print('error')
        logger.error('there was an error with the message: %s' % message)


"""
The following functions will handle managing the state of the daily coffee log.   The first file will handle
the creation and update of a log from startup / logging of the pi.  The second will handle starting a pot brew
and the final function will be to handle ending the pot brew and creating an archive.  

This function is to read the current brewing state file.  This file will maintain the current pot count,
current pot brewing status, and current pot brewing time.  Will create a file if there is none.  
"""


def read_current_brewing_file():
    today = str(datetime.date.today())
    print("%s" % today)
    current_epoch = int(time.time())
    brewing_file = table.get_item(Key={"brewing_date": today})

    if 'Item' not in brewing_file:
        table.put_item(
            Item={
                'brewing_date': today,
                'current_pot_count': 0,
                'brew_start_time': 0,
                'brew_end_time': 0,
                'idle_start_time': current_epoch,
                'brew_in_progress': False
            }
        )
        return 0, current_epoch, False  # Number of pots, start_time, pot_brewing

    elif 'Item' in brewing_file:
        current_pot_count = int(brewing_file['Item']['current_pot_count'])
        brew_start_time = int(brewing_file['Item']['brew_start_time'])
        brewing = bool(brewing_file['Item']['brew_in_progress'])

        if brewing is True and ((current_epoch - brew_start_time) > 10):
            print("Prior brewing file: %s, %s, %s" % (current_pot_count, brew_start_time, brewing))
            table.update_item(
                Key={
                    'brewing_date': today
                },
                UpdateExpression="set brew_start_time = :st, brew_end_time = :et,"
                                 " idle_start_time = :it, brew_in_progress = :b",
                ExpressionAttributeValues={
                    ':st': 0,
                    ':et': 0,
                    ':it': current_epoch,
                    ':b': False
                },
                ReturnValues="UPDATED_NEW"
            )
            print('Completing last pot and resetting brewing')
            return current_pot_count, current_epoch, False  # Number of pots, start_time, pot_brewing

        else:
            return current_pot_count, brew_start_time, brewing  # Number of pots, start_time, pot_brewing

    else:
        logger.error('there was an error with the daily log file.')

"""
This function will handle capturing and logging the state when a brewing cycle starts.
Inputs:   Today (key for dynamo, prior pot count and
Outputs:  Updates to dynamo state, updated pot count, time the brewing started (epoch).
"""


def update_current_brewing_file(current_pot_count):
    today = str(datetime.date.today())
    current_epoch = int(time.time())
    updated_pot_count = int(current_pot_count) + 1

    brewing_file = table.get_item(Key={"brewing_date": today})

    # This handles the change in days if there is no daily log file.  This is based on this being an update call from
    # the prior day of the script running.
    if 'Item' not in brewing_file:
        print('There was an error with the log file:  Attempted to update, no file found')
        read_current_brewing_file()
        return 1, current_epoch, True

    elif 'Item' in brewing_file:
        table.update_item(
            Key={
                'brewing_date': today
            },
            UpdateExpression="set brew_start_time = :t, current_pot_count = :p, "
                             "brew_in_progress = :b",
            ExpressionAttributeValues={
                ':t': decimal.Decimal(current_epoch),
                ':p': decimal.Decimal(updated_pot_count),
                ':b': True
            },
            ReturnValues="UPDATED_NEW"
        )
        return updated_pot_count, current_epoch, True

"""
This function will handle the end of the brewing cycle.
Log the prior pot to a new file
Create a new daily log file to be consumed
"""


def close_current_brewing_file(current_pots_brewed):
    today = str(datetime.date.today())
    current_epoch = int(time.time())
    brewing_file = table.get_item(Key={"brewing_date": today})

    if 'Item' not in brewing_file:
        read_current_brewing_file()
        print('There was an error in the log file:  Attempted to close, no file found')
        return (int(current_pots_brewed) + 1), current_epoch, False

    elif 'Item' in brewing_file:
        current_pot_brew_start_time = brewing_file['Item']['brew_start_time']
        idle_start_time = brewing_file['Item']['idle_start_time']
        time_to_brew = current_epoch - current_pot_brew_start_time
        time_between_brew = current_pot_brew_start_time - idle_start_time
        updated_pots_brewed = int(current_pots_brewed)
        finished_pot_number = updated_pots_brewed + 100
        finished_pot = str('{"brew_start": "%s", "brew_end": "%s", "brew_time": "%s", "idle_time": "%s"}' %
                           (current_pot_brew_start_time, current_epoch, time_to_brew, time_between_brew))

        table.update_item(
            Key={
                'brewing_date': today
            },
            UpdateExpression="set brew_start_time = :st, brew_end_time = :et, idle_start_time = :it, "
                             "current_pot_count = :p, brew_in_progress = :b, Pot%s = :fp" % finished_pot_number,
            ExpressionAttributeValues={
                ':st': 0,
                ':et': 0,
                ':it': current_epoch,
                ':fp': finished_pot,
                ':p': decimal.Decimal(updated_pots_brewed),
                ':b': False
            },
            ReturnValues="UPDATED_NEW"
        )
        return updated_pots_brewed, current_epoch, False


"""
This function will monitor the GPIO with the light sensor to look for changes.  Initial
conditions are brew light is at zero, once the light is turned on the thread will exit 
out and return brewing is in progress. 
"""


def brew_light_counter(light_value):
    global light_count
    light_count += 1
    print("light_count:%s, light_value:%s" % light_count, light_value)


"""
Main Function:  There are no initial condition for the main function.  This function will
execute in the following manner.
"""

gpio.add_event_detect(4, gpio.RISING, callback=brew_light_counter, bouncetime=300)


def brew_watch():
    global light_count
    pot_count, brew_start, brewing = read_current_brewing_file()
    light_count_check = 0

    while True:
        print('light_count %s\nlight_watch %s' % (light_count, light_count_check))

        if light_count == 0:
            current_epoch = int(time.time())
            print('Not Brewing: -------- Pot Count: %s Not Brewing Check: %s Brewing?: %s'
                  % (pot_count, current_epoch, brewing))
            sleep(2)
            # light_count = 1

        elif (light_count > 0) and (light_count_check < light_count) and (brewing is False):
            pot_count, brew_update, brewing = update_current_brewing_file(pot_count)
            light_count_check = light_count
            slack_send_message('started_brewing', pot_count)
            print('Start Brewing: ------ Pot Count: %s Brew Start: %s Brewing?: %s'
                  % (pot_count, brew_update, brewing))
            sleep(5)

        elif (light_count > 0) and (light_count_check < light_count) and (brewing is True):
            light_count_check = light_count
            sleep(5)

        elif light_count_check == light_count:
            pot_count, brew_end, brewing = close_current_brewing_file(pot_count)
            slack_send_message('finished_brewing', pot_count)
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
