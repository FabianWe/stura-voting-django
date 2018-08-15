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

from django.shortcuts import render, reverse
from django.views.generic.detail import DetailView
from django.views.generic import ListView, UpdateView
from django.views.generic.edit import DeleteView

# TODO when parsing inputs via our library, check lengths before inserting?

from .models import *
from .forms import PeriodForm, RevisionForm, SessionForm
from .utils import add_votings, get_groups_template


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
        # TODO is this even working?
        collections = VotingCollection.objects.filter(revision__period=period).order_by('-time')
        context['collections'] = collections
        return context


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
            return render(request, 'votings/success_period.html', {'period': period.name})
    return render(request, 'votings/new_period.html', {'form': form})


def new_revision(request):
    if request.method == 'GET':
        form = RevisionForm()
    else:
        form = RevisionForm(request.POST)
        if form.is_valid():
            rev = form.save()
            for voter in form.cleaned_data['voters']:
                Voter.objects.create(revision=rev, name=voter.name, weight=voter.weight)
            return render(request, 'votings/success_revision.html', {'period': rev.period.name})
    return render(request, 'votings/new_revision.html', {'form': form})


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
            return render(request, 'votings/success_session.html', {'voting_session': session})
    return render(request, 'votings/new_session.html', {'form': form})


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
