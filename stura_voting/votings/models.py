# Copyright 2018 - 2019 Fabian Wenzelmann
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from django.db import models

from django.utils import timezone
from django.utils.translation import gettext_lazy

from .utils import *

# TODO change display names

FIFTY_MAJORITY = '50'
TWO_THIRDS_MAJORITY = '2/3'

MAJORiTY_CHOICES = (
    (FIFTY_MAJORITY, gettext_lazy('50%')),
    (TWO_THIRDS_MAJORITY, gettext_lazy('2/3 majority')),
)


class Period(models.Model):
    """A Period is a timespan in which sessions take place.

    A model has a name (for example Summer Term 2018) and a start and end date.

    Attributes:
        name (models.CharField): The name of the period.
        created (models.DateTimeField): The time the database object was created,
            defaults to now.
        start (models.DateField): The time the period begins.
        end (models.DateField): The time the period ends.

    """
    name = models.CharField(
        max_length=150,
        help_text=gettext_lazy('Name of the Period, e.g. "Summer Term 2019"'),
        unique=True,
        default=get_semester_name)
    created = models.DateTimeField(
        help_text=gettext_lazy('Time of creation'),
        default=timezone.now)
    start = models.DateField(
        blank=True,
        null=True,
        help_text=gettext_lazy('Start date of the period'),
        default=get_semester_start)
    end = models.DateField(
        blank=True,
        null=True,
        help_text=gettext_lazy('End date of the period'),
        default=get_semester_end)

    def __str__(self):
        return str(self.name)


class VotersRevision(models.Model):
    """A revision is a collection of different voters.

    It is associated with the period in which it belongs.

    Attributes:
        period (Period): The period to which this revision belongs.
        created (models.DateTimeField): The time the database object was created,
            defaults to now.
        note (models.TextField): An optional note describing for example why this revision was created.

    """
    period = models.ForeignKey(
        'Period',
        on_delete=models.CASCADE,
        help_text=gettext_lazy('Period this revision belongs to'))
    created = models.DateTimeField(
        help_text=gettext_lazy('Time of creation'),
        default=timezone.now)
    note = models.TextField(help_text=gettext_lazy('Optional note'), blank=True)

    def __str__(self):
        created_format = formats.date_format(self.created, 'DATETIME_FORMAT')
        period = str(self.period)
        return 'Revision vom %s für %s' % (created_format, period)


class Voter(models.Model):
    """A voter that exists in a revision.

    A voter belongs in a certain revision and has a name (string) and weight (positive int).

    Attributes:
        revision (VotersRevision): The revision this voter belongs to.
        name (models.CharField): The name of the group or person.
        weight (models.PositiveIntegerField): The weight of the voter, i.e. how many votes the voter actually casts.

    """
    revision = models.ForeignKey(
        'VotersRevision',
        on_delete=models.CASCADE,
        help_text=gettext_lazy('Revision this user is used in'))
    name = models.CharField(max_length=150,
                            help_text=gettext_lazy('Name of the voter / group'))
    weight = models.PositiveIntegerField(
        help_text=gettext_lazy('Weight of the votes, i.e. how many votes the voter actually casts'))

    def __str__(self):
        return str(self.name)

    class Meta:
        unique_together = ('revision', 'name',)


class VotingCollection(models.Model):
    """A collection of different votings, created with a certain revision (identifying the valid voters).

    A collection (or session) is just a collection of different polls / votings.
    It has a name (e.g. "Meeting on April 18, 2019)", a time when the session takes place and an associated revision.

    Attributes:
        name (models.CharField): The name of the session / collection.
        time (models.DateTimeField): The time when the session takes place.
        revision (VotersRevision): The revision identifying the voters for this session.

    """
    name = models.CharField(
        max_length=150,
        help_text=gettext_lazy('Name of the collection (e.g. "Meeting on XXX")'),
        default=get_next_session_name_stura)
    time = models.DateTimeField(help_text=gettext_lazy('Time the session takes place'),
                                default=get_next_session_stura)
    revision = models.ForeignKey(
        'VotersRevision',
        on_delete=models.CASCADE,
        help_text=gettext_lazy('Group of voters for this session'))

    class Meta:
        permissions = (
            ("view_collection_results",
             "Can view results of a collection"),
            ("enter_collection_results",
             "Can enter results for all who are entitled to vote"),
        )


