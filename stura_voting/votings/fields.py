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
from stura_voting_utils.parser import parse_voters, parse_voting_collection, ParseException


class VotersRevisionField(forms.CharField):

    widget = forms.Textarea

    def clean(self, value):
        cleaned = super().clean(value)
        try:
            voters = list(parse_voters(cleaned.split('\n')))
            return voters
        except ParseException as e:
            raise forms.ValidationError("Can't parse voters from field: %s" % str(e))


class VotingCollectionField(forms.CharField):

    widget = forms.Textarea

    def clean(selfself, value):
        cleaned = super().clean(value)
        try:
            return parse_voting_collection(cleaned.split('\n'))
        except ParseException as e:
            raise forms.ValidationError("Can't parse voting collection from field: %s" % str(e))