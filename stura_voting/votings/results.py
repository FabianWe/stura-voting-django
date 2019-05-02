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

from django.utils.translation import gettext

from . import utils
from . import models as voting_models
from django.db.models import Q


# TODO in subpackage (stura_voting_utils) specify requirements
# (I know that this is not the right place for this TODO)

def get_median_votes(collection, voter=None, **kwargs):
    """Returns all median votes for a given collection.

    Returns a queryset containing all votes for all median votings in the given collection.

    Args:
        collection (models.VotingCollection): Collection pk or models.VotingCollection to
            gather results for.
        voter (models.Voter or None): If None all median votes are returned, otherwise
            only for this particular voter are returned.
        **kwargs: Additional arguments directly passed to the queryset filter.

    Returns:
        queryset: All votes for all votings in the collection (or only for a particular
            voter).
    """
    collection = utils.get_instance(voting_models.VotingCollection, collection)
    if voter is None:
        return voting_models.MedianVote.objects.filter(
            voting__group__collection=collection, **kwargs)
    else:
        voter = utils.get_instance(voting_models.Voter, voter)
        return voting_models.MedianVote.objects.filter(
            voting__group__collection=collection, voter=voter, **kwargs)


def get_schulze_votes(collection, voter=None, **kwargs):
    """Returns all schulze votes for a given collection.

    Returns a queryset containing all votes for all schulze votings in the given collection.

    Args:
        collection (models.VotingCollection): Collection pk or models.VotingCollection to
            gather results for.
        voter (models.Voter or None): If None all schulze votes are returned, otherwise
            only for this particular voter are returned.
        **kwargs: Additional arguments directly passed to the queryset filter.

    Returns:
        queryset: All votes for all votings in the collection (or only for a particular
            voter).
    """
    collection = utils.get_instance(voting_models.VotingCollection, collection)
    if voter is None:
        return voting_models.SchulzeVote.objects.filter(
            option__voting__group__collection=collection, **kwargs)
    else:
        voter = utils.get_instance(voting_models.Voter, voter)
        return voting_models.SchulzeVote.objects.filter(
            option__voting__group__collection=collection, voter=voter, **kwargs)


def get_voters_with_vote(collection):
    # returns all voters that casted a vote for any of the votes in the
    # collection
    # returns them by id as a set
    """Returns a set of all voters that voted for a least one voting.

    Args:
        collection (models.VotingCollection): The collection to gather votes for.

    Returns:
        set of int: The set of all voter ids that participated in at least one of the median
            and schulze votings in the collection.
    """
    all_voters = get_median_votes(collection).values_list('voter__id', flat=True)
    result = set(all_voters)
    all_voters = get_schulze_votes(collection).values_list('voter__id', flat=True)
    result.update(all_voters)
    return result


class QueryWarning(object):
    """A warning encountered during performing a query.

    This is a more or less generic warning class we use to notify about warnings (wrong
    vote etc.).
    Can be converted to string with str.

    Attributes:
        message (string): The warning message.

    """
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return str(self.message)


class MedianWarning(object):
    """A warning for a median voting, describing that an invalid entry was found.

    A warning can be converted to a string with str.

    Attributes:
        voting (models.MedianVoting): The voting for which something went wrong.
        got (int): The value we found during the voting.
    """
    def __init__(self, voting, got):
        self.voting = voting
        self.got = got

    def __str__(self):
        return gettext(
            'Warning for voting with id %(voting)d: Expected value between 0 and %(max)d but got value %(got)d' % {
                'voting': self.voting.id,
                'max': self.voting.value,
                'got': self.got,
            })


