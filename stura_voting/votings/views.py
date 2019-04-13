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

from schulze_voting import evaluate_schulze

from django.shortcuts import render, reverse, redirect
from django.views.generic.detail import DetailView
from django.views.generic import ListView, UpdateView, CreateView
from django.views.generic.edit import DeleteView
from django.http import Http404
from django.db import transaction
from django.db.models import Max
from django.utils.translation import gettext
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin

from .results import *

# TODO when parsing inputs via our library, check lengths before inserting?

from .models import *
from .forms import *
from .utils import *

from .median import median_for_evaluation, single_median_statistics
from .schulze import schulze_for_evaluation, single_schulze_instance


# TODO which views should be atomic
# also see select_for_update

def index(request):
    return render(request, 'votings/index.html')


def copyright_view(request):
    return render(request, 'votings/copyright.html')


@login_required
def profile(request):
    return render(request, 'registration/profile.html')


def archive_index(request):
    return render(request, 'votings/archive.html',
                  {'periods': Period.objects.order_by('-start', '-created')[:10],
                   'collections': VotingCollection.objects.order_by('-time')[:10]})


@transaction.atomic
@permission_required(
    ('votings.change_votinggroup',
     'votings.change_medianvoting',
     'votings.change_schulzevoting'))
def edit_group_view(request, pk):
    group = get_object_or_404(VotingGroup, pk=pk)
    context = {'group': group}
    median_votings = results.median_votings(
        group=group, select_for_update=True)
    schulze_votings = results.schulze_votings(
        group=group, select_for_update=True)
    merged = results.CombinedVotingResult(median_votings, schulze_votings)
    context['median_votings'] = median_votings
    context['schulze_votings'] = schulze_votings
    context['votings'] = merged
    votings = list(merged.combined_votings())
    num_votings = len(votings)
    if request.method == 'GET':
        # store current order
        current_order = []
        for voting in votings:
            current_order.append(voting.voting_num)
        form = UpdateGroupForm(current_order=current_order)
    else:
        form = UpdateGroupForm(request.POST, num_votings=num_votings)
        if form.is_valid():
            new_order = form.cleaned_data['order']
            if new_order:
                assert len(new_order) == num_votings
                for voting, new_pos in zip(votings, new_order):
                    if voting.voting_num != new_pos:
                        voting.voting_num = new_pos
                        voting.save(update_fields=['voting_num'])
            return redirect('group_update', pk=pk)
    context['form'] = form
    groups, _ = list(merged.for_overview_template())
    if len(groups) == 0:
        context['votings_list'] = []
    elif len(groups) == 1:
        context['votings_list'] = groups[0][1]
    else:
        assert False
    return render(request, 'votings/group/group_detail.html', context)


class VotingDeleteView(DeleteView):
    # success_url = reverse_lazy('revision_delete_success')
    template_name = 'votings/voting/voting_confirm_delete.html'

    def get_success_url(self):
        return reverse('group_update', args=[self.object.group.id])


class MedianVotingDeleteView(PermissionRequiredMixin, VotingDeleteView):
    # permissions
    permission_required = 'votings.delete_medianvoting'

    model = MedianVoting

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        num_voters = MedianVote.objects.filter(voting=self.object).count()
        context['num_voters'] = num_voters
        return context


class SchulzeVotingDeleteView(PermissionRequiredMixin, VotingDeleteView):
    # permissions
    permission_required = 'votings.delete_schulzevoting'

    model = SchulzeVoting

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        num_voters = (SchulzeVote.objects.filter(option__voting=self.object)
                      .values_list('voter__id', flat=True)
                      .distinct()
                      .count())
        # without values_list sqlite does not work
        context['num_voters'] = num_voters
        return context


class MedianUpdateView(PermissionRequiredMixin, UpdateView):
    # permissions
    permission_required = 'votings.change_medianvoting'

    model = MedianVoting
    fields = ('name', 'majority', 'absolute_majority')

    context_object_name = 'voting'
    template_name = 'votings/voting/median_update.html'

    def get_success_url(self):
        return reverse(
            'session_detail', args=[
                self.object.group.collection.id])


