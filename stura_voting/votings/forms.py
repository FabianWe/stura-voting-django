from django import forms

from .models import Period, VotersRevision
from .fields import VotersRevisionField

class PeriodForm(forms.ModelForm):

    revision = VotersRevisionField(required=False)

    class Meta:
        model = Period
        fields = ('name', 'start', 'end')


class RevisionForm(forms.ModelForm):

    class Meta:
        model = VotersRevision
        fields = ('period', 'note')

    def __init__(self, *args, **kwargs):
        super(RevisionForm, self).__init__(*args, **kwargs)
        self.fields['period'].queryset = self.fields['period'].queryset.order_by('created')