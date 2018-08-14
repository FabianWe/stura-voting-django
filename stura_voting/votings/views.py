from django.shortcuts import render

# Create your views here.

from .models import VotersRevision, Voter
from .forms import PeriodForm, RevisionForm


def index(request):
    return render(request, 'votings/index.html')


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
        pass
    return render(request, 'votings/new_revision.html', {'form': form})