class VotingGroup(models.Model):
    """A group of votings in a session.

    Each session has different groups in which the actual polls exist.

    Such a group could for example be "Financial Polls" or "Elections for the board of directors".

    Attributes:
        name (models.CharField): The name of the group.
        collection (VotingCollection): The collection in which this group exists.
        group_num (models.PositiveIntegerField): A unique number for each group describing the order in which groups
            are sorted in the session.

    """
    name = models.CharField(
        max_length=150,
        help_text=gettext_lazy('Name of the group, for example "Financial Votes"'))
    collection = models.ForeignKey(
        'VotingCollection',
        on_delete=models.CASCADE,
        help_text=gettext_lazy('Collection this group belongs to'))
    group_num = models.PositiveIntegerField(help_text=gettext_lazy('Order of the group in the session'))

    class Meta:
        unique_together = (('name', 'collection',),
                           ('group_num', 'collection'),)


class MedianVoting(models.Model):
    """A median voting, i.e. a voting of integers in which the first one with a majority wins.

    A single median poll. It belongs in a certain group.
    The poll has a name (for example "Money for party") and the value in question.
    The value is stored in "cent" (whatever this means given a specific currency). That is plain integer values.
    They're parsed in the format "21.00" (meaning 2100 cent) or "42,00" (meaning 4200 cents).
    The currency is used only for displaying purposes.
    As the groups are sorted according to an ordering inside a session the polls in a group are sorted accorded to
    a voting num. This field must be unique, also including schulze polls (though this is not checked on a database
    level).

    Attributes:
        name (models.CharField): Name of the poll.
        value (models.PositiveIntegerField): The value of this poll, always meassured in cents.
        majority (models.CharField): The majority required, at the moment 50% or 2/3. Valid choices are in
            MAJORiTY_CHOICES.
        absolute_majority (models.BooleanField): If true all votes should be counted for the majority, not just the
            votes casted. All voters without a vote should be inserted as a vote for 0 cent.
        currency (models.CharField): The currency to display, only used for displaying. E.g. 4200 with currency "€" is
            displayed as "42,00 €".
        group (VotingGroup): The group to which this poll belongs to.
        voting_num (models.PositiveIntegerField): The sorting position inside the group, must be unique for that group.

    """
    name = models.CharField(max_length=150, help_text=gettext_lazy('Name of the poll'))
    value = models.PositiveIntegerField(
        help_text=gettext_lazy('Value for this voting (for example 2000 (cent). Always meassured in cents, pence etc.)'))
    majority = models.CharField(
        max_length=10,
        help_text=gettext_lazy('Required majority for voting'),
        choices=MAJORiTY_CHOICES,
        default=FIFTY_MAJORITY)
    absolute_majority = models.BooleanField(
        help_text=gettext_lazy('Set to true if all voters should be considerd, even those who did not cast a vote. Thes voters will be treated as if they voted for 0€'),
        default=False)
    currency = models.CharField(
        max_length=10,
        blank=True,
        help_text=gettext_lazy('Currency of the vote, for example "$" or "€". For example value=100 and currency=€ means 1,00€.'),
        default='€')
    group = models.ForeignKey(
        'VotingGroup',
        on_delete=models.CASCADE,
        help_text=gettext_lazy('Group this voting belongs to'))
    voting_num = models.PositiveIntegerField(
        help_text=gettext_lazy('Order position inside the group'))


