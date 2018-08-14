from django import forms

from .models import Period
from .fields import VotersRevisionField

class PeriodForm(forms.ModelForm):

    revision_text = VotersRevisionField(required=False)

    class Meta:
        model = Period
        fields = ('name', 'start', 'end')
