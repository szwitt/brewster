#!/usr/bin/python3

"""
This function will handle the direct messaging to a slack webhook notifying
users 1) Pot #x of the day is brewing, or if one was found as empty.
"""

import slackweb
import logging


#  Globals for Test - This is for messages directly into TonkaToy
slack = slackweb.Slack(url="xxxxx")
light_count = 0


#  setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


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
