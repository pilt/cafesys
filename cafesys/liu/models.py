# -*- coding: utf-8 -*-
from django.db import models
from django.utils.encoding import smart_str
from django.contrib.auth.models import User, Group
from django.db.models.signals import post_save
from datetime import date
import random
import string
from dateutil.relativedelta import relativedelta

class Student(models.Model):
    user = models.ForeignKey(User, unique=True)

    liu_id = models.CharField(max_length=8, unique=True)
    balance = models.IntegerField(default=0)

    def __str__(self):
        fmt = "%s" % self.liu_id
        return smart_str(fmt)

    def is_worker(self):
        return len(self.user.groups.filter(name='workers')) != 0

    def is_board_member(self):
        return len(self.user.groups.filter(name='board')) != 0

    def is_regular(self):
        if self.is_worker() or self.is_board_member():
            return False
        else:
            return True

    def scheduled_for(self):
        scheds = list(self.scheduledmorning_set.all()) + list(self.scheduledafternoon_set.all())
        scheds.sort(key=lambda s: s.shift.day)
        scheds = [s for s in scheds if s.shift.day >= date.today()]
        return scheds

    def group_requests(self):
        return self.joingrouprequest_set.all()

    def wants_to_be_a_worker(self):
        return len(self.joingrouprequest_set.filter(group__name='workers')) != 0


def create_profile(sender, instance=None, **kwargs):
    if instance is None:
        return
    profile, created = Student.objects.get_or_create(
            user=instance,
            liu_id=instance.username,
            )

post_save.connect(create_profile, sender=User)


class JoinGroupRequest(models.Model):
    student = models.ForeignKey(Student)
    group = models.ForeignKey(Group)

    @staticmethod
    def from_group_name(student, group_name):
        group = Group.objects.get(name=group_name)
        return JoinGroupRequest(student=student, group=group)

    def __str__(self):
        fmt = "%s wants to be in %s" % (self.student.liu_id, self.group.name)
        return smart_str(fmt)


CODE_LENGTH = 8
BALANCE_CODE_DEFAULT_VALUE = 100 # SEK
RELATIVE_SERIES_LEAST_VALIDITY = relativedelta(years=1)
SERIES_DEFAULT_VALUE = 1000 # SEK
SERIES_CODE_COUNT = SERIES_DEFAULT_VALUE // BALANCE_CODE_DEFAULT_VALUE

def default_issued():
    return date.today()

def default_least_valid_until():
    return default_issued() + RELATIVE_SERIES_LEAST_VALIDITY

def generate_balance_code():
    pool = string.letters + string.digits
    def get_code():
        return ''.join(random.choice(pool) for _ in range(CODE_LENGTH))

    code = get_code()
    while len(BalanceCode.objects.filter(code=code)) != 0:
        code = get_code()
    return code


class RefillSeries(models.Model):
    issued = models.DateField(default=default_issued)
    least_valid_until = models.DateField(default=default_least_valid_until)

    class Meta:
        verbose_name = 'refill series'
        verbose_name_plural = 'refill series'

    def codes(self):
        return BalanceCode.objects.filter(refill_series=self)

    def used(self):
        codes = self.codes()
        used_codes = [c for c in codes if c.used_by]
        return used_codes

    def unused(self):
        codes = self.codes()
        unused_codes = [c for c in codes if not c.used_by]
        return unused_codes

    def __str__(self):
        used = len(self.used())
        codes = len(self.codes())
        pc = 100.0*float(used)/codes
        fmt = "%s. issued %s, %d of %d used (%.1f%%)" \
                % (self.pk, self.issued.strftime('%Y-%m-%d'), used, codes, pc)
        return smart_str(fmt)

code_help = "To create a bulk of codes, <a href='../../refillseries/add'>create a new refill series</a> instead."

class BalanceCode(models.Model):
    created_at = models.DateField(auto_now_add=True)
    code = models.CharField(max_length=CODE_LENGTH, unique=True, 
            default=generate_balance_code, help_text=code_help)
    value = models.PositiveIntegerField(default=BALANCE_CODE_DEFAULT_VALUE)
    refill_series = models.ForeignKey(RefillSeries)
    used_by = models.ForeignKey(Student, null=True, blank=True)
    used_at = models.DateField(blank=True, null=True)

    def __str__(self):
        fmt = "%d SEK" % self.value

        if self.used_by:
            try:
                usedpart = 'used by %s %s' % (self.used_by.liu_id, self.used_at.strftime('%Y-%m-%d'))
            except:
                usedpart = 'used by %s' % self.used_by.liu_id
        else:
            usedpart = 'unused'

        series = self.refill_series
        fmt = "%s (series %d, %s)" % (fmt, series.pk, usedpart)
        return smart_str(fmt)
