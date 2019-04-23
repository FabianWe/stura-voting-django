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

from django import forms

from .models import *
from .fields import *
from .results import *

from stura_voting_utils.utils import output_currency


class PeriodForm(forms.ModelForm):
    """A form to add a new voting period.

    The name, start and end are displayed in the form.
    In addition a VotersRevisionField is used to directly create a revision for
    this period.

    The revision is not created in the form but in the views using the form.

    Attributes:
        revision (VotersRevisionField): Field to create a revision for the period, optional.

    """

    revision = VotersRevisionField(required=False)

    class Meta:
        model = Period
        fields = ('name', 'start', 'end')


class RevisionForm(forms.ModelForm):
    """A form used to add a revision.

    The period and note of the revision are displayed in the form.
    The voters are parsed in a VotersRevisionField.

    The revision / voters are not created in the form but in the views using the form.

    Attributes:
        voters (VotersRevisionField): Field for the voters, required.

    """

    voters = VotersRevisionField(required=True)

    class Meta:
        model = VotersRevision
        fields = ('period', 'note')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['period'].queryset = self.fields['period'].queryset.order_by(
            '-start', '-created')


class SessionForm(forms.ModelForm):
    """A form used to add a session / VotingCollection.

    The time and revision are displayed in the form.
    The revisions (for display) get sorted accordingly.

    The groups / votings are not created in the form but in the views using the form.

    Attributes:
        collection (VotingCollectionField): Field to parse the votings, required.

    """

    collection = VotingCollectionField(required=True, label='Abstimmungen')

    class Meta:
        model = VotingCollection
        fields = ('time', 'revision')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['revision'].queryset = self.fields['revision'].queryset.order_by(
            '-period__start', '-created')


class RevisionUpdateForm(forms.Form):
    """A form used to update a revision.

    Only the voters can be changed in this form.
    The init method expects an keyword argument "voters" that must be a list of
    voter instances (models.Voter, but stura_voting_utils.WeightedVoter should work as well).

    Voters are not changed in the form but in the views using the form.

    Attributes:
        voters (VotersRevisionField): The voters to update / delete / insert, required.

    """
    voters = VotersRevisionField(required=True)

    def __init__(self, *args, **kwargs):
        voters = kwargs.pop('voters')
        super().__init__(*args, **kwargs)
        voters_text = '\n'.join('* %s: %d' %
                                (voter.name, voter.weight) for voter in voters)
        self.fields['voters'].initial = voters_text


class DynamicVotingsListForm(forms.Form):
    """Base class for forms that dynamically add new fields for all votings.

    This form just introduces three prefixes median_field_prefix, schulze_field_prefix
    and label_field_prefix. These prefixes are the names for the dynamic fields (the
    voting id is appended).

    """
    median_field_prefix = 'extra_median_'
    schulze_field_prefix = 'extra_schulze_'
    label_field_prefix = 'group_label_'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


