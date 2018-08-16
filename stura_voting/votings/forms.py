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

    collection = VotingCollectionField(required=True)

    class Meta:
        model = VotingCollection
        fields = ('time', 'revision')


class EnterResultsForm(forms.Form):
    # TODO add some fields for groups as well?

    median_field_prefix = 'extra_median_'
    schulze_field_prefix = 'extra_schulze_'
    label_field_prefix = 'group_label_'

    def __init__(self, *args, **kwargs):
        groups = kwargs.pop('groups', [])
        super().__init__(*args, **kwargs)
        # TODO insert in field order
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
                yield voting_id, value
            elif name.startswith(self.schulze_field_prefix):
                voting_id = int(name[len(self.schulze_field_prefix):])
                yield voting_id, value


# TODO aufpassen mit update und erzeugen
# https://jacobian.org/writing/dynamic-form-generation/