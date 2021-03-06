# -*- coding: utf-8 -*-

from datagrid.grids import DataGrid, Column, NonDatabaseColumn
from django.utils.translation import ugettext_lazy as _ 
from django.conf import settings

class ShiftGrid(DataGrid):
    when = Column()
    span = Column()
    exam_period = Column()
    enabled = Column()


def pl_image(path):
    if path:
        return '<img src="%s/%s" />' % (settings.MEDIA_URL, path)
    return ''

def pl_desc(good):
    if good.description:
        return '%s<br/><em>%s</em>' % (good.title, good.description)
    return '%s' % good.title

def pl_price(good):
    return '%s %s' % good.current_costcur()

class PriceListGrid(DataGrid):
    img = Column(_("image"),
        data_func=pl_image,
    )
    desc = NonDatabaseColumn(_("desciption"),
        data_func=pl_desc,
    )
    price = NonDatabaseColumn(_("price"),
        data_func=pl_price,
    )
