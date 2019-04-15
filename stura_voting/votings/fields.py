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
from stura_voting_utils.parser import parse_voters, parse_voting_collection, ParseException, parse_currency, _schulze_option_rx
from stura_voting_utils import SchulzeVotingSkeleton

import re

# TODO check maxlength before insertion?


class VotersRevisionField(forms.CharField):
    """A field for a voters revision.

    A voters revision field must have a multiline text content of the form:
    Beginning with *, followed by the name, a colon and the voters weight: "* <NAME>: <WEIGHT>".

    The clean method returns the list of all voters in the form of stura_voting_utils.WeightedVoter.

    """

    widget = forms.Textarea

    def clean(self, value):
        cleaned = super().clean(value)
        try:
            voters = list(parse_voters(cleaned.split('\n')))
            return voters
        except ParseException as e:
            raise forms.ValidationError(
                "Can't parse voters from field: %s" %
                str(e))


class SchulzeOptionsField(forms.CharField):
    """A field for parsing Schulze options.

    A schulze option field must have a multiline text content of the for:
    Beginning with *, followed by the option name: "* <OPTION TEXT>".

    The clean method returns the list of all option strings.
    At least two options must exist, otherwise a ValidationError is raised.

    """

    widget = forms.Textarea

    def clean(self, value):
        cleaned = super().clean(value)
        # kind of hacky, but ok
        options = []
        for line in cleaned.split('\n'):
            line = line.strip()
            if not line:
                continue
            match = _schulze_option_rx.match(line)
            if not match:
                raise forms.ValidationError(
                    "Can't parse option line '%s'" % line)
            o = match.group('option')
            o = o.strip()
            options.append(o)
        if len(options) < 2:
            raise forms.ValidationError('Not enough options for voting')
        return options


class VotingCollectionField(forms.CharField):
    """A field to parse a whole voting collection.

    The content must be a (multilined) description of the voting collection as defined in
    stura_voting_utils.parse_voting_collection. The clean method returns this parsed instance.
    The clean method may raise a ValidationError if the collection can't be parsed (invalid syntax)
    or if a schulze voting has less than two options.

    """

    widget = forms.Textarea

    def clean(self, value):
        cleaned = super().clean(value)
        try:
            collection = parse_voting_collection(cleaned.split('\n'))
            # check if each schulze voting has at least two options
            for group in collection.groups:
                for skel in group.get_votings():
                    if isinstance(skel, SchulzeVotingSkeleton):
                        if len(skel.options) < 2:
                            raise forms.ValidationError(
                                'Not enough options for schulze voting')
            return collection
        except ParseException as e:
            raise forms.ValidationError(
                "Can't parse voting collection from field: %s" %
                str(e))


# TODO test both fields

class CurrencyField(forms.CharField):
    """A field for a currency value.

    The field must be a valid currency according to stura_votings_util.parse_currency.
    For example "100,00 €" would be valid.
    If the field is left empty the clean method returns None if this field is left empty
    (empty string).
    It returns the integer value and currency (as a tuple).
    For example "100,00 €" would return (10000, '€').
    If no currency symbol was provided it returns None instead.

    """

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
            raise forms.ValidationError(
                'Invalid currency: Must be >= 0 and <= max_value (%d)' %
                self.max_value)
        return val, currency


_schulze_vote_rx = re.compile(r'[ /;,]')


class SchulzeVoteField(forms.CharField):
    """A field used for a vote casted for a schulze voting.

    The field must be a list of integers (the sorting positions). Smaller values mean
    "higher ranked". The integers must be separated by a space, "/", ";" or ",".
    The number of integers in the ranking must match the number of options in the voting.
    The clean method returns the ranking as a list of integers.
    A validation error in clean may be raised:
    If one of the entries can't be parsed as an integer, if one of the integers is < 0
    or if the number of integers does not match the number of options in the voting
    (num_options).

    Attributes:
        num_options (int): The number of options in the schulze voting.

    """

    def __init__(self, **kwargs):
        num_options = kwargs.pop('num_options')
        self.num_options = num_options
        super().__init__(**kwargs)

    def clean(self, value):
        cleaned = super().clean(value)
        cleaned = cleaned.strip()
        if not cleaned:
            return None
        split = _schulze_vote_rx.split(cleaned)
        ranking = []
        for s in split:
            s = s.strip()
            if not s:
                continue
            try:
                val = int(s)
                if val < 0:
                    raise forms.ValidationError(
                        'Invalid Schulze vote: Must be a postive integer')
                ranking.append(val)
            except ValueError as e:
                raise forms.ValidationError(
                    'Invalid Schulze vote: Must be list of integers: %s' %
                    str(e))
        if len(ranking) != self.num_options:
            raise forms.ValidationError(
                'Invalid Schulze vote: Does not match number of options in voting')
        return ranking


class GroupOrderField(forms.CharField):
    """A field used to change the order of votings in a group.

    This field works nearly as SchulzeVoteField, but instead of num_options has a
    num_votings attribute that defines the number of votings in a specific group.
    This field is meant to change the order in which votings are sorted in a group.

     In additon the clean method may raise an error if one position appears more than once
     in the order; otherwise works like SchulzeVoteField.

     Attributes:
         num_votings (int): The number of votings in the group.

    """

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
                    raise forms.ValidationError(
                        'Invalid group position: Must be a postive integer')
                order.append(val)
            except ValueError as e:
                raise forms.ValidationError(
                    'Invalid group position: Must be list of integers: %s' %
                    str(e))
        if len(order) != self.num_votings:
            raise forms.ValidationError(
                'Invalid position in group: Does not match number of votings')
        if len(order) != len(set(order)):
            raise forms.ValidationError(
                'Invalid position in group: Positions must be unique')
        return order
