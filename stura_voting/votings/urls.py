from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('period/new', views.new_period, name='new_period'),
    path('revision/new', views.new_revision, name='new_revision'),
    path('archive', views.archive_index, name='archive_index'),
    path('period/<int:pk>/', views.PeriodDetailView.as_view(), name='period_detail'),
    path('periods/', views.PeriodsList.as_view(), name='periods_list'),
    path('sesions/', views.CollectionsList.as_view(), name='collections_list'),
    path('session/new', views.new_session, name='new_session'),
]
