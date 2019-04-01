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

from collections import OrderedDict
from itertools import groupby
from heapq import merge

from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext

from . import utils
from . import models as voting_models


# TODO in subpackage (stura_voting_utils) specify requirements
# (I know that this is not the right place for this TODO)

def get_median_votes(collection, voter=None, **kwargs):
    collection = utils.get_instance(voting_models.VotingCollection, collection)
    if voter is None:
        return voting_models.MedianVote.objects.filter(voting__group__collection=collection, **kwargs)
    else:
        voter = utils.get_instance(voting_models.Voter, voter)
        return voting_models.MedianVote.objects.filter(voting__group__collection=collection, voter=voter, **kwargs)


def get_schulze_votes(collection, voter=None, **kwargs):
    collection = utils.get_instance(voting_models.VotingCollection, collection)
    if voter is None:
        return voting_models.SchulzeVote.objects.filter(option__voting__group__collection=collection, **kwargs)
    else:
        voter = utils.get_instance(voting_models.Voter, voter)
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
        return gettext('Warning for voting with id %(voting)d: Expected value between 0 and %(max)d but got value %(got)d' % {
            'voting': self.voting.id,
            'max': self.voting.value,
            'got': self.got,
        })


class SchulzeWarning(object):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return str(self.message)


class GenericVotingResult(object):

    median_prefix = 'median_'
    schulze_prefix = 'schulze_'

    @staticmethod
    def median_key(id):
        return GenericVotingResult.median_prefix + str(id)


    @staticmethod
    def schulze_key(id):
        return GenericVotingResult.schulze_prefix + str(id)


    @staticmethod
    def parse_median_key(s):
        return int(s[len(GenericVotingResult.median_prefix):])


    @staticmethod
    def parse_schulze_key(s):
        return int(s[len(GenericVotingResult.schulze_prefix):])


    @staticmethod
    def parse_key(s):
        if s.startswith(GenericVotingResult.median_prefix):
            return 'median', GenericVotingResult.parse_median_key(s)
        elif s.startswith(GenericVotingResult.schulze_prefix):
            return 'schulze', GenericVotingResult.parse_schulze_key(s)
        else:
            return None


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
        for group_instance, group in groupby(self.votings.values(), lambda voting: voting.group):
            yield group_instance, list(group)

    def for_overview_template(self):
        # returns groups, option_map where
        # groups is a list of (group, group_list)
        # where group is the group instance
        # group_list is a list containing
        # (type, Voting)
        # where type is either 'median' or 'schulze' and voting is an instace of
        # the voting (model)
        #
        # option_map is a mapping from each schulze_voting id to a list of its
        # options as string
        groups = []
        option_map = dict()
        for group, votings in self.by_group():
            group_list = []
            for v in votings:
                if isinstance(v, voting_models.MedianVoting):
                    group_list.append(('median', v))
                elif isinstance(v, voting_models.SchulzeVoting):
                    group_list.append(('schulze', v))
                    v_id = v.id
                    if v_id not in self.voting_description:
                        msg = gettext('No options for schulze voting %(voting)d' % {'voting': v_id})
                        warning = QueryWarning(msg)
                        self.warnings.append(warning)
                        option_map[v_id] = []
                    else:
                        options = self.voting_description[v_id]
                        option_map[v_id] = [o.option for o in options]
                else:
                    assert False
            groups.append((group, group_list))
        return groups, option_map


def merge_voting_results(median, schulze):
    # TODO why should ids be unique? something seems wrong here...
    # I mean id=42 could appear in both, median and schulze?
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


