from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('period/new', views.new_period, name='new_period')
]
