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

from django.shortcuts import render, reverse, get_object_or_404, redirect
from django.views.generic.detail import DetailView
from django.views.generic import ListView, UpdateView
from django.views.generic.edit import DeleteView
from django.http import HttpResponseBadRequest, Http404

# TODO when parsing inputs via our library, check lengths before inserting?

from .models import *
from .forms import PeriodForm, RevisionForm, SessionForm, EnterResultsForm, ResultsSingleVoterForm
from .utils import *
# from .results import *


def index(request):
    return render(request, 'votings/index.html')


def archive_index(request):
    return render(request, 'votings/archive.html',
             {'periods': Period.objects.order_by('-start', '-created')[:10],
              'collections': VotingCollection.objects.order_by('-time')[:10]})


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

def enter_single_voter_view(request, coll, v):
    collection = get_object_or_404(VotingCollection, pk=coll)
    voter = get_object_or_404(Voter, pk=v)
    context = {'collection': collection, 'voter': voter}
    if voter.revision != collection.revision:
        return HttpResponseBadRequest('Fooo')
    if request.method == 'GET':
        form = ResultsSingleVoterForm(collection=collection)
    else:
        form = ResultsSingleVoterForm(request.POST, collection=collection)
        if form.is_valid():
            print(form.cleaned_data)
    context['form'] = form
    return render(request, 'votings/enter_single.html', context)

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


def revision_success(request, pk):
    rev = get_object_or_404(VotersRevision, pk=pk)
    return render(request, 'votings/success_revision.html', {'period': rev.period.name})


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


# TODO remove once net method is there
def enter_results_view(request, pk):
    session = get_object_or_404(VotingCollection, pk=pk)
    if request.method == 'GET':
        last_voter_id = request.GET.get('last_voter', None)
        if last_voter_id is not None:
            try:
                last_voter_id = int(last_voter_id)
            except ValueError:
                # we don't care about an error
                pass
        form = EnterResultsForm(session=session, last_voter_id=last_voter_id)
    else:
        form = EnterResultsForm(request.POST, session=session)
        if form.is_valid():
            voter = form.cleaned_data['voter']
            # add results
            errors = []
            for v_type, v_id, val in filter(lambda x: x[2] is not None, form.votings()):
                if v_type == 'median':
                    try:
                        res = insert_median_vote(val[0], voter, v_id)
                        if isinstance(res, HttpResponseBadRequest):
                            errors.append(res)
                    except Http404 as e:
                        errors.append(e)
                else:
                    assert v_type == 'schulze'
                    try:
                        res = insert_schulze_vote(val, voter, v_id)
                        if isinstance(res, HttpResponseBadRequest):
                            errors.append(res)
                    except Http404 as e:
                        errors.append(e)
            if errors:
                errors_joined = '\n'.join(str(err) for err in errors)
                error_txt = 'There were errors while adding some votes, please check the result carefully!\n\n' + errors_joined
                return HttpResponseBadRequest(error_txt)
            # TODO return?
            # TODO was tun, wenn schon Eintragungen existieren?
            # Irgendwie noch nicht perfekt...
    return render(request, 'votings/enter_results.html', {'form': form})


# def votes_for_json(collection, voter):
#     collection = get_instance(VotingCollection, collection)
#     voter = get_instance(Voter, voter)
#     # get all votes for the collection where voter has voted
#     median_votes = MedianVote.objects.filter(voting__group__collection=collection)
#     # TODO schulze
#     res = dict()
#     for vote in median_votes:
#         id = EnterResultsForm.median_field_prefix + str(vote.id)
