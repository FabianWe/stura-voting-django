# The MIT License (MIT)
#
# Copyright (c) 2016 Fabian Wenzelmann
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from django.db import models
from django.utils.translation import ugettext_lazy as _, ungettext_lazy
import django.utils
from django.core.validators import MaxValueValidator, MinValueValidator


from decimal import Decimal
import uuid

# Create your models here.


class VotingTerm(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pub_date = models.DateTimeField(
        _('Erstellungszeitpunkt'),
        default=django.utils.timezone.now)
    name = models.CharField(
        _('Name'),
        help_text=_('Name der Abstimmungsperiode'),
        max_length=40,
        unique=True)


class VotingWeightGroup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    term = models.ForeignKey(
        VotingTerm,
        on_delete=models.CASCADE,
        verbose_name=_('Abstimmungszeitraum'),
        help_text='Abstimmungszeitraum dem diese Gewichtung zugeordnet wird')


class VotingWeight(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        _('Name'),
        help_text=_('Name der abstimmenden Gruppe'),
        max_length=75)
    weight = models.PositiveSmallIntegerField(
        verbose_name=_('Gewichtung'),
        help_text=_('Die Abstimmungsgewichtung der Gruppe'))
    group = models.ForeignKey(
        VotingWeightGroup,
        on_delete=models.CASCADE,
        verbose_name=_('Gruppe'),
        help_text=_('Gruppe zu der diese Eintragung gehört'))

    class Meta:
        unique_together = ('group', 'name')


class VotingDay(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField(
        verbose_name=_('Datum'),
        help_text='Datum an dem die Abstimmungen durchgeführt werden.')
    weights = models.ForeignKey(
        VotingWeightGroup,
        on_delete=models.CASCADE,
        verbose_name=_('Gewichtungsgruppe'),
        help_text=_('Gewichtungsgruppe welche zur Auszählung verwendet wird'))


class GeneralPoll(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    percent_required = models.DecimalField(
        _('Prozent'),
        help_text=_(
            'Prozent die nötig sind, damit die Abstimmung als angenommen gilt'),
        max_digits=4,
        decimal_places=2,
        default=Decimal('50.00'),
        validators=[MinValueValidator(Decimal('0.00')),
                    MaxValueValidator(Decimal('100.00'))])
    all_votes = models.BooleanField(
        _('Alle Stimmen?'),
        help_text=_(
            'Wenn aktiviert werden ALLE Stimmen gezählt, auch jene die nicht mit abgestimmt haben!'),
        default=False)
