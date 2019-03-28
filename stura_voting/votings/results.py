# MIT License
#
# Copyright (c) 2018, 2019 Fabian Wenzelmann
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

from collections import OrderedDict
from itertools import groupby
from heapq import merge

from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext as _

from .utils import get_instance
from . import models as voting_models


# TODO in subpackage (stura_voting_utils) specify requirements
# (I know that this is not the right place for this TODO)

def get_median_votes(collection, voter=None, **kwargs):
    collection = get_instance(voting_models.VotingCollection, collection)
    if voter is None:
        return voting_models.MedianVote.objects.filter(voting__group__collection=collection, **kwargs)
    else:
        voter = get_instance(voting_models.Voter, voter)
        return voting_models.MedianVote.objects.filter(voting__group__collection=collection, voter=voter, **kwargs)


def get_schulze_votes(collection, voter=None, **kwargs):
    collection = get_instance(voting_models.VotingCollection, collection)
    if voter is None:
        return voting_models.SchulzeVote.objects.filter(option__voting__group__collection=collection, **kwargs)
    else:
        voter = get_instance(voting_models.Voter, voter)
        return voting_models.SchulzeVote.objects.filter(option__voting__group__collection=collection, voter=voter, **kwargs)


def get_voters_with_vote(collection):
    # returns all voters that casted a vote for any of the votes in the
    # collection
    # returns them by id as a set
    all = get_median_votes(collection).values_list('voter__id', flat=True)
    result = set(all)
    all = get_schulze_votes(collection).values_list('voter__id', flat=True)
    result.update(all)
    return result


def QueryWarning(object):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return str(self.message)


class MedianWarning(object):
    def __init__(self, voting, got):
        self.voting = voting
        self.got = got


    def __str__(self):
        return _('Warning for voting with id %(voting)d: Expected value between 0 and %(max)d but got value %(got)d' % {
            'voting': self.voting.id,
            'max': self.voting.value,
            'got': self.got,
        })


class SchulzeWarning(object):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return str(self.message)


def single_median_vote(voter, voting):
    try:
        res = voting_models.MedianVote.objects.get(voter=voter, voting=voting)
        if res.value > voting.value:
            return res, MedianWarning(voting, res.value)
        return res, None
    except ObjectDoesNotExist:
        return None, None


def single_schulze_vote(voter, voting, voting_options=None):
    if voting_options is None:
        voting_options = voting_models.SchulzeOption.objects.filter(voting=voting).order_by('option_num')
    # get all votes
    votes = voting_models.SchulzeVote.objects.filter(voter=voter, option__voting=voting).order_by('option__option_num')
    # now we must be able to match them, i.e. they must refer to exactly the same
    # option elements
    # it's also possible that simply no votes exist...
    votes = list(votes)
    if not votes:
        return None, None
    # now match
    if len(votes) != len(voting_options):
        msg = _('Number of options %(options)d does not match number of votes %(votes)d for voting %(voting)d' % {
            'options': len(voting_options),
            'votes': len(votes),
            'voting': voting.id,
        })
        return voting_options,votes, SchulzeWarning(msg)
    # check if each option is correctly covered
    for vote, option in zip(votes, voting_options):
        if vote.option != option:
            msg = _('Invalid vote for option for vote %(vote)d: Got vote for option %(option)d instead of %(for)d' % {
                'vote': voting.id,
                'option': vote.option.id,
                'for': option.id,
            })
            return voting_options, votes, SchulzeWarning(msg)
    return voting_options, votes, None


class GenericVotingResult(object):
    def __init__(self):
        # all votings, sorted according to group and then voting_num
        self.votings = OrderedDict()
        # mapping voting_id to actual vote
        self.votes = dict()
        # contains all warnings from fetching the result
        self.warnings = []
        # maps votings -> entry "voting is about"
        # maps to value in median and list of SchulzeOption in schulze
        self.voting_description = dict()

    def by_group(self):
        for group_id, group in groupby(self.votings.values(), lambda voting: voting.group.id):
            yield group_id, list(group)


