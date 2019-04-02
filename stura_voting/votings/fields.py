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
        if not cleaned:
            return None
        try:
            # Does not raise ParseException? should be changed?
            parsed = parse_currency(cleaned)
            if parsed is None:
                raise forms.ValidationError('No valid currency')
            val, currency = parsed
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
            return None
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
        return ranking

class GroupOrderField(forms.CharField):
    def __init__(self, **kwargs):
        num_votings = kwargs.pop('num_votings')
        self.num_votings = num_votings
        super().__init__(**kwargs)

    def clean(self, value):
        cleaned = super().clean(value)
        cleaned = cleaned.strip()
        if not cleaned:
            return cleaned
        split = cleaned.split(' ')
        order = []
        for s in split:
            s = s.strip()
            if not s:
                continue
            try:
                val = int(s)
                if val < 0:
                    raise forms.ValidationError('Invalid group position: Must be a postive integer')
                order.append(val)
            except ValueError as e:
                raise forms.ValidationError('Invalid group position: Must be list of integers: %s' % str(e))
        if len(order) != self.num_votings:
            raise forms.ValidationError('Invalid group position: Does not match number of votings')
        if len(order) != len(set(order)):
            raise forms.ValidationError('Invalid group position: Positions must be unique')
        return order
