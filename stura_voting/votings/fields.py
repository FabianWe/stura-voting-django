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
from stura_voting_utils.parser import parse_voters, parse_voting_collection, ParseException, parse_currency

import re

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

    def clean(self, value):
        cleaned = super().clean(value)
        try:
            return parse_voting_collection(cleaned.split('\n'))
        except ParseException as e:
            raise forms.ValidationError("Can't parse voting collection from field: %s" % str(e))


# TODO test both fields

class CurrencyField(forms.CharField):

    def __init__(self, **kwargs):
        self.max_value = kwargs.pop('max_value')
        super().__init__(**kwargs)

    def clean(self, value):
        cleaned = super().clean(value).strip()
        try:
            val, currency = parse_currency(cleaned)
        except ParseException as e:
            raise forms.ValidationError('No valid currency: %s' % str(e))
        if val < 0 or val > self.max_value:
            raise forms.ValidationError('Invalid currency: Must be >= 0 and <= max_value (%d)' % self.max_value)
        return val, currency


_schulze_option_rx = re.compile(r'[ /;,]')


class SchulzeVoteField(forms.CharField):

    def __init__(self, **kwargs):
        num_options = kwargs.pop('num_options')
        self.num_options = num_options
        super().__init__(**kwargs)


    def clean(self, value):
        cleaned = super().clean(value)
        cleaned = cleaned.strip()
        if not cleaned:
            raise forms.ValidationError('Invalid Schulze option')
        split = _schulze_option_rx.split(cleaned)
        ranking = []
        for s in split:
            s = s.strip()
            if not s:
                continue
            try:
                val = int(s)
                if val < 0:
                    raise forms.ValidationError('Invalid Schulze vote: Must be a postive integer')
                ranking.append(val)
            except ValueError as e:
                raise forms.ValidationError('Invalid Schulze vote: Must be list of integers: %s' % str(e))
        if len(ranking) != self.num_options:
            raise forms.ValidationError('Invalid Schulze vote: Does not match number of options in voting')
