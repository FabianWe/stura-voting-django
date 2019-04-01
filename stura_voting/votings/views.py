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

from django.shortcuts import render, reverse, redirect
from django.views.generic.detail import DetailView
from django.views.generic import ListView, UpdateView
from django.views.generic.edit import DeleteView
from django.http import Http404
from django.db import transaction
from django.utils.translation import gettext
from django.urls import reverse_lazy

from .results import *

# TODO when parsing inputs via our library, check lengths before inserting?

from .models import *
from .forms import *
from .utils import *

# TODO which views should be atomic
# also see select_for_update

def index(request):
    return render(request, 'votings/index.html')

def copyright_view(request):
    return render(request, 'votings/copyright.html')


def archive_index(request):
    return render(request, 'votings/archive.html',
             {'periods': Period.objects.order_by('-start', '-created')[:10],
              'collections': VotingCollection.objects.order_by('-time')[:10]})


@transaction.atomic
def edit_group_view(request, pk):
    group = get_object_or_404(VotingGroup, pk=pk)
    context = {'group': group}
    median_votings = results.median_votings(group=group)
    schulze_votings = results.schulze_votings(group=group)
    merged = results.merge_voting_results(median_votings, schulze_votings)
    context['median_votings'] = median_votings
    context['schulze_votings'] = schulze_votings
    context['votings'] = merged
    # TODO use a form.
    return render(request, 'votings/group/group_detail.html', context)


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
    return render(request, 'votings/period/new_period.html', {'form': form})


class PeriodDetailView(DetailView):
    model = Period

    context_object_name = 'period'
    template_name = 'votings/period/period_detail.html'

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
    template_name = 'votings/period/update_period.html'

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
    return render(request, 'votings/session/enter_voterlist.html', context)


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
    return render(request, 'votings/session/enter_single.html', context)


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
            if entry.value != val[0]:
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
                if vote.sorting_position != new_pos:
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
    return render(request, 'votings/revision/success_revision.html', {'revision': rev})


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
    return render(request, 'votings/revision/new_revision.html', {'form': form})


class PeriodsList(ListView):
    template_name = 'votings/period/all_periods.html'
    model = Period
    context_object_name = 'periods'

    def get_queryset(self):
        res = super().get_queryset()
        return res.order_by('-start', '-created')


class RevisionDetailView(DetailView):
    model = VotersRevision

    template_name = 'votings/revision/revision_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        voters = Voter.objects.filter(revision=self.object).order_by('name')
        context['voters'] = list(voters)
        return context

class RevisionDeleteView(DeleteView):
    model = VotersRevision
    success_url = reverse_lazy('revision_delete_success')
    template_name = 'votings/revision/revision_confirm_delete.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        num_sessions = VotingCollection.objects.filter(revision=self.object).count()
        context['num_sessions'] = num_sessions
        return context


def revision_delete_success_view(request):
    return render(request, 'votings/revision/revision_success_delete.html')

class PeriodDeleteView(DeleteView):
    model = Period
    success_url = reverse_lazy('period_delete_success')
    template_name = 'votings/period/period_confirm_delete.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        num_revisions = VotersRevision.objects.filter(period=self.object).count()
        context['num_revisions'] = num_revisions
        num_sessions = VotingCollection.objects.filter(revision__period=self.object).count()
        context['num_sessions'] = num_sessions
        return context


def period_delete_success_view(request):
    return render(request, 'votings/period/period_success_delete.html')


@transaction.atomic
def update_revision_view(request, pk):
    revision = get_object_or_404(VotersRevision, pk=pk)
    voters = Voter.objects.filter(revision=revision).order_by('name').select_for_update()
    if request.method == 'GET':
        form = RevisionUpdateForm(voters=voters)
    else:
        form = RevisionUpdateForm(request.POST, voters=voters)
        if form.is_valid():
            transmitted_voters = form.cleaned_data['voters']
            update_summary = __update_voters(voters, transmitted_voters, revision)
            # render success template and show information about what happend
            context = {'revision': revision, 'update_summary': update_summary}
            return render(request, 'votings/revision/revision_update_success.html', context)
    num_sessions = VotingCollection.objects.filter(revision=revision).count()
    return render(request, 'votings/revision/revision_update.html', {
        'revision': revision,
        'form': form,
        'voters': voters,
        'num_sessions': num_sessions})


def __update_voters(old_voters, new_voters, revision):
    summary = []
    # old_voters: instances of all voters in revision, from database
    # new_voters: parsed from the input, so WeightedVoter objects (from stura-voting-utils)
    # we transform both to dicts, this makes updates easier
    old, new = dict(), dict()
    for v in old_voters:
        old[v.name] = v
    for v in new_voters:
        new[v.name] = v
    # iterate over all new voters
    # either we have a new entry or we update an existing one
    for new_voter_name, new_voter in new.items():
        if new_voter_name in old:
            old_voter = old[new_voter_name]
            if new_voter.weight != old_voter.weight:
                # update
                entry = gettext('Changed weight for %(voter)s from %(old)d to %(new)d' % {
                    'voter': new_voter_name,
                    'old': old_voter.weight,
                    'new': new_voter.weight,
                })
                summary.append(entry)
                old_voter.weight = new_voter.weight
                old_voter.save(update_fields=['weight'])
        else:
            # insert
            entry = gettext('Inserted new voter %(voter)s with weigth %(weight)d' % {
                'voter': new_voter_name,
                'weight': new_voter.weight,
            })
            summary.append(entry)
            Voter.objects.create(revision=revision, name=new_voter_name, weight=new_voter.weight)
    # now iterate over all old entries.
    # the entries not in the new list can be deleted
    # we could probably just delete with a single query with name__in = ...
    # but because we already locked the db... I'm not sure if this works as we
    # would like, so each one gets a single delete
    for old_voter_name, old_voter in old.items():
        if old_voter_name not in new:
            # delete
            entry = gettext('Delete voter %(voter)s' % {'voter': old_voter_name})
            summary.append(entry)
            old_voter.delete()
    return summary


class SessionsList(ListView):
    template_name = 'votings/session/all_sessions.html'
    model = VotingCollection
    context_object_name = 'collections'

    def get_queryset(self):
        res = super().get_queryset()
        return res.order_by('-time')


class SessionUpdate(UpdateView):
    model = VotingCollection
    fields = ('name', 'time')
    template_name = 'votings/session/update_session.html'

    def get_success_url(self):
        return reverse('session_update', args=[self.object.id])

class SessionDetailView(DetailView):
    model = VotingCollection

    context_object_name = 'voting_session'
    template_name = 'votings/session/session_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        groups, option_map, warnings = get_groups_template(self.object)
        context['groups'] = groups
        context['option_map'] = option_map
        context['warnings'] = list(map(str, warnings))
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
    return render(request, 'votings/session/new_session.html', {'form': form})


def success_session_delete(request):
    return render(request, 'votings/session/success_session_delete.html')


class SessionDelete(DeleteView):
    model = VotingCollection
    success_url = reverse_lazy('session_delete_success')
    template_name = 'votings/session/session_confirm_delete.html'


class SessionPrintView(DetailView):
    model = VotingCollection

    context_object_name = 'voting_session'
    template_name = 'votings/session/session_print.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        groups, option_map, _ = get_groups_template(self.object)
        context['groups'] = groups
        context['option_map'] = option_map
        return context
