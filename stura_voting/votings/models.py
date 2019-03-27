# MIT License
#
# Copyright (c) 2018 Fabian Wenzelmann
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from django.db import models

from decimal import Decimal
from django.core.validators import MaxValueValidator, MinValueValidator

from django.utils import timezone

from .utils import *

# TODO change display names


class Period(models.Model):
    name = models.CharField(max_length=150, help_text='Name der Abstimmungsperiode, z.B. "Sommersemester 2018"', unique=True, default=get_semester_name)
    created = models.DateTimeField(help_text='Erstellungszeitpunkt', default=timezone.now)
    start = models.DateField(blank=True, null=True, help_text='Start der Periode', default=get_semester_start)
    end = models.DateField(blank=True, null=True, help_text='Ende der Periode', default=get_semester_end)

    def __str__(self):
        return str(self.name)


class VotersRevision(models.Model):
    period = models.ForeignKey('Period', on_delete=models.CASCADE, help_text='Periode für diese Revision')
    created = models.DateTimeField(help_text='Erstellungszeitpunkt', default=timezone.now)
    note = models.TextField(help_text='Optinale Notiz', blank=True)

    def __str__(self):
        created_format = formats.date_format(self.created, 'DATETIME_FORMAT')
        period = str(self.period)
        return 'Revision vom %s für %s' % (created_format, period)


class Voter(models.Model):
    revision = models.ForeignKey('VotersRevision', on_delete=models.CASCADE, help_text='Revision this user is used in')
    name = models.CharField(max_length=150, help_text='Name of the voter / group')
    weight = models.PositiveIntegerField(help_text='Weight of the votes, i.e. how many votes the voter actually casts')

    def __str__(self):
        return str(self.name)

    class Meta:
        unique_together = ('revision', 'name',)


class VotingCollection(models.Model):
    # TODO test default methods
    name = models.CharField(max_length=150,
                            help_text='Name of the collection (for example "StuRa-Sitzung vom XX.XX.XXXX")',
                            default=get_next_session_name_stura)
    time = models.DateTimeField(help_text='Time the votings take place',
                                default=get_next_session_stura)
    revision = models.ForeignKey('VotersRevision', on_delete=models.CASCADE, help_text='Group of voters for this voting')


class VotingGroup(models.Model):
    name = models.CharField(max_length=150, help_text='Name of the group, for example "Financial Votes"')
    collection = models.ForeignKey('VotingCollection', on_delete=models.CASCADE, help_text='Collection this group belongs to')
    group_num = models.PositiveIntegerField(help_text='Gruppen Nummer')

    class Meta:
        unique_together = ('name', 'collection',)


class MedianVoting(models.Model):
    name = models.CharField(max_length=150, help_text='Name of the voting')
    value = models.PositiveIntegerField(help_text='Value for this voting (for example 2000 (cent). Always meassured in cents, pence etc.)')
    percent_required = models.DecimalField(help_text='Percent of votes required, for example 50 (half of all votes) or 75 (three-quarters)',
        max_digits=4,
        decimal_places=1,
        default=Decimal('50.0'),
        validators=[MinValueValidator(Decimal('0.0')), MaxValueValidator(Decimal('100.0'))])
    count_all_votes = models.BooleanField(help_text='Set to true if all voters should be considerd, even those who did not cast a vote. Thes voters will be treated as if they voted for 0€', default=False)
    currency = models.CharField(max_length=10, blank=True, help_text='Currency of the vote, for example "$" or "€". For example value=100 and currency=€ means 1,00€.')
    group = models.ForeignKey('VotingGroup', on_delete=models.CASCADE, help_text='Group this voting belongs to')
    voting_num = models.PositiveIntegerField(help_text='Abstimmungsnummer innerhalb der Gruppe')


class SchulzeVoting(models.Model):
    name = models.CharField(max_length=150, help_text='Name of the voting')
    percent_required = models.DecimalField(help_text='Percent of votes required, for example 50 (half of all votes) or 75 (three-quarters)',
        max_digits=4,
        decimal_places=1,
        default=Decimal('50.0'),
        validators=[MinValueValidator(Decimal('0.0')), MaxValueValidator(Decimal('100.0'))])
    count_all_votes = models.BooleanField(help_text='Set to true if all voters should be considerd, even those who did not cast a vote. Thes voters will be treated as if they voted for no (which is considered to be the last option)', default=False)
    group = models.ForeignKey('VotingGroup', on_delete=models.CASCADE, help_text='Group this voting belongs to')
    voting_num = models.PositiveIntegerField(help_text='Abstimmungsnummer innerhalb der Gruppe')


class SchulzeOption(models.Model):
    option = models.CharField(max_length=150, help_text='Option text')
    voting = models.ForeignKey('SchulzeVoting', on_delete=models.CASCADE, help_text='Voting this option belongs to')
    option_num = models.PositiveIntegerField(help_text='Optionsnummer innerhalb der Schulze Abstimmung')

    class Meta:
        unique_together = (('option', 'voting',), ('voting', 'option_num'))


class MedianVote(models.Model):
    value = models.PositiveIntegerField('Value the voter voted for')
    voter = models.ForeignKey('Voter', on_delete=models.CASCADE, help_text='The voter of this vote')
    voting = models.ForeignKey('MedianVoting', on_delete=models.CASCADE, help_text='The voting in question')

    class Meta:
        unique_together = ('voter', 'voting',)


class SchulzeVote(models.Model):
    sorting_position = models.IntegerField(help_text='Position in the voting (the smaller the higher the option was voted)')
    voter = models.ForeignKey('Voter', on_delete=models.CASCADE, help_text='The voter of this vote')
    option = models.ForeignKey('SchulzeOption', on_delete=models.CASCADE, help_text='The option this entry is created for')

    class Meta:
        unique_together = ('voter', 'option',)