def merge_voting_results(median, schulze):
    res = GenericVotingResult()
    def key(e):
        _, voting = e
        return voting.group.group_num, voting.voting_num
    merged_list = merge(median.votings.items(), schulze.votings.items(), key=key)
    res.votings = OrderedDict(merged_list)
    if len(res.votings) != len(median.votings) + len(schulze.votings):
        warning = QueryWarning('Something went wrong, ids of the votings are probably not unique or a voting appears twice!')
        res.warnings.append(warning)
    res.votes.update(median.votes)
    res.votes.update(schulze.votes)
    res.warnings += median.warnings
    res.warnings += schulze.warnings
    res.voting_description.update(schulze.voting_description)
    res.voting_description.update(median.voting_description)
    return res


def median_votes_for_voter(collection, voter):
    # could proabably be done in a single more efficient query
    votings_qs = (voting_models.MedianVoting.objects.filter(group__collection=collection)
                 .order_by('group__group_num', 'voting_num'))
    votes_qs = (voting_models.MedianVote.objects
                .select_for_update()
                .filter(voter=voter, voting__group__collection=collection)
                .select_related('voting'))

    res = GenericVotingResult()
    # fetch all median votings
    for voting in votings_qs:
        voting_id = voting.id
        res.votings[voting_id] = voting
        res.voting_description[voting_id] = voting.value

    # fetch all votings for which there exists a vote and perform sanity check
    for vote in votes_qs:
        res.votes[vote.voting.id] = vote
        if vote.value > vote.voting.value:
            warning = MedianWarning(vote.voting, vote.value)
            res.warnings.append(warning)
    return res


def schulze_votes_for_voter(collection, voter):
    # all votings
    votings_qs = (voting_models.SchulzeVoting.objects.filter(group__collection=collection)
                  .order_by('group__group_num', 'voting_num'))
    # all options
    options_qs = (voting_models.SchulzeOption.objects.filter(voting__group__collection=collection)
                  .order_by('voting__id', 'option_num'))
    # all options voted for
    votes_qs = (voting_models.SchulzeVote.objects.filter(voter=voter, option__voting__group__collection=collection)
                .select_for_update()
                .select_related('option')
                .order_by('option__voting__id', 'option__option_num'))
    res = GenericVotingResult()

    # fetch all schulze votings
    for voting in votings_qs:
        res.votings[voting.id] = voting
    # group options according to votings
    for option in options_qs:
        voting_id = option.voting.id
        # just to be sure, should not happen
        if voting_id not in res.votings:
            msg = _('Found option with id %(option)d for voting %(voting)d, but voting does not exist' %{
                'option': option.id,
                'voting': voting_id,
            })
            res.warnings.append(SchulzeWarning(msg))
            continue
        if voting_id in res.voting_description:
            res.voting_description[voting_id].append(option)
        else:
            res.voting_description[voting_id] = [option]
    # do the same for casted votes
    for schulze_vote in votes_qs:
        voting_id = schulze_vote.option.voting.id
        # just to be sure
        if voting_id not in res.votings:
            msg = _('Found a vote with id %(vote)d for schulze option with id %(option)d for voting %(voting)d, but voting does not exist' % {
                'vote': schulze_vote.id,
                'option': schulze_vote.option.id,
                'voting': voting_id,
            })
            res.warnings.append(SchulzeWarning(msg))
            continue
        if voting_id in res.votes:
            res.votes[voting_id].append(schulze_vote)
        else:
            res.votes[voting_id] = [schulze_vote]
    # now perform sanity checks
    for voting_id, votes in res.votes:
        if voting_id not in res.voting_description:
            msg = _('Vote with id %(vote)d has no description' % {'vote': voting_id})
            res.warnings.append(msg)
            continue
        voting_options = res.voting_description[voting_id]
        if len(votes) != len(voting_options):
            msg = _('Number of options %(options)d does not match number of votes %(votes)d for voting %(voting)d' % {
                'options': len(voting_options),
                'votes': len(votes),
                'voting': voting_id,
            })
            res.warnings.append(SchulzeWarning(msg))
            continue
        for vote, option in zip(votes, voting_options):
            msg = _('Invalid vote for option for vote %(vote)d: Got vote for option %(option)d instead of %(for)d' % {
                'vote': voting_id,
                'option': vote.option.id,
                'for': option.id,
            })
            res.warnings.append(SchulzeWarning(msg))
            # no continue here, evaluation works fine but probably something is wrong
    return res