class SchulzeUpdateView(PermissionRequiredMixin, UpdateView):
    # permissions
    permission_required = 'votings.change_schulzevoting'

    model = SchulzeVoting
    fields = ('name', 'majority', 'absolute_majority')

    context_object_name = 'voting'
    template_name = 'votings/voting/schulze_update.html'

    def get_success_url(self):
        return reverse(
            'session_detail', args=[
                self.object.group.collection.id])


@transaction.atomic
@permission_required(('votings.add_period', 'votings.add_votersrevision'))
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
                    Voter.objects.create(
                        revision=rev, name=voter.name, weight=voter.weight)
            return redirect('period_detail_success', pk=period.id)
    return render(request, 'votings/period/new_period.html', {'form': form})


class PeriodDetailView(DetailView):
    model = Period

    context_object_name = 'period'
    template_name = 'votings/period/period_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        period = context['period']
        revs = VotersRevision.objects.filter(
            period=period).order_by(
            '-period__start',
            '-period__created',
            '-created')
        context['revisions'] = revs
        collections = VotingCollection.objects.filter(
            revision__period=period).order_by('-time')
        context['collections'] = collections
        return context


class PeriodUpdateView(PermissionRequiredMixin, UpdateView):
    # permissions
    permission_required = 'votings.change_period'

    model = Period
    fields = ('start', 'end', 'name')
    template_name = 'votings/period/update_period.html'

    def get_success_url(self):
        return reverse('period_detail', args=[self.object.id])


class PeriodDetailSuccess(PermissionRequiredMixin, PeriodDetailView):
    # permissions
    permission_required = 'votings.add_period'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['success'] = True
        return context


@permission_required('votings.enter_collection_results')
def enter_voterlist(request, pk):
    collection = get_object_or_404(VotingCollection, pk=pk)
    with_vote_id = get_voters_with_vote(collection)
    all_voters = Voter.objects.filter(
        revision=collection.revision).order_by('name')
    with_vote = []
    without_vote = []
    for voter in all_voters:
        if voter.id in with_vote_id:
            with_vote.append(voter)
        else:
            without_vote.append(voter)
    context = {
        'collection': collection,
        'with_vote': with_vote,
        'without_vote': without_vote}
    return render(request, 'votings/session/enter_voterlist.html', context)


@transaction.atomic
@permission_required('votings.enter_collection_results')
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
        form = ResultsSingleVoterForm(
            request.POST, collection=collection, voter=voter)
        if form.is_valid():
            for v_type, v_id, val in form.votings():
                if v_type == 'median':
                    __handle_enter_median(form.median_result, v_id, val, voter)
                elif v_type == 'schulze':
                    __handle_enter_schulze(
                        form.schulze_result, v_id, val, voter)
                else:
                    assert False
    context['form'] = form
    # our methods might change the contents of schulze and median warnings, thus
    # the merged result does not contain all warnings, we merge them here again
    context['warnings'] = list(
        map(str, form.median_result.warnings + form.schulze_result.warnings))
    return render(request, 'votings/session/enter_single.html', context)


