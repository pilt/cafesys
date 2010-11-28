# -*- coding: utf-8 -*-
from celery.decorators import task
from baljan.sounds import play_sound
from baljan.util import get_logger
from django.conf import settings

log = get_logger('baljan.tasks')

@task(ignore_result=True)
def play_success_normal():
    return play_sound(settings.SOUND_SUCCESS_NORMAL)

@task(ignore_result=True)
def play_success_rebate():
    return play_sound(settings.SOUND_SUCCESS_REBATE)

@task(ignore_result=True)
def play_no_funds():
    return play_sound(settings.SOUND_NO_FUNDS)

@task(ignore_result=True)
def play_error():
    return play_sound(settings.SOUND_ERROR)

@task(ignore_result=True)
def play_start():
    return play_sound(settings.SOUND_START)

@task(ignore_result=True)
def play_leader():
    return play_sound(settings.SOUND_LEADER)

SOUND_FUNCS_AND_DESCS = [
    (play_success_normal, "normal success"),
    (play_success_rebate, "rebate success"),
    (play_no_funds, "no funds"),
    (play_error, "error"),
    (play_start, "start"),
    (play_leader, "leader"),
]

SOUND_FUNCS_AND_LIKELINESS = [
    (play_start, 0.01),
    (play_error, 0.02),
    (play_leader, 0.05),
    (play_no_funds, 0.1),
    (play_success_rebate, 0.5),
    (play_success_normal, 0.8),
]

def test_play_all():
    for (func, msg) in SOUND_FUNCS_AND_DESCS:
        log.debug(msg)
        res = func.delay()
        res.get()
