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

from django.shortcuts import render, reverse, redirect
from django.views.generic.detail import DetailView
from django.views.generic import ListView, UpdateView
from django.views.generic.edit import DeleteView
from django.http import Http404
from django.db import transaction

from .results import *

# TODO when parsing inputs via our library, check lengths before inserting?

from .models import *
from .forms import *
from .utils import *

# TODO which views should be atomic
# also see select_for_update

def index(request):
    return render(request, 'votings/index.html')


def archive_index(request):
    return render(request, 'votings/archive.html',
             {'periods': Period.objects.order_by('-start', '-created')[:10],
              'collections': VotingCollection.objects.order_by('-time')[:10]})


@transaction.atomic
def new_period(request):
    if request.method == 'GET':
        form = PeriodForm()
    else:
        form = PeriodForm(request.POST)
        if form.is_valid():
            period = form.save()
            if form.cleaned_data['revision']:
                # create a first revision
                rev = VotersRevision.objects.create(period=period, note='')
                for voter in form.cleaned_data['revision']:
                    Voter.objects.create(revision=rev, name=voter.name, weight=voter.weight)
            return redirect('period_detail_success', pk=period.id)
    return render(request, 'votings/new_period.html', {'form': form})


class PeriodDetailView(DetailView):
    model = Period

    context_object_name = 'period'
    template_name = 'votings/period_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        period = context['period']
        revs = VotersRevision.objects.filter(period=period).order_by('-period__start', '-period__created', '-created')
        context['revisions'] = revs
        collections = VotingCollection.objects.filter(revision__period=period).order_by('-time')
        context['collections'] = collections
        return context


class PeriodUpdateView(UpdateView):
    model = Period
    fields = ('start', 'end')
    template_name = 'votings/update_period.html'

    def get_success_url(self):
        return reverse('period_detail', args=[self.object.id])