# TODO check form: Are warnings displayed if POSTed?
class ResultsSingleVoterForm(DynamicVotingsListForm):
    """A form for adding the votes of a single voter into a session / VotingCollection.

    The init method expects the keyword arguments "collection" and "voter".
    "collection" must be a models.VotingCollection and voter a models.Voter instance.
    It dynamically creates new fields for all votings.
    The votings are created with the functions median_votes_for_voter and schulze_votes_for_voter.

    It adds fields with the prefixes as defined in DynamicVotingsListForm and sets the
    initial value if a vote already exists.
    The added fields are of type CurrencyField for median and SchulzeVoteField for schulze votings.

    Attributes:
        results (CombinedVotingResult): The combined median and schulze votings.
        median_result (GenericVotingResult): The median votings and results.
        schulze_result (GenericVotingResult): The schulze votings and results.
    """

    def __init__(self, *args, **kwargs):
        collection = kwargs.pop('collection')
        voter = kwargs.pop('voter')
        super().__init__(*args, **kwargs)
        # TODO add check according to same revision and so on?
        median_result = median_votes_for_voter(collection, voter)
        schulze_result = schulze_votes_for_voter(collection, voter)
        all_results = CombinedVotingResult(median_result, schulze_result)
        self.results = all_results
        self.median_result = median_result
        self.schulze_result = schulze_result
        for group, voting_list in all_results.by_group():
            group_field_name = self.label_field_prefix + str(group.id)
            self.fields[group_field_name] = forms.CharField(
                label='', initial=str(group.name), required=False, disabled=True)
            for voting in voting_list:
                voting_id = voting.id
                if isinstance(voting, MedianVoting):
                    field_name = self.median_field_prefix + str(voting_id)
                    currency = voting.currency
                    if not currency:
                        currency = None
                    as_currency = output_currency(voting.value, currency)
                    self.fields[field_name] = CurrencyField(
                        max_value=voting.value,
                        label='Finanzantrag: %s (%s)' %
                        (str(
                            voting.name),
                            as_currency),
                        required=False)
                    # add initial value (if exists)
                    if voting_id in median_result.votes:
                        result = median_result.votes[voting_id]
                        as_currency = output_currency(result.value, currency)
                        self.fields[field_name].initial = as_currency
                elif isinstance(voting, SchulzeVoting):
                    field_name = self.schulze_field_prefix + str(voting_id)
                    num_options = len(
                        schulze_result.voting_description[voting_id])
                    self.fields[field_name] = SchulzeVoteField(
                        num_options=num_options,
                        label='Abstimmung: %s (%d)' %
                        (str(
                            voting.name),
                            num_options),
                        required=False)
                    if voting_id in schulze_result.votes:
                        result = schulze_result.votes[voting_id]
                        assert result
                        ranking_str = ' '.join(
                            str(vote.sorting_position) for vote in result)
                        self.fields[field_name].initial = ranking_str
                else:
                    assert False

    def votings(self):
        for name, value in self.cleaned_data.items():
            if name.startswith(self.median_field_prefix):
                voting_id = int(name[len(self.median_field_prefix):])
                yield 'median', voting_id, value
            elif name.startswith(self.schulze_field_prefix):
                voting_id = int(name[len(self.schulze_field_prefix):])
                yield 'schulze', voting_id, value


class NewGroupForm(forms.Form):
    name = forms.CharField(required=True,
                           max_length=VotingGroup._meta.get_field('name').max_length)

class UpdateGroupForm(forms.Form):
    """A form used to change the order of votings in a group.

    The only field is a GroupOrderField used to order the votings in the group.
    The init method expects either the keyword argument "num_votings" (the number of
    entries expected in the order field) or "current_order". In this case current_order
    must be a list of n distinct integers with len(current_order) = the number of votings
    in the group.
    If current_order is given this order is used as the initial value in the form.

    Attributes:
        order (GroupOrderField): Field to enter the order in the group.

    """
    order = GroupOrderField(
        num_votings=-1,
        label='Anordnung: Positionsnummer für jede Abstimmung (muss eindeutig sein)',
        required=False)

    def __init__(self, *args, **kwargs):
        num_votings = None
        current_order = None
        if 'num_votings' in kwargs:
            num_votings = kwargs.pop('num_votings')
        elif 'current_order' in kwargs:
            current_order = kwargs.pop('current_order')
            num_votings = len(current_order)
        else:
            raise ValueError('Requires num_votings or current_order')
        super().__init__(*args, **kwargs)
        self.fields['order'].num_votings = num_votings
        if current_order is not None:
            self.fields['order'].initial = ' '.join(map(str, current_order))


class SchulzeVotingCreateForm(forms.ModelForm):
    """Form to add a schulze voting.

    Name, majority and absolute_majority can be configured, the options are parsed
    from a SchulzeOptionsField field.

    Attributes:
        options (SchulzeOptionsField): The options for the voting, required.

    """

    options = SchulzeOptionsField(required=True)

    class Meta:
        model = SchulzeVoting
        fields = ('name', 'majority', 'absolute_majority')

# https://jacobian.org/writing/dynamic-form-generation/