def median_votings(**kwargs):
    # usage: provide a query for votings like votings_qs = ...
    # or provide collection=VotingCollection(...) for all votings in a certain collection
    # or provide group=VotingGroup(...) for all votings in a certain group
    votings_qs = None
    if 'votings_qs' in kwargs:
        votings_qs = kwargs['votings_qs']
    elif 'collection' in kwargs:
        collection = kwargs['collection']
        votings_qs = (voting_models.MedianVoting.objects.filter(group__collection=collection)
                     .order_by('group__group_num', 'voting_num'))
    elif 'group' in kwargs:
        group = kwargs['group']
        votings_qs = (voting_models.MedianVoting.objects.filter(group=group)
                     .order_by('voting_num'))
    else:
        raise TypeError('Missing queryset / filter')

    res = GenericVotingResult()
    for voting in votings_qs:
        voting_id = voting.id
        res.votings[voting_id] = voting
        res.voting_description[voting_id] = voting.value
    return res


def schulze_votings(**kwargs):
    # usage: provide a query for votings like votings_qs = ...
    # and options_qs = ...
    # or provide collection=VotingCollection(...) for all votings in a certain collection
    # or provide group=VotingGroup(...) for all votings in a certain group
    votings_qs, options_qs = None, None
    if 'votings_qs' in kwargs:
        votings_qs = kwargs['votings_qs']
    elif 'collection' in kwargs:
         collection = kwargs['collection']
         votings_qs = (voting_models.SchulzeVoting.objects.filter(group__collection=collection)
                       .order_by('group__group_num', 'voting_num'))
    elif 'group' in kwargs:
        group = kwargs['group']
        votings_qs = (voting_models.SchulzeVoting.objects.filter(group=group)
                      .order_by('voting_num'))
    else:
        raise TypeError('Missing queryset / filter')

    if 'options_qs' in kwargs:
        options_qs = kwargs['options_qs']
    elif 'collection' in kwargs:
        collection = kwargs['collection']
        options_qs = (voting_models.SchulzeOption.objects.filter(voting__group__collection=collection)
                      .order_by('voting__id', 'option_num'))
    elif 'group' in kwargs:
        group = kwargs['group']
        options_qs = (voting_models.SchulzeOption.objects.filter(voting__group=group)
                      .order_by('voting__id', 'option_num'))

    res = GenericVotingResult()
    # fetch all schulze votings
    for voting in votings_qs:
        res.votings[voting.id] = voting
    # group options according to votings
    for option in options_qs:
        voting_id = option.voting.id
        # just to be sure, should not happen
        if voting_id not in res.votings:
            msg = gettext('Found option with id %(option)d for voting %(voting)d, but voting does not exist' %{
                'option': option.id,
                'voting': voting_id,
            })
            res.warnings.append(SchulzeWarning(msg))
            continue
        if voting_id in res.voting_description:
            res.voting_description[voting_id].append(option)
        else:
            res.voting_description[voting_id] = [option]
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
            msg = gettext('Found option with id %(option)d for voting %(voting)d, but voting does not exist' %{
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
            msg = gettext('Found a vote with id %(vote)d for schulze option with id %(option)d for voting %(voting)d, but voting does not exist' % {
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
    for voting_id, votes in res.votes.items():
        if voting_id not in res.voting_description:
            msg = gettext('Vote with id %(vote)d has no description' % {'vote': voting_id})
            res.warnings.append(msg)
            continue
        voting_options = res.voting_description[voting_id]
        if len(votes) != len(voting_options):
            msg = gettext('Number of options %(options)d does not match number of votes %(votes)d for voting %(voting)d' % {
                'options': len(voting_options),
                'votes': len(votes),
                'voting': voting_id,
            })
            res.warnings.append(SchulzeWarning(msg))
            continue
        for vote, option in zip(votes, voting_options):
            if vote.option != option:
                msg = gettext('Invalid vote for option for vote %(vote)d: Got vote for option %(option)d instead of %(for)d' % {
                    'vote': voting_id,
                    'option': vote.option.id,
                    'for': option.id,
                    })
                res.warnings.append(SchulzeWarning(msg))
                # no continue here, evaluation works fine but probably something is wrong
    return res
