from django.shortcuts import render
from django.views.generic.detail import DetailView
from django.views.generic import ListView

# Create your views here.

from .models import VotersRevision, Voter, Period, VotingCollection
from .forms import PeriodForm, RevisionForm, SessionForm


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
            # TODO do stuff, fix success_session
            return render(request, 'votings/success_session.html')
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