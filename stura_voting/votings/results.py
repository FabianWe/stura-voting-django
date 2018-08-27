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
from collections import OrderedDict
from heapq import merge


class VoteConsistencyError(Exception):
    def __init__(self, message, voter, voting):
        super().__init__(message)
        self.voter = voter
        self.voting = voting


class DuplicateError(Exception):
    pass


def voters_map(revision):
    voters = Voter.objects.filter(revision=revision)
    return {voter.id: voter for voter in voters}


class GenericVote(object):
    def __init__(self, voter, value=None, inst=None):
        self.voter = voter
        self.value = value
        self.inst = inst


class GenericVoting(object):
    def __init__(self, voting):
        self.voting = voting
        self.votes = {}


class GroupRes(object):

    median_prefix = 'median'
    schulze_prefix = 'schulze'

    def __init__(self, group):
        self.group = group
        self.results = OrderedDict()


    def insert_median(self, voting):
        self.results[self.median_prefix + str(voting.id)] = GenericVoting(voting)

    def insert_schulze(self, voting):
        self.results[self.schulze_prefix + str(voting.id)] = GenericVoting(voting)


    def insert(self, voting):
        if isinstance(voting, MedianVoting):
            self.insert_median(voting)
        elif isinstance(voting, SchulzeVoting):
            self.insert_schulze(voting)
        else:
            # TODO raise value error?
            assert False


    def get_median(self, id, default=None):
        return self.results.get(self.median_prefix + str(id), default)

    def get_schulze(self, id, default=None):
        return self.results.get(self.schulze_prefix + str(id), default)


    def items(self):
        for key, voting in self.results.items():
            if key.startswith(self.median_prefix):
                yield 'median', int(key[len(self.median_prefix):]), voting
            elif key.startswith(self.schulze_prefix):
                yield 'schulze', int(key[len(self.schulze_prefix):]), voting
            else:
                # TODO raise value error?
                assert False


class GroupWarning(object):
    def __init__(self, group, voting):
        self.group = group
        self.voting = voting


    def __str__(self):
        return 'Group %s(id=%d) vor voting %s(id=%d) not found' % (self.group.name, self.group.id, self.voting.name, self.voting.id)


class CollectionRes(object):
    def __init__(self):
        self.groups = OrderedDict()
        self.warnings = []

    @staticmethod
    def from_collection(collection, voters=None, check_pedantic=True):
        # TODO test this stuff
        # TODO everything broken here :(
        collection = get_instance(VotingCollection, collection)
        res = CollectionRes()
        # we want something like a sql left join, we'll use multiple queries...
        # easier than writing complicated queries, not so efficient but should do
        # that's because we want all groups, even those that don't have a voting
        # and we want all votings, even those that don't have a result
        groups = VotingGroup.objects.filter(collection=collection).order_by('group_num')
        # now we have all groups, so find the votings for each group
        for group in groups:
            group_res = GroupRes(group)
            res.groups[group.id] = group_res
            # now find all votings for this group
            median_votings = MedianVoting.objects.filter(group=group).order_by('voting_num')
            schulze_votings = SchulzeVoting.objects.filter(group=group).order_by('voting_num')
            # now both are sorted according to voting_num, merge results
            all_votings = merge(median_votings, schulze_votings, key=lambda v: v.voting_num)
            for voting in all_votings:
                group_res.insert(voting)
        # now we have all groups and all votings, now we gather the results
        # first we need the voters
        if voters is None:
            voters = voters_map(collection.revision)
        # now with two queries we get all results
        # query for all median results
        median_votes = MedianVote.objects.filter(voting__group__collection=collection).order_by('voting__id', 'value')
        for vote in median_votes:
            group_res = res.groups.get(vote.voting.group.id, None)
            if group_res is None:
                res.warnings.append(GroupWarning(vote.voting.group, vote.voting))
            else:
                # group found
                # fetch voting object from group
                generic_voting = group_res.get_median(vote.voting.id)
                if generic_voting is None:
                    res.warnings.append('')
        # TODO correct??
        schulze_votes = SchulzeVote.objects.filter(option__voting__group__collection=collection).order_by('voting__id',
                                                                                                          'voter__id',
                                                                                                          'option__option_num')
        print(list(schulze_votes))
        # now all options should be nicely sorted... so we can just iterate over them
        # iterate over each voting
        for voting, votes_for_voting in groupby(schulze_votes, lambda vote: vote.option.voting):
            # now for each vote of that voting iterate over each voter
            for voter, votes_for_voter in groupby(votes_for_voting, lambda vote: vote.voter):
                pass
        return res



class Votes(object):
    def __init__(self, voting, votes, num_casted_votes, all_voters):
        self.voting = voting
        self.votes = votes
        self.num_casted_votes = num_casted_votes
        self.all_voters = all_voters

    @staticmethod
    def from_median(voting, voters=None, check_pedantic=True):
        # TODO read again and check...
        voting = get_instance(MedianVoting, voting)
        if voters is None:
            voters = voters_map(voting.group.collection.revision)
        # compute result, first all voters that did cast a voting
        casted_votes = list(MedianVote.objects.filter(voting=voting))
        num_casted_votes = len(casted_votes)
        res = []
        for vote in casted_votes:
            if check_pedantic:
                if vote.value < 0 or vote.value > voting.value:
                    raise VoteConsistencyError('Found invalid vote for voting: Value is %d, expected value betweeen 0 and %d in voting %s(id=%d)' %
                                               (vote.value, voting.value, voting.name, voting.voting_num),
                                               vote.voter,
                                               voting)
            res.append(GenericVote(vote.voter, vote.value, vote))
        # if all votes should be counted, even those who did not submit, compute
        # them as well
        if voting.count_all_votes:
            casted_votes_set = {vote.voter.id for vote in casted_votes}
            # iterate over all voters and compute those who didn't submit
            for voter_id, voter in voters.items():
                if voter_id not in casted_votes_set:
                    # append to res
                    res.append(GenericVote(voter, None, None))
        return Votes(voting, res, num_casted_votes, voters)


    @staticmethod
    def from_schulze(voting, voters=None, check_pedantic=True):
        # TODO doc: Raises ConsistencyError...
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
                raise VoteConsistencyError('Found invalid votes for voting: Expected %d options, fond %d in voting %s(id=%d)' %
                                           (num_options, len(ranking), voting.name, voting.voting_num),
                                           voter, voting)
                pass
            else:
                res.append(GenericVote(voter, ranking, votes))
        num_casted_votes = len(res)
        if voting.count_all_votes:
            casted_votes_set = {vote.voter.id for vote in casted_votes}
            # iterate over all voters and compute those who didn't submit
            for voter_id, voter in voters.items():
                if voter_id not in casted_votes_set:
                    # append to res
                    res.append(GenericVote(voter, None, None))
        return Votes(voting, res, num_casted_votes, voters)


    # TODO build a smarter way to access the database instead of calling
    # from_median and from_schulze multiple times?

    # TODO in subpackage (stura_voting_utils) specify requirements
    # (I know that this is not the right place for this TODO)
