# -*- coding: utf-8 -*-
from baljan.models import BalanceCode
from datetime import datetime
from baljan.util import get_logger

log = get_logger('baljan.credits')

class CreditsError(Exception):
    pass

class BadCode(CreditsError):
    pass

def used_by(user):
    return BalanceCode.objects.filter(
        used_by=user,
    ).order_by('-used_at', '-id')


def get_unused_code(entered_code):
    try:
        bc = BalanceCode.objects.get(
                code__exact=entered_code,
                used_by__isnull=True,
                used_at__isnull=True)
        return bc
    except BalanceCode.DoesNotExist:
        raise BadCode()


def is_used(entered_code, lookup_by_user=None):
    try:
        bc = get_unused_code(entered_code)
        if lookup_by_user:
            log.info('%r found %r unused' % (lookup_by_user, entered_code))
        return not bc
    except BadCode:
        if lookup_by_user:
            log.info('%r found %r used or invalid' % (lookup_by_user, entered_code))
        return True


def manual_refill(entered_code, by_user):
    try:
        use_code_on(get_unused_code(entered_code), by_user)
        return True
    except BalanceCode.DoesNotExist:
        log.warning('%r tried bad code %r' % (by_user, entered_code))
        raise BadCode()


def use_code_on(bc, user):
    assert bc.used_by is None
    assert bc.used_at is None
    profile = user.get_profile()
    assert bc.currency == profile.balance_currency
    bc.used_by = user
    bc.used_at = datetime.now()
    bc.save()
    profile.balance += bc.value
    profile.save()
    log.info('%r used %r' % (user, bc))
    return True