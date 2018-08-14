from django import forms
from stura_voting_utils.parser import parse_voters, ParseException

class VotersRevisionField(forms.CharField):

    widget = forms.Textarea

    def clean(self, value):
        cleaned = super(VotersRevisionField, self).clean(value)
        try:
            voters = list(parse_voters(cleaned.split('\n')))
            return voters
        except ParseException as e:
            raise forms.ValidationError("Can't parse voters from field: %s" % str(e))
