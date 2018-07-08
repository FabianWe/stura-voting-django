from django.db import models

from decimal import Decimal
from django.core.validators import MaxValueValidator, MinValueValidator

# Create your models here.

class Period(models.Model):
    name = models.CharField(max_length=150, help_text='Name of the period, for example "Summer Term 2018"', unique=True)
    # TODO timezone?
    created = models.DateTimeField(auto_now_add=True, help_text='Time when the category was created')
    # TODO default method
    start = models.DateField(blank=True, null=True, help_text='Start of the period (for example start of term)')
    end = models.DateField(blank=True, null=True, help_text='End ofthe period (for example end of term)')


class VotersRevision(models.Model):
    period = models.ForeignKey('Period', on_delete=models.CASCADE, help_text='Period this revision is used in')
    created = models.DateTimeField(auto_now_add=True, help_text='Time when the revision was created')
    note = models.TextField(help_text='Optional note for this revision')


class Voter(models.Model):
    revision = models.ForeignKey('VotersRevision', on_delete=models.CASCADE, help_text='Revision this user is used in')
    name = models.CharField(max_length=150, help_text='Name of the voter / group')
    weight = models.PositiveIntegerField(help_text='Weight of the votes, i.e. how many votes the voter actually casts')

    class Meta:
        unique_together = ('revision', 'name',)


class VotingCollection(models.Model):
    name = models.CharField(max_length=150, help_text='Name of the collection (for example "StuRa-Sitzung vom XX.XX.XXXX")')
    # TODO default
    time = models.DateTimeField(help_text='Time the votings take place')
    revision = models.ForeignKey('VotersRevision', on_delete=models.CASCADE, help_text='Group of voters for this voting')


class VotingGroup(models.Model):
    name = models.CharField(max_length=150, help_text='Name of the group, for example "Financial Votes"')
    collection = models.ForeignKey('VotingCollection', on_delete=models.CASCADE, help_text='Collection this group belongs to')

    class Meta:
        unique_together = ('name', 'collection',)


class MedianVoting(models.Model):
    name = models.CharField(max_length=150, help_text='Name of the voting')
    value = models.PositiveIntegerField(help_text='Value for this voting (for example 2000 (cent))')
    percent_required = models.DecimalField(help_text='Percent of votes required, for example 50 (half of all votes) or 75 (three-quarters)',
        max_digits=4,
        decimal_places=1,
        default=Decimal('50.0'),
        validators=[MinValueValidator(Decimal('0.0')), MaxValueValidator(Decimal('100.0'))])
    group = models.ForeignKey('VotingGroup', on_delete=models.CASCADE, help_text='Group this voting belongs to')

    class Meta:
        unique_together = ('name', 'group',)


class SchulzeVoting(models.Model):
    name = models.CharField(max_length=150, help_text='Name of the voting')
    percent_required = models.DecimalField(help_text='Percent of votes required, for example 50 (half of all votes) or 75 (three-quarters)',
        max_digits=4,
        decimal_places=1,
        default=Decimal('50.0'),
        validators=[MinValueValidator(Decimal('0.0')), MaxValueValidator(Decimal('100.0'))])
    group = models.ForeignKey('VotingGroup', on_delete=models.CASCADE, help_text='Group this voting belongs to')

    class Meta:
        # TODO we should enforce name and group to be unique in median and schulze
        unique_together = ('name', 'group',)


class SchulzeOption(models.Model):
    option = models.CharField(max_length=150, help_text='Option text')
    voting = models.ForeignKey('SchulzeVoting', on_delete=models.CASCADE, help_text='Voting this option belongs to')

    class Meta:
        unique_together = ('option', 'voting',)


class MedianVote(models.Model):
    value = models.PositiveIntegerField('Value the voter voted for')
    # TODO we should enforce that the voter here is allowed to vote here, but checking
    # this on the DB level is really annoying
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