class SchulzeVoting(models.Model):
    """A schulze voting.

    A single schulze poll. It belongs in a certain group.
    The poll has a name (for example "Election of XXX").
    The options are given by SchulzeOption objects referencing this poll.
    As the groups are sorted according to an ordering inside a session the polls in a group are sorted accorded to
    a voting num. This field must be unique, also including median polls (though this is not checked on a database
    level).

    Attributes:
        name (models.CharField): Name of the poll.
        majority (models.CharField): The majority required, at the moment 50% or 2/3. Valid choices are in
            MAJORiTY_CHOICES.
        absolute_majority (models.BooleanField): If true all votes should be counted for the majority, not just the
            votes casted.
        group (VotingGroup): The group to which this poll belongs to.
        voting_num (models.PositiveIntegerField): The sorting position inside the group, must be unique for that group.

    """
    name = models.CharField(max_length=150, help_text=gettext_lazy('Name of the poll'))
    majority = models.CharField(
        max_length=10,
        help_text=gettext_lazy('Required majority for voting'),
        choices=MAJORiTY_CHOICES,
        default=FIFTY_MAJORITY)
    absolute_majority = models.BooleanField(
        help_text=gettext_lazy('Set to true if all voters should be considerd, even those who did not cast a vote. Thes voters will be treated as if they voted for no (which is considered to be the last option)'),
        default=False)
    group = models.ForeignKey(
        'VotingGroup',
        on_delete=models.CASCADE,
        help_text=gettext_lazy('Group this voting belongs to'))
    voting_num = models.PositiveIntegerField(
        help_text=gettext_lazy('Order position inside the group'))


class SchulzeOption(models.Model):
    """A single option for a schulze poll.

    An option references the poll it belongs to and has a string describing the option.
    Options are sorted according to an option num.

    Attributes:
        option (models.CharField): The option as a string.

    """
    option = models.CharField(max_length=150, help_text=gettext_lazy('Option text'))
    voting = models.ForeignKey(
        'SchulzeVoting',
        on_delete=models.CASCADE,
        help_text=gettext_lazy('Poll this option belongs to'))
    option_num = models.PositiveIntegerField(
        help_text=gettext_lazy('Order position inside the poll'))

    class Meta:
        unique_together = (('option', 'voting',), ('voting', 'option_num'))


class MedianVote(models.Model):
    """A vote for a median voting.

    The vote consists of the value voted for and the voter that voted for this
    It is not checked on a database level if voter.revision == voting.group.collection.revision, even though only this
    would make sense.
    It is also not checked (on database level) if value <= voting.value.

    Attributes:
        value (models.PositiveIntegerField): Value the voter voted for.
        voter (Voter): The voter that cast the vote.
        voting (MedianVoting): The poll in question.

    """
    value = models.PositiveIntegerField(help_text=gettext_lazy('Value the voter voted for'))
    voter = models.ForeignKey(
        'Voter',
        on_delete=models.CASCADE,
        help_text=gettext_lazy('The voter of this vote'))
    voting = models.ForeignKey(
        'MedianVoting',
        on_delete=models.CASCADE,
        help_text=gettext_lazy('The poll in question'))

    class Meta:
        unique_together = ('voter', 'voting',)


class SchulzeVote(models.Model):
    """A vote for a schulze voting.

    For a given schulze poll and a voter there must exist one one vote entry for all its options.
    That is Each vote is associated with an option and the ranking position is stored in the vote for that option.
    So if you have two options "A" and "B" for a voter there must be two entries, one for "A" and one for "B".
    This is however not checked on a database level. As in a median poll the revision of the voting and the voter
    are not checked on a database level.

    Attributes:
        sorting_position (models.IntegerField): The sorting position, the lower the number the higher ranked.
            The same positions means "indifferent between two options".
        voter (Voter): The voter that cast the vote.
        option (SchulzeOption): The option this entry is for. There must be one entry for each option for a given voter.

    """
    sorting_position = models.IntegerField(
        help_text=gettext_lazy('Position in the voting (the smaller the higher the option was voted)'))
    voter = models.ForeignKey(
        'Voter',
        on_delete=models.CASCADE,
        help_text=gettext_lazy('The voter of this vote'))
    option = models.ForeignKey(
        'SchulzeOption',
        on_delete=models.CASCADE,
        help_text=gettext_lazy('The option this entry is created for'))

    class Meta:
        unique_together = ('voter', 'option',)
