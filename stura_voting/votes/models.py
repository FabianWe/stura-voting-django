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


class WeightedVoter(models.Model):
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
        help_text='Datum an dem die Abstimmungen durchgeführt werden')
    weights = models.ForeignKey(
        VotingWeightGroup,
        on_delete=models.CASCADE,
        verbose_name=_('Gewichtungsgruppe'),
        help_text=_('Gewichtungsgruppe welche zur Auszählung verwendet wird'))


class GeneralPoll(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        _('Name'),
        help_text=_('Name / Beschreibung der Abstimmung'),
        max_length=250)
    voting_day = models.ForeignKey(
        VotingDay,
        on_delete=models.CASCADE,
        verbose_name=_('Abstimmungstag'),
        help_text='Tag an dem diese Abstimmung stattfindet')
    poll_id = models.PositiveSmallIntegerField(
        verbose_name=_('AbstimmungsID innerhalb des Tages'))
    percent_required = models.DecimalField(
        _('Prozent'),
        help_text=_(
            'Prozent die nötig sind, damit die Abstimmung als angenommen gilt'),
        max_digits=5,
        decimal_places=2,
        default=Decimal('50.00'),
        validators=[MinValueValidator(Decimal('0.00')),
                    MaxValueValidator(Decimal('100.00'))])
    all_votes = models.BooleanField(
        _('Alle Stimmen?'),
        help_text=_(
            'Wenn aktiviert werden ALLE Stimmen gezählt, auch jene die nicht mit abgestimmt haben!'),
        default=False)

    class Meta:
        unique_together = ('voting_day', 'poll_id')


class MedianPoll(GeneralPoll):
    max_value = models.DecimalField(
        _('Abzustimmender Betrag'),
        help_text=_('Betrag welcher beantragt wurde'),
        max_digits=20,
        decimal_places=2)


class SchulzePoll(GeneralPoll):
    pass


class SchulzePollOption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    option = models.CharField(
        _('Option'),
        help_text=_('Die Option für diesen Abstimmungsgegenstand'),
        max_length=250)
    poll = models.ForeignKey(
        SchulzePoll,
        on_delete=models.CASCADE,
        verbose_name=_('Schulze-Abstimmung'),
        help_text=_('Abstimmung, zu der diese Option gehört'))


class MedianVote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    poll = models.ForeignKey(
        MedianPoll,
        on_delete=models.CASCADE,
        verbose_name=_('Abstimmung'),
        help_text='Abstimmung, auf welche sich die Antwort bezieht')
    voter = models.ForeignKey(
        WeightedVoter,
        on_delete=models.CASCADE,
        verbose_name=_('Abstimmende Gruppe'))
    models.DecimalField(
        _('Abgestimmter Betrag'),
        help_text=_('Betrag welchen diese Gruppe abgestimmt hat'),
        max_digits=20,
        decimal_places=2)

    class Meta:
        unique_together = ('poll', 'voter')


class SchulzeVote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    poll_option = models.ForeignKey(
        SchulzePollOption,
        on_delete=models.CASCADE,
        verbose_name=_('Option'),
        help_text='Option auf welch sich diese Antwort bezieht')
    voter = models.ForeignKey(
        WeightedVoter,
        on_delete=models.CASCADE,
        verbose_name=_('Abstimmende Gruppe'))
    rank = models.PositiveSmallIntegerField(
        verbose_name=_('Position im Ranking'))

    class Meta:
        unique_together = ('poll_option', 'voter')
