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

from itertools import groupby

from .results import *
from .models import *

import schulze_voting as sv


def schulze_for_evaluation(collection):
    # TODO check revisions or is this not required?
    all_votings = schulze_votings(collection=collection)
    # now get all votes
    votes_qs = (
        SchulzeVote.objects .filter(
            option__voting__group__collection=collection) .select_related(
            'option',
            'voter') .order_by(
                'option__voting__id',
                'voter__id',
            'option__option_num'))
    # now fill all_votings.votes with ordered dicts: for each voting
    # map to a list of lists of SchulzeVote objects and do some sanity checks
    # we do this in some places so probably we could write a nicer function
    # for this...

    # sanity checks are postponed until later to keep the code clearer
    for voting, votes_for_voting in groupby(
            votes_qs, lambda vote: vote.option.voting):
        voter_mapping = dict()
        for voter, votes_for_voter in groupby(
                votes_for_voting, lambda vote: vote.voter):
            votes_list = list(votes_for_voter)
            voter_mapping[voter.id] = votes_list
        all_votings.votes[voting.id] = voter_mapping
    # now for the sanity checks
    # we might need to remove votings if they're invalid
    votings_to_remove = set()
    for voting_id, voter_mapping in all_votings.votes.items():
        # first assert that voting exists
        # again, this should really not happen ;)
        if voting_id not in all_votings.votings or voting_id not in all_votings.voting_description:
            msg = gettext(
                'Invalid voting with id %(voting_id)s: Does not exist' % {
                    'voting_id': voting_id,
                })
            all_votings.warnings.append(QueryWarning(msg))
            continue
        voting = all_votings.votings[voting_id]
        options = all_votings.voting_description[voting_id]
        if not options:
            msg = gettext(
                'Invalid schulze voting %(voting_name)s: No options given. Not including in result' % {
                    'voting_name': voting.name,
                })
            all_votings.warnings.append(QueryWarning(msg))
            votings_to_remove.add(voting_id)
            continue
        voters_to_remove = set()
        for voter_id, votes_for_voter in voter_mapping.items():
            if len(options) != len(votes_for_voter):
                msg = gettext(
                    'Invalid vote for voting %(voting_name)s: Expected ranking of length %(expected) and got length %(got)d. Not considered. Voter id is %(voter_id)d' % {
                        'voting_name': voting.name,
                        'expected': len(options),
                        'got': len(votes_for_voter),
                        'voter_id': voter_id,
                    })
                all_votings.warnings.append(QueryWarning(msg))
                # remove entry for this voter
                voters_to_remove.add(voter_id)
                continue
            for vote, option in zip(votes_for_voter, options):
                if vote.option != option:
                    msg = gettext(
                        'Invalid vote for voting %(voting_name)s: Expected vote for %(expected_name)s and got vote for %(got_name)s' % {
                            'voting_name': voting.name,
                            'expected_name': option.option,
                            'got_name': vote.option.name,
                        })
                    all_votings.warnings.append(QueryWarning(msg))
                    # remove
                    voters_to_remove.add(voter_id)
                    continue

        # now remove all voters that had invalid votes
        for remove in voters_to_remove:
            del voter_mapping[remove]
    # first we remove all votings marked in votings_to_remove
    # we delete that votings as well as all votes for it
    for remove in votings_to_remove:
        if remove in all_votings.votings:
            del all_votings.votings[remove]
        if remove in all_votings.votes:
            del all_votings.votes[remove]
    # because we removed voters a voter_mapping could have become empty:
    # we clear that data
    votings_to_remove = set()
    for voting_id, voter_mapping in all_votings.votes.items():
        if not voter_mapping:
            votings_to_remove.add(voting_id)
    for remove in votings_to_remove:
        del all_votings.votes[remove]
    return all_votings


def single_schulze_instance(voting, votes, options, voters_map):
    # TODO how to check if we have at least two options?
    # voting: SchulzeVoting instance, votes: map as computed in view
    # options: list of options for instance (map)
    # voters_map: map voter_id to voter
    res = GenericVotingInstance()
    schulze_votes = []
    weight_sum = 0
    absolute = voting.absolute_majority
    for voter_id, vote in votes.items():
        weight = voters_map[voter_id].weight
        if vote is None:
            if absolute:
                # make a vote for last option (No)
                weight_sum += weight
                n = len(options)
                assert n
                ranking = [2] * (n - 1)
                ranking.append(1)
                v = sv.SchulzeVote(ranking, weight)
                schulze_votes.append(v)
                res.votes[voter_id] = v
            else:
                res.votes[voter_id] = None
        else:
            weight_sum += weight
            ranking = [option_vote.sorting_position for option_vote in vote]
            v = sv.SchulzeVote(ranking, weight)
            schulze_votes.append(v)
            res.votes[voter_id] = v
    res.instance = schulze_votes
    res.weight_sum = weight_sum
    res.majority = compute_majority(voting.majority, weight_sum)
    return res
