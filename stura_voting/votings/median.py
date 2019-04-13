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

from .results import *
from .models import *
from .utils import compute_majority

from django.utils.translation import gettext

import median_voting as mv


def median_for_evaluation(collection):
    # TODO check revisions or is this not required?
    all_votings = median_votings(collection=collection)
    # now get all votes for all votings
    votes_qs = (MedianVote.objects
                .filter(voting__group__collection=collection)
                .select_related('voting', 'voter')
                .order_by('voting__id', '-value'))
    # TODO did we somewhere use order_by(voting) (or something like that)
    # instead of voting__id?

    # now fill all_votings.votes with ordered dicts: for each voting
    # map to list of MedianVote objects
    # we don't actually map to a list but to OrderedDict with the voter ids
    # as key
    for voting, votes in groupby(votes_qs, lambda vote: vote.voting):
        voter_mapping = OrderedDict()
        for vote in votes:
            if vote.voting.id not in all_votings.votings:
                # this should really not happen ;)
                msg = gettext(
                    'Invalid voting %(voting_name)s: Does not exist.' % {
                        'voting_name': vote.voting.name,
                    })
                all_votings.warnings.append(QueryWarning(msg))
                continue
            if vote.value > voting.value:
                # not very nice, but should be fine...
                msg = gettext(
                    'Invalid vote for voting %(voting_name)s: Value %(got)d is greater than voting value %(voting_value)d. Vote for %(voter)s not counted' % {
                        'voting_name': voting.name,
                        'got': vote.value,
                        'voting_value': voting.value,
                        'voter': vote.voter.name,
                    })
                all_votings.warnings.append(QueryWarning(msg))
            else:
                voter_mapping[vote.voter.id] = vote
        all_votings.votes[voting.id] = voter_mapping
    return all_votings


def single_median_statistics(voting, votes, voters_map):
    res = GenericVotingInstance()
    # create list of MedianVote instances
    median_votes = []
    # compute sum of all weights
    weight_sum = 0
    # appended s.t. we can keep the order
    # should not be really necessary because all None votes are at the end
    # though
    additional_votes = []
    absolute = voting.absolute_majority
    # only for debuging to ensure the queryset is sorted
    last_vote = None
    for voter_id, vote in votes.items():
        if vote is None:
            if absolute:
                weight = voters_map[voter_id].weight
                weight_sum += weight
                v = mv.MedianVote(0, weight)
                additional_votes.append(v)
                res.votes[voter_id] = v
            else:
                res.votes[voter_id] = None
        else:
            weight = vote.voter.weight
            weight_sum += weight
            v = mv.MedianVote(vote.value, weight)
            median_votes.append(v)
            res.votes[voter_id] = v
            if last_vote is not None:
                assert last_vote.value >= vote.value
            last_vote = vote
    # append all missing
    median_votes.extend(additional_votes)
    res.instance = mv.MedianStatistics(median_votes, is_sorted=True)
    res.weight_sum = weight_sum
    res.majority = compute_majority(voting.majority, weight_sum)
    return res