class PeriodDetailSuccess(PeriodDetailView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['success'] = True
        return context


def enter_voterlist(request, pk):
    collection = get_object_or_404(VotingCollection, pk=pk)
    with_vote_id = get_voters_with_vote(collection)
    all_voters = Voter.objects.filter(revision=collection.revision).order_by('name')
    with_vote = []
    without_vote = []
    for voter in all_voters:
        if voter.id in with_vote_id:
            with_vote.append(voter)
        else:
            without_vote.append(voter)
    context = {'collection': collection, 'with_vote': with_vote, 'without_vote': without_vote}
    return render(request, 'votings/enter_voterlist.html', context)

@transaction.atomic
def enter_single_voter_view(request, coll, v):
    collection = get_object_or_404(VotingCollection, pk=coll)
    voter = get_object_or_404(Voter, pk=v)
    context = {'collection': collection, 'voter': voter}
    if voter.revision != collection.revision:
        # TODO remove probably
        return HttpResponseBadRequest('Fooo')
    if request.method == 'GET':
        form = ResultsSingleVoterForm(collection=collection, voter=voter)
    else:
        form = ResultsSingleVoterForm(request.POST, collection=collection, voter=voter)
        if form.is_valid():
            for v_type, v_id, val in form.votings():
                if v_type == 'median':
                    __handle_enter_median(form.median_result, v_id, val, voter)
                elif v_type == 'schulze':
                    __handle_enter_schulze(form.schulze_result, v_id, val, voter)
                else:
                    assert False
    context['form'] = form
    # our methods might change the contents of schulze and median warnings, thus
    # the merged result does not contain all warnings, we merge them here again
    context['warnings'] = list(map(str, form.median_result.warnings + form.schulze_result.warnings))
    return render(request, 'votings/enter_single.html', context)

def __handle_enter_median(result, v_id, val, voter):
    # result: GenericVotingResult for meidan votes only
    # v_id id of the voting
    # val: None or tuple (value, currency)
    # first lookup voting and ensure it exists
    if v_id not in result.votings:
        msg = _('Median voting with id %(voting)d does not exist, not saved' % {
            'voting': v_id,
        })
        waring = QueryWarning(msg)
        result.warnings.append(warning)
        return
    voting = result.votings[v_id]
    # if val is None (no entry and result exists: delete it)
    if val is None:
        # delete if exists, otherwise keep as it is
        if v_id in result.votes:
            # just delete the single entry
            result.votes[v_id].delete()
    else:
        # update or insert
        if v_id in result.votes:
            entry = result.votes[v_id]
            # update
            entry.value = val[0]
            entry.save(update_fields=['value'])
        else:
            # insert
            MedianVote.objects.create(value=val[0], voter=voter, voting=voting)

def __handle_enter_schulze(result, v_id, val, voter):
    # result: GenericVotingResult for meidan votes only
    # v_id id of the voting
    # val: None or list of ints (the ranking)
    # in this code we do some sanity checks, just to be absolutely sure everything
    # is correct
    # first lookup voting and ensure it exists
    if v_id not in result.votings:
        msg = _('Schulze voting with id %(voting)d does not exist, not saved' % {
            'voting': v_id,
        })
        waring = QueryWarning(msg)
        result.warnings.append(warning)
        return
    # if val is None (no entry and result exists: delete it)
    if val is None:
        # delete all entries if exists, otherwise keep as it is
        if v_id in result.votes:
            votes = result.votes[v_id]
            for vote in votes:
                vote.delete()
    else:
        # update or insert
        if v_id not in result.voting_description:
            msg = _('Schulze voting with id %(voting)d has no options, not saved' % {
                'voting': v_id,
            })
            warning = QueryWarning(msg)
            result.warnings.append(warning)
            return
        voting_options = result.voting_description[v_id]
        if len(val) != len(voting_options):
            msg = _('Invalid schulze result. Internal error? Result for voting %(voting)d not saved' % {
                'voting': v_id
            })
            warning = QueryWarning(msg)
            result.warnings.append(waring)
            return
        if v_id in result.votes:
            # update
            current_votes = result.votes[v_id]
            # again, some sanity checks here...
            # before we only added warnings, but even options with warnings
            # got inserted. So now we prevent an update / insertion if something
            # is wrong
            if len(current_votes) != len(voting_options):
                msg = _('Number of options %(options)d does not match number of votes %(votes)d for voting %(voting)d. Not saved' % {
                    'options': len(voting_options),
                    'votes': len(current_votes),
                    'voting': v_id,
                })
                warning = QueryWarning(msg)
                result.warnings.append(warning)
                return
            # another sanity check, again
            for vote, option in zip(current_votes, voting_options):
                if vote.option != option:
                    # if this happens: The existing entries are invalid, we delete all of them
                    # then when create a warning and return
                    for vote in current_votes:
                        vote.delete()
                    msg = _('Invalid vote for option for vote %(vote)d: Got vote for option %(option)d instead of %(for)d. Existing entries were deleted!' % {
                        'vote': v_id,
                        'option': vote.option.id,
                        'for': option.id,
                        })
                    warning = QueryWarning(msg)
                    result.warnings.append(warning)
                    return
            # sanity checks passed, now we can update all existing votes
            # finally, everything ok, insert
            # we also know that len(current_votes) == len(val)
            for vote, new_pos in zip(current_votes, val):
                vote.sorting_position = new_pos
                vote.save(update_fields=['sorting_position'])
        else:
            # we know that len(val) == len(voting_options, so insert)
            for option, ranking_pos in zip(voting_options, val):
                SchulzeVote.objects.create(sorting_position= ranking_pos,
                                           voter=voter,
                                           option=option)


def revision_success(request, pk):
    rev = get_object_or_404(VotersRevision, pk=pk)
    return render(request, 'votings/success_revision.html', {'period': rev.period.name})

@transaction.atomic
def new_revision(request):
    if request.method == 'GET':
        form = RevisionForm()
    else:
        form = RevisionForm(request.POST)
        if form.is_valid():
            rev = form.save()
            for voter in form.cleaned_data['voters']:
                Voter.objects.create(revision=rev, name=voter.name, weight=voter.weight)
            return redirect('new_revision_success', pk=rev.id)
    return render(request, 'votings/new_revision.html', {'form': form})


class PeriodsList(ListView):
    template_name = 'votings/all_periods.html'
    model = Period
    context_object_name = 'periods'

    def get_queryset(self):
        res = super().get_queryset()
        return res.order_by('-start', '-created')


class CollectionsList(ListView):
    template_name = 'votings/all_collections.html'
    model = VotingCollection
    context_object_name = 'collections'

    def get_queryset(self):
        res = super().get_queryset()
        return res.order_by('-time')


class SessionUpdate(UpdateView):
    model = VotingCollection
    fields = ('name', 'time', 'revision')
    template_name = 'votings/update_session.html'

    def get_success_url(self):
        return reverse('session_update', args=[self.object.id])

class SessionDetailView(DetailView):
    model = VotingCollection

    context_object_name = 'voting_session'
    template_name = 'votings/session_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        groups, option_map = get_groups_template(self.object)
        context['groups'] = groups
        context['option_map'] = option_map
        return context


class SessionDetailSuccess(SessionDetailView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['success'] = True
        return context


@transaction.atomic
def new_session(request):
    if request.method == 'GET':
        form = SessionForm()
    else:
        form = SessionForm(request.POST)
        if form.is_valid():
            parsed_collection = form.cleaned_data['collection']
            session = form.save(commit=False)
            session.name = parsed_collection.name
            session.save()
            add_votings(parsed_collection, session)
            return redirect('new_session_success', pk=session.id)
    return render(request, 'votings/new_session.html', {'form': form})


def success_session_delete(request):
    return render(request, 'votings/success_session_delete.html')


class SessionDelete(DeleteView):
    model = VotingCollection
    success_url = 'session_delete_success'
    template_name = 'votings/session_confirm_delete.html'


class SessionPrintView(DetailView):
    model = VotingCollection

    context_object_name = 'voting_session'
    template_name = 'votings/session_print.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        groups, option_map = get_groups_template(self.object)
        context['groups'] = groups
        context['option_map'] = option_map
        return context
