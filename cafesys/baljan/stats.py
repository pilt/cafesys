# -*- coding: utf-8 -*-
from celery.task.schedules import crontab
from baljan.models import Order, Semester, Section
from django.conf import settings
from django.db.models import Avg, Count, Max, Min
from django.db.models.query import QuerySet
from django.contrib.auth.models import User, Permission, Group
from datetime import datetime
from django.core.cache import cache
from datetime import datetime, date, timedelta
from django.utils.translation import ugettext_lazy as _ 
from baljan.util import year_and_week, week_dates, adjacent_weeks
from baljan.util import get_logger

log = get_logger('baljan.stats', with_sentry=False)

LONG_PERIODIC = crontab(minute=30)
LONG_CACHE_TIME = 60 * 60 * 24 * 2 # 2 days. Should at least be longer than LONG_PERIODIC.
SHORT_PERIODIC = crontab(minute='*/10')
SHORT_CACHE_TIME = 60 * 15 * 2 # 2x15 minutes. Should at least be longer than SHORT_PERIODIC.

CACHE_KEY_BASE = 'baljan.stats.periodic.%s'
LONG_CACHE_KEY = CACHE_KEY_BASE % 'long'
LONG_CACHE_KEY_GROUP = CACHE_KEY_BASE % 'long.group'
SHORT_CACHE_KEY = CACHE_KEY_BASE % 'short'
SHORT_CACHE_KEY_GROUP = CACHE_KEY_BASE % 'short.group'
CACHE_KEYS = [SHORT_CACHE_KEY, LONG_CACHE_KEY]
CACHE_KEYS_GROUP = [SHORT_CACHE_KEY_GROUP, LONG_CACHE_KEY_GROUP]

def top_consumers(start=None, end=None, simple=False):
    """`start` and `end` are dates. Returns top consumers in the interval with
    order counts annotated (num_orders). If `simple` is true the returned list 
    consists of serializable data types only. """
    if start is None:
        start = datetime(1970, 1, 1, 0, 0)
    if end is None:
        end = datetime(2999, 1, 1, 0, 0)

    fmt = '%Y-%m-%d'
    key = 'baljan.stats.start-%s.end-%s' % (start.strftime(fmt), end.strftime(fmt))
    top = cache.get(key)
    if top is None:
        top = User.objects.filter(
            profile__show_profile=True,
            order__put_at__gte=start,
            order__put_at__lte=end,
        ).annotate(
            num_orders=Count('order'),
        ).order_by('-num_orders')

        quarter = 60 * 15 # seconds
        cache.set(key, top, quarter)

    if simple:
        simple_top = []
        for u in top:
            simple_top.append({
                'full_name': u.get_full_name(),
                'username': u.username,
                'blipped': u.num_orders,
            })
        return simple_top
    return top


class Meta(object):

    def __init__(self):
        self.classes = {}
        self.classes_ordered = []
        self.classes_i18n = {}
        self.class_members = {}
        for name, name_i18n in [
            ('board member', _('board member')),
            ('old board member', _('old board member')),
            ('worker', _('worker')),
            ('old worker', _('old worker')),
            ('normal user', _('normal user')),
            ]:
            self.classes[name] = {}
            self.classes_i18n[name] = name_i18n
            self.class_members[name] = []
            self.classes_ordered.append(name)

        self.intervals = []
        self.interval_keys = {}

    def compute_users(self):
        board_users = User.objects.filter(groups__name=settings.BOARD_GROUP).distinct()
        for user in board_users:
            self.classes['board member'][user] = True

        oldie_users = User.objects.filter(groups__name=settings.OLDIE_GROUP).distinct()
        for user in oldie_users:
            self.classes['old board member'][user] = True

        worker_users = User.objects.filter(groups__name=settings.WORKER_GROUP).distinct()
        for user in worker_users:
            self.classes['worker'][user] = True

        old_worker_users = User.objects.annotate(
            num_shiftsignups=Count('shiftsignup'),
        ).exclude(
            num_shiftsignups=0,
        ).distinct()
        for user in old_worker_users:
            self.classes['old worker'][user] = True

        self.all_users = set(User.objects.all().distinct())
        for user in self.all_users:
            self.classes['normal user'][user] = True

        for user in self.all_users:
            self.class_members[self.user_class(user)].append(user)

        self.all_sections = Section.objects.all().order_by('name')

    def compute_intervals(self):
        today = date.today()
        yesterday = today - timedelta(days=1)

        std_staff_classes = [
            'board member',
            'old board member',
            'worker',
        ]

        self.intervals.append({
            'key': 'today',
            'name': _('Today'),
            'staff classes': std_staff_classes,
            'dates': [today, today],
        })

        self.intervals.append({
            'key': 'yesterday',
            'name': _('Yesterday'),
            'staff classes': std_staff_classes,
            'dates': [yesterday, yesterday],
        })

        current_week_dates = week_dates(*year_and_week())
        self.intervals.append({
            'key': 'this_week',
            'name': _('This Week'),
            'staff classes': std_staff_classes,
            'dates': current_week_dates,
        })

        last_week_dates = week_dates(*adjacent_weeks()[0])
        self.intervals.append({
            'key': 'last_week',
            'name': _('Last Week'),
            'staff classes': std_staff_classes,
            'dates': last_week_dates,
        })

        sem_now = Semester.objects.current()
        if sem_now:
            self.intervals.append({
                'key': 'this_semester',
                'name': sem_now.name,
                'staff classes': std_staff_classes,
                'dates': list(sem_now.date_range()),
            })
        
        try:
            sem_last = Semester.objects.old()[0]
            if sem_last:
                self.intervals.append({
                    'key': 'last_semester',
                    'name': sem_last.name,
                    'staff classes': std_staff_classes + ['old worker'],
                    'dates': list(sem_last.date_range()),
                })
        except Exception, e:
            log.warning('could not fetch last semester: %s' % e)

        self.intervals.append({
            'key': 'total',
            'name': _('Total'),
            'staff classes': std_staff_classes + ['old worker'],
            'dates': None,
        })

        for interval in self.intervals:
            self.interval_keys[interval['key']] = interval


    def compute(self):
        self.compute_users()
        self.compute_intervals()

    def user_class(self, user):
        for name in self.classes_ordered:
            if user in self.classes[name]:
                return name

