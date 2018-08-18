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

from .utils import get_instance
from .models import *

from itertools import groupby


def voters_map(revision):
    voters = Voter.objects.filter(revision=revision)
    return {voter.id: voter for voter in voters}


class GenericVotingRes(object):
    def __init__(self, voter, value=None, inst=None):
        self.voter = voter
        self.value = value
        self.inst = inst


class Votes(object):
    def __init__(self, voting, votes, num_casted_votes, all_voters):
        self.voting = voting
        self.votes = votes
        self.num_casted_votes = num_casted_votes
        self.all_voters = all_voters


    @staticmethod
    def from_median(voting, voters=None):
        # TODO read again and check...
        voting = get_instance(MedianVoting, voting)
        if voters is None:
            voters = voters_map(voting.group.collection.revision)
        # compute result, first all voters that did cast a voting
        casted_votes = list(MedianVote.objects.filter(voting=voting))
        num_casted_votes = len(casted_votes)
        res = [GenericVotingRes(vote.voter, vote.value, vote) for vote in casted_votes]
        # if all votes should be counted, even those who did not submit, compute
        # them as well
        if voting.count_all_votes:
            casted_votes_set = {vote.voter.id for vote in casted_votes}
            # iterate over all voters and compute those who didn't submit
            for voter_id, voter in voters.items():
                if voter_id not in casted_votes_set:
                    # append to res
                    res.append(GenericVotingRes(voter, None, None))
        return Votes(voting, res, num_casted_votes, voters)


    @staticmethod
    def from_schulze(voting, voters=None, check_pedantic=True):
        # TODO read again and check...
        voting = get_instance(SchulzeVoting, voting)
        if voters is None:
            voters = voters_map(voting.group.collection.revision)
        # if check pedantic is true check each voter for correct length
        num_options = None
        if check_pedantic:
            num_options = SchulzeOption.objects.filter(voting=voting).count()
        # compute result, first all voters that did cast a vote
        # this gives us many entries for each voter, so we have to map them
        # TODO is this order by correct?
        casted_votes = SchulzeVote.objects.filter(option__voting=voting).order_by('voter__id', 'option__option_num')
        # build groups according to the voter
        votes_by_voter = groupby(casted_votes, lambda vote: vote.voter)
        res = []
        for voter, votes in votes_by_voter:
            # we may use votes many times, so simply cast to a list
            votes = list(votes)
            # the vote positions are sorted according to the option they belong to, so
            # simply transform to a list
            ranking = [vote.sorting_position for vote in votes]
            # if check pedantic is true check length
            if check_pedantic and len(ranking) != num_options:
                # TODO do something
                pass
            else:
                res.append(GenericVotingRes(voter, ranking, votes))
        num_casted_votes = len(res)
        if voting.count_all_votes:
            casted_votes_set = {vote.voter.id for vote in casted_votes}
            # iterate over all voters and compute those who didn't submit
            for voter_id, voter in voters.items():
                if voter_id not in casted_votes_set:
                    # append to res
                    res.append(GenericVotingRes(voter, None, None))
        return Votes(voting, res, num_casted_votes, voters)

