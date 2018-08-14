from django.shortcuts import render

# Create your views here.

from django.http import HttpResponse

from .forms import PeriodForm


def index(request):
    return render(request, 'votings/index.html')


def new_period(request):
    if request.method == 'GET':
        form = PeriodForm()
    else:
        form = PeriodForm(request.POST)
        if form.is_valid():
            period = form.save()
            return render(request, 'votings/success_period.html', {'period': period.name})
    return render(request, 'votings/new_period.html', {'form': form})
