#!/usr/bin/python3

"""
The following functions will handle managing the state of the daily brewing log.   The first file will handle
the creation and update of a log from startup / logging of the pi.  The second will handle starting a pot brew
and the final function will be to handle ending the pot brew and creating an archive.

This function is to read the current brewing state file.  This file will maintain the current pot count,
current pot brewing status, and current pot brewing time.  Will create a file if there is none.
"""

import datetime
import time
import decimal
import logging

#  set logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


#  dynamo table and access settings
dynamodb = boto3.resource('dynamodb',
                          aws_access_key_id='xxxxxx',
                          aws_secret_access_key='xxxxxxx',
                          region_name='xxxxxx')
table = dynamodb.Table('xxxxxx')


def create_brewing_log():
    today = str(datetime.date.today())
    current_epoch = int(time.time())
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
    print("creating brewing file for: %s" % today)
    return


def read_brewing_log():
    today = str(datetime.date.today())
    print("reading brewing file for: %s" % today)
    current_epoch = int(time.time())
    brewing_file = table.get_item(Key={"brewing_date": today})

    if 'Item' not in brewing_file:
        create_brewing_log()
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


def update_brewing_log(current_pot_count):
    today = str(datetime.date.today())
    current_epoch = int(time.time())
    updated_pot_count = int(current_pot_count) + 1

    brewing_file = table.get_item(Key={"brewing_date": today})

    if 'Item' not in brewing_file:
        create_brewing_log()
        return 1, current_epoch, True  # Number of pots, start_time, pot_brewing

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


def close_brewing_log(current_pots_brewed):
    today = str(datetime.date.today())
    current_epoch = int(time.time())
    brewing_file = table.get_item(Key={"brewing_date": today})

    if 'Item' not in brewing_file:
        create_brewing_log()
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