class Stats(object):

    def __init__(self):
        self.meta = Meta()
        self.meta.compute()

    def get_interval(self, interval_key):
        interval = self.meta.interval_keys[interval_key]
        staff_users = set()
        for cls_name in interval['staff classes']:
            staff_users |= set(self.meta.class_members[cls_name])
        normal_users = self.meta.all_users - staff_users

        limit = 15
        groups = []
        for title, users in [
            (_('Normal Users'), normal_users),
            (_('Staff'), staff_users),
            ]:
            top = User.objects.filter(
                id__in=[u.id for u in users],
                profile__show_profile=True,
            )
            if interval['dates']:
                dates = list(interval['dates'])
                top = top.filter(
                    order__put_at__gte=dates[0],
                    order__put_at__lte=dates[-1] + timedelta(days=1),
                )
            top = top.annotate(
                num_orders=Count('order'),
            ).order_by('-num_orders')[:limit]
            top = list(top)

            groups.append({
                'title': title,
                'top_users': top,
            })

        return {
            'name': interval['name'],
            'groups': groups,
            'empty': sum([len(g['top_users']) for g in groups]) == 0,
        }


class SectionStats(object):

    def __init__(self):
        self.meta = Meta()
        self.meta.compute()

    def get_interval(self, interval_key):
        interval = self.meta.interval_keys[interval_key]
        staff_users = set()
        for cls_name in interval['staff classes']:
            staff_users |= set(self.meta.class_members[cls_name])
        normal_users = self.meta.all_users - staff_users

        limit = 15
        groups = []
        for title, users in [
                (_('Normal Users'), normal_users),
                (_('Staff'), staff_users),
                ]:

            section_stats = []
            for section in self.meta.all_sections:
                orders = Order.objects.filter(
                    user__profile__section__id=section.id,
                    user__id__in=[u.id for u in users],
                )

                if interval['dates']:
                    dates = list(interval['dates'])
                    orders = orders.filter(
                        put_at__gte=dates[0],
                        put_at__lte=dates[-1] + timedelta(days=1),
                    )

                this_users = User.objects.filter(
                    profile__section__id=section.id,
                    id__in=[u.id for u in users],
                ).distinct().count()

                if this_users == 0:
                    continue

                sec_stat = {
                    'name': section.name,
                    'num_orders': orders.count(),
                    'num_users': this_users,
                    'avg_orders': 0,
                }

                if sec_stat['num_orders'] == 0:
                    continue

                if this_users:
                    sec_stat['avg_orders'] = float(sec_stat['num_orders']) / this_users

                section_stats.append(sec_stat)

            section_stats.sort(key=lambda x: x['avg_orders'], reverse=True)
            groups.append({
                'title': title,
                'top_sections': section_stats,
            })

        return {
            'name': interval['name'],
            'groups': groups,
            'empty': sum([len(g['top_sections']) for g in groups]) == 0,
        }