class SchulzeWarning(object):
    """A warning for a schulze voting.

    A more or less generic class for warnings directly connected to a schulze voting.
    A warning can be converted to a string with str.

    Attributes:
        message (str): Description of the warning.

    """
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return str(self.message)


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
        for group_instance, group in groupby(
                self.votings.values(), lambda voting: voting.group):
            yield group_instance, list(group)

    def for_overview_template(self):
        # TODO is this used somewhere? I think only in combined required?
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
                        msg = gettext(
                            'No options for schulze voting %(voting)d' % {
                                'voting': v_id})
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

    def fill_missing_voters(self, voters_list):
        for vote_id in self.votings:
            if vote_id not in self.votes:
                self.votes[vote_id] = dict()
            votes = self.votes[vote_id]
            for voter in voters_list:
                if voter.id not in votes:
                    votes[voter.id] = None


class CombinedVotingResult(object):
    median_prefix = 'median_'
    schulze_prefix = 'schulze_'

    @staticmethod
    def median_key(m_id):
        return CombinedVotingResult.median_prefix + str(m_id)

    @staticmethod
    def schulze_key(s_id):
        return CombinedVotingResult.schulze_prefix + str(s_id)

    @staticmethod
    def parse_median_key(s):
        return int(s[len(CombinedVotingResult.median_prefix):])

    @staticmethod
    def parse_schulze_key(s):
        return int(s[len(CombinedVotingResult.schulze_prefix):])

    @staticmethod
    def parse_key(s):
        if s.startswith(CombinedVotingResult.median_prefix):
            return 'median', CombinedVotingResult.parse_median_key(s)
        elif s.startswith(CombinedVotingResult.schulze_prefix):
            return 'schulze', CombinedVotingResult.parse_schulze_key(s)
        else:
            return None

    def __init__(self, median, schulze):
        self.median = median
        self.schulze = schulze
        self.warnings = median.warnings + schulze.warnings

    def get_schulze_vote(self, voting_id):
        return self.schulze.votes[voting_id]

    def get_median_vote(self, voting_id):
        return self.median.votes[voting_id]

    def combined_votings(self):
        def key(e):
            return e.group.group_num, e.voting_num
        merged_list = merge(
            self.median.votings.values(),
            self.schulze.votings.values(),
            key=key)
        yield from merged_list

    def by_group(self):
        for group_instance, group in groupby(
                self.combined_votings(), lambda voting: voting.group):
            yield group_instance, list(group)

    def for_overview_template(self, all_groups=None):
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

        # if we should also include empty groups, check this
        if all_groups is not None:
            if isinstance(all_groups, voting_models.VotingCollection):
                all_groups = (voting_models.VotingGroup.objects.filter(collection=all_groups)
                              .order_by('group_num'))


        # a set for all groups for which we found an entry (ids)
        groups_set = set()
        groups = []
        option_map = dict()
        for group, votings in self.by_group():
            groups_set.add(group.id)
            group_list = []
            for v in votings:
                if isinstance(v, voting_models.MedianVoting):
                    group_list.append(('median', v))
                elif isinstance(v, voting_models.SchulzeVoting):
                    group_list.append(('schulze', v))
                    v_id = v.id
                    if v_id not in self.schulze.voting_description:
                        msg = gettext(
                            'No options for schulze voting %(voting)d' % {
                                'voting': v_id})
                        warning = QueryWarning(msg)
                        self.warnings.append(warning)
                        option_map[v_id] = []
                    else:
                        options = self.schulze.voting_description[v_id]
                        option_map[v_id] = [o.option for o in options]
                else:
                    assert False
            groups.append((group, group_list))
        # now: if we should also fetch empty groups check which groups have not
        # been found, add an empty list
        if all_groups is not None:
            groups_not_found = []
            for group in all_groups:
                if group.id not in groups_set:
                    groups_not_found.append((group, []))
            # merge lists
            groups = list(merge(groups, groups_not_found, key=lambda e: e[0].group_num))
        return groups, option_map


