from django.shortcuts import render
from django.views.generic.detail import DetailView

# Create your views here.

from .models import VotersRevision, Voter, Period
from .forms import PeriodForm, RevisionForm


def index(request):
    return render(request, 'votings/index.html')


def archive_index(request):
    return render(request, 'votings/archive.html', {'periods': Period.objects.order_by('created')[:10]})


class PeriodDetailView(DetailView):
    model = Period

    context_object_name = 'period'
    template_name = 'votings/period_detail.html'


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