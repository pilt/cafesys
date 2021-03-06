# -*- coding: utf-8 -*-

from django import forms
import baljan.models
from django.contrib.auth.models import User
from django.utils.translation import ugettext as _

class SemesterForm(forms.ModelForm):
    class Meta:
        model = baljan.models.Semester


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = (
                'first_name',
                'last_name',
                )

class ProfileForm(forms.ModelForm):
    class Meta:
        model = baljan.models.Profile
        fields = (
                'mobile_phone',
                'picture',
                'show_profile',
                'show_email',
                'section',
                'motto',
                )


class RefillForm(forms.Form):
    code = forms.CharField(max_length=baljan.models.BALANCE_CODE_LENGTH,
            label=_("code"),
            help_text=_(u"found on your value card"))


class ImportOldCardForm(forms.Form):
    code = forms.IntegerField(label=_("code"))


class ShiftSelectionForm(forms.Form):
    CHOICES = (
        ('enabled', _('open')),
        ('disabled', _('closed')),
        ('exam_period', _('exam period')),
    )

    make = forms.ChoiceField(
        label=_("make"),
        choices=CHOICES,
    )