def __handle_enter_median(result, v_id, val, voter):
    # result: GenericVotingResult for median votes only
    # v_id id of the voting
    # val: None or tuple (value, currency)
    # first lookup voting and ensure it exists
    if v_id not in result.votings:
        msg = gettext(
            'Median voting with id %(voting)d does not exist, not saved' % {
                'voting': v_id,
            })
        warning = QueryWarning(msg)
        result.warnings.append(warning)
        return
    voting = result.votings[v_id]
    # if val is None (no entry and result exists: delete it)
    if not val:
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
    # result: GenericVotingResult for schulze votes only
    # v_id id of the voting
    # val: None or list of ints (the ranking)
    # in this code we do some sanity checks, just to be absolutely sure everything
    # is correct
    # first lookup voting and ensure it exists
    if v_id not in result.votings:
        msg = gettext(
            'Schulze voting with id %(voting)d does not exist, not saved' % {
                'voting': v_id,
            })
        warning = QueryWarning(msg)
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
            msg = gettext(
                'Schulze voting with id %(voting)d has no options, not saved' % {
                    'voting': v_id,
                })
            warning = QueryWarning(msg)
            result.warnings.append(warning)
            return
        voting_options = result.voting_description[v_id]
        if len(val) != len(voting_options):
            msg = gettext(
                'Invalid schulze result. Internal error? Result for voting %(voting)d not saved' % {
                    'voting': v_id})
            warning = QueryWarning(msg)
            result.warnings.append(warning)
            return
        if v_id in result.votes:
            # update
            current_votes = result.votes[v_id]
            # again, some sanity checks here...
            # before we only added warnings, but even options with warnings
            # got inserted. So now we prevent an update / insertion if something
            # is wrong
            if len(current_votes) != len(voting_options):
                msg = gettext(
                    'Number of options %(options)d does not match number of votes %(votes)d for voting %(voting)d. Not saved' % {
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
                    msg = gettext(
                        'Invalid vote for option for vote %(vote)d: Got vote for option %(option)d instead of %(for)d. Existing entries were deleted!' % {
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
                SchulzeVote.objects.create(sorting_position=ranking_pos,
                                           voter=voter,
                                           option=option)


@permission_required('votings.add_votersrevision')
def revision_success(request, pk):
    rev = get_object_or_404(VotersRevision, pk=pk)
    return render(request,
                  'votings/revision/success_revision.html',
                  {'revision': rev})


@transaction.atomic
@permission_required('votings.add_votersrevision')
def new_revision(request):
    if request.method == 'GET':
        form = RevisionForm()
    else:
        form = RevisionForm(request.POST)
        if form.is_valid():
            rev = form.save()
            if form.cleaned_data['voters']:
                for voter in form.cleaned_data['voters']:
                    Voter.objects.create(
                        revision=rev, name=voter.name, weight=voter.weight)
            return redirect('new_revision_success', pk=rev.id)
    return render(request,
                  'votings/revision/new_revision.html',
                  {'form': form})


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
        context['voters'] = voters
        return context


class RevisionDeleteView(PermissionRequiredMixin, DeleteView):
    # permissions
    permission_required = 'votings.delete_votersrevision'

    model = VotersRevision
    success_url = reverse_lazy('revision_delete_success')
    template_name = 'votings/revision/revision_confirm_delete.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        num_sessions = VotingCollection.objects.filter(
            revision=self.object).count()
        context['num_sessions'] = num_sessions
        return context


@permission_required('votings.delete_votersrevision')
def revision_delete_success_view(request):
    return render(request, 'votings/revision/revision_success_delete.html')


class PeriodDeleteView(PermissionRequiredMixin, DeleteView):
    # permissions
    permission_required = 'votings.delete_period'

    model = Period
    success_url = reverse_lazy('period_delete_success')
    template_name = 'votings/period/period_confirm_delete.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        num_revisions = VotersRevision.objects.filter(
            period=self.object).count()
        context['num_revisions'] = num_revisions
        num_sessions = VotingCollection.objects.filter(
            revision__period=self.object).count()
        context['num_sessions'] = num_sessions
        return context


@permission_required('votings.delete_period')
def period_delete_success_view(request):
    return render(request, 'votings/period/period_success_delete.html')


@transaction.atomic
@permission_required('votings.change_votersrevision')
def update_revision_view(request, pk):
    revision = get_object_or_404(VotersRevision, pk=pk)
    voters = Voter.objects.filter(
        revision=revision).order_by('name').select_for_update()
    if request.method == 'GET':
        form = RevisionUpdateForm(voters=voters)
    else:
        form = RevisionUpdateForm(request.POST, voters=voters)
        if form.is_valid():
            transmitted_voters = form.cleaned_data['voters']
            update_summary = __update_voters(
                voters, transmitted_voters, revision)
            # render success template and show information about what happend
            context = {'revision': revision, 'update_summary': update_summary}
            return render(
                request,
                'votings/revision/revision_update_success.html',
                context)
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
                entry = gettext(
                    'Changed weight for %(voter)s from %(old)d to %(new)d' % {
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
                            'voter': new_voter_name, 'weight': new_voter.weight, })
            summary.append(entry)
            Voter.objects.create(
                revision=revision,
                name=new_voter_name,
                weight=new_voter.weight)
    # now iterate over all old entries.
    # the entries not in the new list can be deleted
    # we could probably just delete with a single query with name__in = ...
    # but because we already locked the db... I'm not sure if this works as we
    # would like, so each one gets a single delete
    for old_voter_name, old_voter in old.items():
        if old_voter_name not in new:
            # delete
            entry = gettext('Delete voter %(voter)s' %
                            {'voter': old_voter_name})
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


class SessionUpdate(PermissionRequiredMixin, UpdateView):
    # permissions
    permission_required = 'votings.change_votingcollection'

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


class SessionDetailSuccess(PermissionRequiredMixin, SessionDetailView):
    # permissions
    permission_required = 'votings.add_votingcollection'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['success'] = True
        return context


@transaction.atomic
@permission_required('votings.add_votingcollection')
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


@permission_required('votings.delete_votingcollection')
def success_session_delete(request):
    return render(request, 'votings/session/success_session_delete.html')


class SessionDelete(PermissionRequiredMixin, DeleteView):
    # permissions
    permission_required = 'votings.delete_votingcollection'

    model = VotingCollection
    success_url = reverse_lazy('session_delete_success')
    template_name = 'votings/session/session_confirm_delete.html'


@transaction.atomic
def session_votes_list(request, pk):
    collection = get_object_or_404(VotingCollection, pk=pk)
    all_voters = Voter.objects.filter(
        revision=collection.revision).order_by('name')

    # get all votings + results
    median = median_for_evaluation(collection)
    # fill missing votes with None
    median.fill_missing_voters(all_voters)
    schulze = schulze_for_evaluation(collection)
    schulze.fill_missing_voters(all_voters)

    merged = CombinedVotingResult(median, schulze)

    group_data = for_votes_list_template(merged)

    warnings = list(map(str, merged.warnings))
    context = {'groups': group_data, 'voters': all_voters,
               'collection': collection, 'warnings': warnings}

    return render(request, 'votings/votes/votes_list.html', context)


def session_results_generalized_view(request, pk, show_votes):
    collection = get_object_or_404(VotingCollection, pk=pk)
    all_voters = (Voter.objects
                  .filter(revision=collection.revision)
                  .select_related('revision')
                  .order_by('name'))
    # required for results methods
    voters_map = dict()
    for voter in all_voters:
        voters_map[voter.id] = voter

    # get all votings + results
    median = median_for_evaluation(collection)
    # fill missing votes with None
    median.fill_missing_voters(all_voters)
    schulze = schulze_for_evaluation(collection)
    schulze.fill_missing_voters(all_voters)

    merged = CombinedVotingResult(median, schulze)

    # create the results objects for evaluation, we store them in a map, we
    # might use this in a template
    median_instances = OrderedDict()
    for median_v_id, median_v in median.votings.items():
        instance = single_median_statistics(
            median_v, median.votes[median_v_id], voters_map)
        median_instances[median_v_id] = instance
    # same for schulze
    schulze_instances = OrderedDict()
    for schulze_v_id, schulze_v in schulze.votings.items():
        instance = single_schulze_instance(
            schulze_v,
            schulze.votes[schulze_v_id],
            schulze.voting_description[schulze_v_id],
            voters_map)
        schulze_instances[schulze_v_id] = instance

    median_results = dict()
    for median_id, gen_instance in median_instances.items():
        median_results[median_id] = gen_instance.instance.median(
            votes_required=gen_instance.majority)

    schulze_results = dict()
    # also map to list of how many voters (weights) ranked an option before no
    schulze_num_no = dict()
    schulze_percent_no = dict()
    for schulze_id, gen_instance in schulze_instances.items():
        schulze_votes = gen_instance.instance
        n = len(schulze.voting_description[schulze_id])
        s_res = evaluate_schulze(schulze_votes, n)
        schulze_results[schulze_id] = s_res
        num, percent = __votes_before_no(s_res, gen_instance.weight_sum)
        schulze_num_no[schulze_id] = num
        schulze_percent_no[schulze_id] = percent

    group_data = for_votes_list_template(merged)

    warnings = list(map(str, merged.warnings))
    context = {
        'show_votes': show_votes,
        'voters': all_voters,
        'collection': collection,
        'warnings': warnings,
        'median_results': median_results,
        'schulze_results': schulze_results,
        'groups': group_data,
        'median_instances': median_instances,
        'schulze_instances': schulze_instances,
        'median_votings': median,
        'schulze_votings': schulze,
        'schulze_num_no': schulze_num_no,
        'schulze_percent_no': schulze_percent_no}

    return render(request, 'votings/results/session_results.html', context)


def __votes_before_no(schulze_res, weight_sum):
    num = []
    percent = []
    for i in range(len(schulze_res.d)):
        entry = schulze_res.d[i][-1]
        num.append(entry)
        if weight_sum:
            percent.append((entry / weight_sum) * 100.0)
        else:
            percent.append(0.0)

    return num, percent


@transaction.atomic
def session_results_view(request, pk):
    return session_results_generalized_view(request, pk, False)


@transaction.atomic
def session_results_votes_view(request, pk):
    return session_results_generalized_view(request, pk, True)


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


def _get_max_voting_num(group):

    max_median = (MedianVoting.objects.filter(group=group)
                  .aggregate(Max('voting_num')))
    # get actual value
    max_median = max_median['voting_num__max']
    res = -1
    if max_median is not None:
        res = max_median
    max_schulze = (SchulzeVoting.objects.filter(group=group)
                   .aggregate(Max('voting_num')))
    # again the actual value
    max_schulze = max_schulze['voting_num__max']
    if max_schulze is not None:
        res = max(res, max_schulze)
    return res


class MedianVotingCreateView(PermissionRequiredMixin, CreateView):
    # permissions
    permission_required = 'votings.add_medianvoting'

    model = MedianVoting
    fields = ['name', 'value', 'majority', 'absolute_majority', 'currency']
    template_name = 'votings/voting/median_create.html'

    @method_decorator(transaction.atomic)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def form_valid(self, form):
        instance = form.instance
        # get group
        pk = self.kwargs['pk']
        group = get_object_or_404(VotingGroup, pk=pk)
        self.group = group
        max_voting_num = _get_max_voting_num(group)
        next_voting_num = max_voting_num + 1
        instance.group = group
        instance.voting_num = next_voting_num
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('group_update', args=[self.group.id])


@transaction.atomic
@permission_required('votings.add_schulzevoting')
def create_schulze_view(request, pk):
    if request.method == 'GET':
        form = SchulzeVotingCreateForm()
    else:
        form = SchulzeVotingCreateForm(request.POST)
        if form.is_valid():
            group = get_object_or_404(VotingGroup, pk=pk)
            voting = form.save(commit=False)
            voting.group = group
            max_voting_num = _get_max_voting_num(group)
            next_voting_num = max_voting_num + 1
            voting.voting_num = next_voting_num
            voting.save()
            options = form.cleaned_data['options']
            for option_num, option in enumerate(options):
                SchulzeOption.objects.create(
                    option=option,
                    option_num=option_num,
                    voting=voting,
                )
    return render(request,
                  'votings/voting/schulze_create.html',
                  {'form': form})
