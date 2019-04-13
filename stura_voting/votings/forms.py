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

    revision = VotersRevisionField(required=False)

    class Meta:
        model = Period
        fields = ('name', 'start', 'end')


class RevisionForm(forms.ModelForm):

    voters = VotersRevisionField(required=True)

    class Meta:
        model = VotersRevision
        fields = ('period', 'note')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['period'].queryset = self.fields['period'].queryset.order_by(
            '-start', '-created')


class SessionForm(forms.ModelForm):
    # TODO sort revision

    collection = VotingCollectionField(required=True, label='Abstimmungen')

    class Meta:
        model = VotingCollection
        fields = ('time', 'revision')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['revision'].queryset = self.fields['revision'].queryset.order_by(
            '-period__start', '-created')


class RevisionUpdateForm(forms.Form):
    voters = VotersRevisionField(required=True)

    def __init__(self, *args, **kwargs):
        voters = kwargs.pop('voters')
        super().__init__(*args, **kwargs)
        voters_text = '\n'.join('* %s: %d' %
                                (voter.name, voter.weight) for voter in voters)
        self.fields['voters'].initial = voters_text


class DynamicVotingsListForm(forms.Form):
    median_field_prefix = 'extra_median_'
    schulze_field_prefix = 'extra_schulze_'
    label_field_prefix = 'group_label_'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class ResultsSingleVoterForm(DynamicVotingsListForm):
    median_field_prefix = 'extra_median_'
    schulze_field_prefix = 'extra_schulze_'
    label_field_prefix = 'group_label_'

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


class UpdateGroupForm(forms.Form):
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

    options = SchulzeOptionsField(required=True)

    class Meta:
        model = SchulzeVoting
        fields = ('name', 'majority', 'absolute_majority')

# https://jacobian.org/writing/dynamic-form-generation/
