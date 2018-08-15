from django import forms

from .models import Period, VotersRevision, VotingCollection
from .fields import VotersRevisionField

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
        super(RevisionForm, self).__init__(*args, **kwargs)
        self.fields['period'].queryset = self.fields['period'].queryset.order_by('-start', '-created')


class SessionForm(forms.ModelForm):

    # TODO add votings block

    class Meta:
        model = VotingCollection
        fields = ('name', 'time', 'revision')