def median_votings(select_for_update=False, **kwargs):
    # usage: provide a query for votings like votings_qs = ...
    # or provide collection=VotingCollection(...) for all votings in a certain collection
    # or provide group=VotingGroup(...) for all votings in a certain group
    if 'votings_qs' in kwargs:
        votings_qs = kwargs['votings_qs']
    elif 'collection' in kwargs:
        collection = kwargs['collection']
        votings_qs = (
            voting_models.MedianVoting.objects.filter(
                group__collection=collection) .order_by(
                'group__group_num', 'voting_num'))
    elif 'group' in kwargs:
        group = kwargs['group']
        votings_qs = (voting_models.MedianVoting.objects.filter(group=group)
                      .order_by('voting_num'))
    else:
        raise TypeError('Missing queryset / filter')

    if select_for_update:
        votings_qs = votings_qs.select_for_update()

    res = GenericVotingResult()
    for voting in votings_qs:
        voting_id = voting.id
        res.votings[voting_id] = voting
        res.voting_description[voting_id] = voting.value
    return res


def schulze_votings(select_for_update=False, **kwargs):
    # usage: provide a query for votings like votings_qs = ...
    # and options_qs = ...
    # or provide collection=VotingCollection(...) for all votings in a certain collection
    # or provide group=VotingGroup(...) for all votings in a certain group
    votings_qs, options_qs = None, None
    if 'votings_qs' in kwargs:
        votings_qs = kwargs['votings_qs']
    elif 'collection' in kwargs:
        collection = kwargs['collection']
        votings_qs = (
            voting_models.SchulzeVoting.objects.filter(
                group__collection=collection) .order_by(
                'group__group_num', 'voting_num'))
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
        options_qs = (
            voting_models.SchulzeOption.objects.filter(
                voting__group__collection=collection) .order_by(
                'voting__id', 'option_num'))
    elif 'group' in kwargs:
        group = kwargs['group']
        options_qs = (
            voting_models.SchulzeOption.objects.filter(
                voting__group=group) .order_by(
                'voting__id', 'option_num'))

    if select_for_update:
        votings_qs = votings_qs.select_for_update()
        options_qs = options_qs.select_for_update()

    res = GenericVotingResult()
    # fetch all schulze votings
    for voting in votings_qs:
        res.votings[voting.id] = voting
    # group options according to votings
    for option in options_qs:
        voting_id = option.voting.id
        # just to be sure, should not happen
        if voting_id not in res.votings:
            msg = gettext(
                'Found option with id %(option)d for voting %(voting)d, but voting does not exist' % {
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


# TODO add select_for_update?
def median_votes_for_voter(collection, voter):
    votings_qs = (
        voting_models.MedianVoting.objects.filter(
            group__collection=collection) .order_by(
            'group__group_num',
            'voting_num'))
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
    votings_qs = (
        voting_models.SchulzeVoting.objects.filter(
            group__collection=collection) .order_by(
            'group__group_num',
            'voting_num'))
    # all options
    options_qs = (
        voting_models.SchulzeOption.objects.filter(
            voting__group__collection=collection) .order_by(
            'voting__id', 'option_num'))
    # all options voted for
    votes_qs = (
        voting_models.SchulzeVote.objects.filter(
            voter=voter,
            option__voting__group__collection=collection) .select_for_update() .select_related('option') .order_by(
            'option__voting__id',
            'option__option_num'))
    res = GenericVotingResult()

    # fetch all schulze votings
    for voting in votings_qs:
        res.votings[voting.id] = voting
    # group options according to votings
    for option in options_qs:
        voting_id = option.voting.id
        # just to be sure, should not happen
        if voting_id not in res.votings:
            msg = gettext(
                'Found option with id %(option)d for voting %(voting)d, but voting does not exist' % {
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
            msg = gettext(
                'Found a vote with id %(vote)d for schulze option with id %(option)d for voting %(voting)d, but voting does not exist' % {
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
            msg = gettext(
                'Vote with id %(vote)d has no description' % {
                    'vote': voting_id})
            res.warnings.append(msg)
            continue
        voting_options = res.voting_description[voting_id]
        if len(votes) != len(voting_options):
            msg = gettext(
                'Number of options %(options)d does not match number of votes %(votes)d for voting %(voting)d' % {
                    'options': len(voting_options),
                    'votes': len(votes),
                    'voting': voting_id,
                })
            res.warnings.append(SchulzeWarning(msg))
            continue
        for vote, option in zip(votes, voting_options):
            if vote.option != option:
                msg = gettext(
                    'Invalid vote for option for voting %(voting)d: Got vote for option %(option)d instead of %(for)d' % {
                        'voting': voting_id,
                        'option': vote.option.id,
                        'for': option.id,
                    })
                res.warnings.append(SchulzeWarning(msg))
                # no continue here, evaluation works fine but probably
                # something is wrong
    return res


def for_votes_list_template(voting_result):
    # assumes missing entries have be filled with fill_missing_voters
    groups = []
    for group, votings in voting_result.by_group():
        group_list = []
        for v in votings:
            if isinstance(v, voting_models.MedianVoting):
                v_res = voting_result.get_median_vote(v.id)
                group_list.append(('median', v, v_res))
            elif isinstance(v, voting_models.SchulzeVoting):
                v_res = voting_result.get_schulze_vote(v.id)
                group_list.append(('schulze', v, v_res))
            else:
                assert False
        groups.append((group, group_list))
    return groups


class GenericVotingInstance(object):
    # fields: instance, MedianStatistics for median
    # or list of list of schulze_voting.SchulzeVote for schulze
    # votes: maps voter_id to an instance of median_voting.MedianVote or
    # majority: required votes (int)
    # an instance of schulze_voting.SchulzeVote
    # weight_sum: sum of weights used
    def __init__(self):
        self.instance = None
        self.votes = dict()
        self.weight_sum = None
        self.majority = None


def query_votes(**kwargs):
    # filter by: timespan or specific user (bound to revision) or
    # username contains
    # also possible: all of it
    # returns, what? for voting? for session
    # for session is good: all votings for which a voter voted something
    period = kwargs.pop('period', None)
    start, end = kwargs.pop('start', None), kwargs.pop('end', None)
    query = kwargs.pop('query', None)
    # build filter args
    schulze_kwargs = dict()
    median_kwargs = dict()
    if period is not None:
        schulze_kwargs.update(option__voting__group__collection__revision__period=period)
        median_kwargs.update(voting__group__collection__revision__period=period)
    if start is not None:
        schulze_kwargs.update(option__voting__group__collection__time__gte=start)
        median_kwargs.update(voting__group__collection__time__gte=start)
    if end is not None:
        schulze_kwargs.update(option__voting__group__collection__time__lte=end)
        median_kwargs.update(voting__group__collection__time__lte=end)
    schulze_q, median_q = None, None
    if query is not None:
        if kwargs.pop('split', False):
            split = query.split(' ')
            split = map(lambda s: s.strip(), split)
            split = list(filter(lambda s: s, split))
            if split:
                schulze_q = Q()
                median_q = Q()
                for sub in map(lambda s: s.strip(), split):
                    schulze_q = schulze_q | Q(voter__name__icontains=sub)
                    median_q = median_q | Q(voter__name__icontains=sub)
        else:
            if query:
                schulze_kwargs.update(voter__name__icontains=query)
                median_kwargs.update(voter__name__icontains=query)
    schulze_args, median_args = (), ()
    if schulze_q is not None:
        schulze_args += (schulze_q,)
    if median_q is not None:
        median_args += (median_q,)
    schulze_votes = voting_models.SchulzeVote.objects.filter(*schulze_args, **schulze_kwargs)
    median_votes = voting_models.MedianVote.objects.filter(*median_args, **median_kwargs)
    for v in schulze_votes:
        print(v)
    for v in median_votes:
        print(v)
    print('Total:', len(schulze_votes) + len(median_votes))
