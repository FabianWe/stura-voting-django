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

from django.urls import path

from . import views

urlpatterns = [
    # TODO singular / plural?
    path('', views.index, name='index'),
    path('copyright/', views.copyright_view, name='copyright'),
    path('period/new', views.new_period, name='new_period'),
    path('revision/new', views.new_revision, name='new_revision'),
    path('revision/<int:pk>/success/', views.revision_success, name='new_revision_success'),
    path('revision/<int:pk>/edit/', views.update_revision_view, name='revision_update'),
    path('revision/<int:pk>/delete/', views.RevisionDeleteView.as_view(), name='revision_delete'),
    path('revision/delete/success/', views.revision_delete_success_view, name='revision_delete_success'),
    path('revision/<int:pk>/', views.RevisionDetailView.as_view(), name='revision_detail'),
    path('archive', views.archive_index, name='archive_index'),
    path('period/<int:pk>/edit/', views.PeriodUpdateView.as_view(), name='period_update'),
    path('period/<int:pk>/', views.PeriodDetailView.as_view(), name='period_detail'),
    path('periods/', views.PeriodsList.as_view(), name='periods_list'),
    path('period/<int:pk>/success', views.PeriodDetailSuccess.as_view(), name='period_detail_success'),
    path('sessions/', views.SessionsList.as_view(), name='collections_list'),
    path('session/new', views.new_session, name='new_session'),
    path('session/<int:pk>/edit/', views.SessionUpdate.as_view(), name='session_update'),
    path('session/<int:pk>/', views.SessionDetailView.as_view(), name='session_detail'),
    path('session/<int:pk>/success', views.SessionDetailSuccess.as_view(), name='new_session_success'),
    path('session/delete/success/', views.success_session_delete, name='session_delete_success'),
    path('session/<int:pk>/delete/', views.SessionDelete.as_view(), name='session_delete'),
    path('session/<int:pk>/print/', views.SessionPrintView.as_view(), name='session_print'),
    path('session/<int:pk>/voters/', views.enter_voterlist, name='enter_voterslist'),
    path('session/<int:coll>/voters/<int:v>/', views.enter_single_voter_view, name='enter_single_voter'),
]
