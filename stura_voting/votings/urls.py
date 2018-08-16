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

from django.urls import path

from . import views

urlpatterns = [
    # TODO singular / plural?
    path('', views.index, name='index'),
    path('period/new', views.new_period, name='new_period'),
    path('revision/new', views.new_revision, name='new_revision'),
    path('archive', views.archive_index, name='archive_index'),
    path('period/<int:pk>/', views.PeriodDetailView.as_view(), name='period_detail'),    path('periods/', views.PeriodsList.as_view(), name='periods_list'),
    path('sesions/', views.CollectionsList.as_view(), name='collections_list'),
    path('session/new', views.new_session, name='new_session'),
    path('session/<int:pk>/edit/', views.SessionUpdate.as_view(), name='session_update'),
    path('session/<int:pk>/', views.SessionDetailView.as_view(), name='session_detail'),
    path('session/delete/success/', views.success_session_delete, name='session_delete_success'),
    path('session/delete/<int:pk>/', views.SessionDelete.as_view(), name='session_delete'),
    path('session/<int:pk>/print/', views.SessionPrintView.as_view(), name='session_print'),
    path('session/<int:pk>/results/', views.enter_results_view, name='session_results'),
]
