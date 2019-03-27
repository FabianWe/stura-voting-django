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

from django import forms

from .models import *
from .fields import *
from .utils import get_groups
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
        self.fields['period'].queryset = self.fields['period'].queryset.order_by('-start', '-created')


class SessionForm(forms.ModelForm):
    # TODO sort revision

    collection = VotingCollectionField(required=True, label='Abstimmungen')

    class Meta:
        model = VotingCollection
        fields = ('time', 'revision')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['revision'].queryset = self.fields['revision'].queryset.order_by('-period__start', '-created')

class ResultsSingleVoterForm(forms.Form):
    median_field_prefix = 'extra_median_'
    schulze_field_prefix = 'extra_schulze_'
    label_field_prefix = 'group_label_'

    def __init__(self, *args, **kwargs):
        collection = kwargs.pop('collection')
        voter = kwargs.pop('voter', None)
        last_voter_id = None
        if voter is not None:
            last_voter_id = voter.id
        # filled later, just make sure it exists whatever happens
        self.warnings = []
        #groups = []
        #if collection is not None:
        #    groups = get_groups(collection)
        super().__init__(*args, **kwargs)
        # not so efficient but works
        # What we do is:
        # Find the last user (if it exists) and then take the next user
        # for the next button
        # we store the next value in the variable next_user_id
        # TODO wrong place
        next_voter_id = None
        if last_voter_id is not None:
            voters_qs = Voter.objects.filter(revision=collection.revision).order_by('name')
            voters_list = list(voters_qs)
            # list is sorted according to name, not id, so just search
            for i, voter in enumerate(voters_list):
                if voter.id == last_voter_id:
                    if (i + 1) < len(voters_list):
                        next_voter_id = voters_list[i + 1].id
                    break
        median_result = median_votes_for_voter(collection, voter)
        schulze_result = schulze_votes_for_voter(collection, voter)
        all_results = merge_voting_results(median_result, schulze_result)
        # insert in field order
        # this was a todo but we should be fine, django uses ordered dict
        # TODO what happens when creating it with POST given? Will this here
        # then do something wrong?
        for _, voting_list in all_results.by_group():
            assert len(voting_list) > 0
            group = voting_list[0].group
            group_field_name = self.label_field_prefix + str(group.id)
            self.fields[group_field_name] = forms.CharField(label='',
                                                            initial=str(group.name),
                                                            required=False,
                                                            disabled=True)
            for voting in voting_list:
                voting_id = voting.id
                if isinstance(voting, MedianVoting):
                    field_name = self.median_field_prefix + str(voting_id)
                    currency = voting.currency
                    if not currency:
                        currency = None
                    as_currency = output_currency(voting.value, currency)
                    self.fields[field_name] = CurrencyField(max_value=voting.value,
                                                            label='Finanzantrag: %s (%s)' % (str(voting.name), as_currency),
                                                            required=False)
                    # add initial value (if exists)
                    if voting_id in median_result.votes:
                        result = median_result.votes[voting_id]
                        as_currency = output_currency(result.value, currency)
                        self.fields[field_name].initial = as_currency
                elif isinstance(voting, SchulzeVoting):
                    field_name = self.schulze_field_prefix + str(voting_id)
                    num_options = len(schulze_result.voting_description[voting_id])
                    self.fields[field_name] = SchulzeVoteField(num_options=num_options,
                                                               label='Abstimmung: %s (%d)' % (str(voting.name), num_options),
                                                               required=False)
                    if voting_id in schulze_result.votes:
                        result = schulze_result.votes[voting_id]
                        assert result
                        ranking_str = ' '.join(str(vote.sorting_position) for vote in result)
                        self.fields[field_name].initial = ranking_str
                else:
                    assert False
        self.warnings = all_results.warnings

    def votings(self):
        for name, value in self.cleaned_data.items():
            if name.startswith(self.median_field_prefix):
                voting_id = int(name[len(self.median_field_prefix):])
                yield 'median', voting_id, value
            elif name.startswith(self.schulze_field_prefix):
                voting_id = int(name[len(self.schulze_field_prefix):])
                yield 'schulze', voting_id, value

# TODO remove once new method is there
class EnterResultsForm(forms.Form):

    median_field_prefix = 'extra_median_'
    schulze_field_prefix = 'extra_schulze_'
    label_field_prefix = 'group_label_'

    # I think None is not the best way, but okay
    voter = forms.ModelChoiceField(None)

    voter.widget.attrs.update({'class': 'custom-select', 'size': '7'})

    def __init__(self, *args, **kwargs):
        session = kwargs.pop('session')
        last_voter_id = kwargs.pop('last_voter_id', None)
        groups = []
        if session is not None:
            groups = get_groups(session)
        super().__init__(*args, **kwargs)
        voters_qs = Voter.objects.filter(revision=session.revision).order_by('name')
        self.fields['voter'].queryset = voters_qs
        voters_list = list(voters_qs)
        # not so efficient but works
        # What we do is:
        # Find the last user (if it exists) and then take the next user
        # as the initial value in the select field
        # we store the next value in the variable next_user_id
        next_voter_id = None
        if last_voter_id is None:
            # no last user provided, so use the first one
            if voters_list:
                next_voter_id = voters_list[0].id
        else:
            # list is sorted according to name, not id, so just search
            for i, voter in enumerate(voters_list):
                if voter.id == last_voter_id:
                    if (i + 1) < len(voters_list):
                        next_voter_id = voters_list[i + 1].id
                    break
        if next_voter_id is not None:
            self.fields['voter'].initial = next_voter_id
        # insert in field order
        # this was a todo but we should be fine, django uses ordered dict
        # TODO what happens when creating it with POST given? Will this here
        # then do something wrong?
        for group, voting_list in groups:
            group_field_name = self.label_field_prefix + str(group.id)
            self.fields[group_field_name] = forms.CharField(label='',
                                                            initial=str(group.name),
                                                            required=False,
                                                            disabled=True)
            for voting in voting_list:
                if isinstance(voting, MedianVoting):
                    field_name = self.median_field_prefix + str(voting.id)
                    self.fields[field_name] = CurrencyField(max_value=voting.value,
                                                            label='Finanzantrag: ' + str(voting.name),
                                                            required=False)
                elif isinstance(voting, SchulzeVoting):
                    field_name = self.schulze_field_prefix + str(voting.id)
                    num_options = SchulzeOption.objects.filter(voting=voting).count()
                    self.fields[field_name] = SchulzeVoteField(num_options=num_options,
                                                               label='Abstimmung: ' + str(voting.name),
                                                               required=False)
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

# https://jacobian.org/writing/dynamic-form-generation/
