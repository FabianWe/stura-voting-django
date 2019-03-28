# MIT License
#
# Copyright (c) 2018, 2019 Fabian Wenzelmann
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

import datetime
from heapq import merge

from dateutil import relativedelta

from django.utils.timezone import make_aware
from django.utils import formats
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.http import HttpResponseBadRequest

# otherwise some really ugly import stuff
from . import models as voting_models
from . import results

from stura_voting_utils import SchulzeVotingSkeleton, MedianVotingSkeleton


def get_next_semester(reference_date=None):
    """
    Return the next semester time span.

    This function computes the closest semester time span. We assume that the year is divided into two semester:
    One from October 1 to March 31 and one from April 1 to September 30.
    It will return first a string, either 'winter' or 'summer' (which term it is) and two dates (start and end).

    If the reference_date is None it will use today as the reference day.

    This implementation is not very smart but it will get the job done.

    Args:
        reference_date (date): The date from which to compute the closest semester time span.

    Returns:
        tuple (str, date, date): Either 'winter' or 'summer' and the start and end of the closest semester time span.

    """
    if reference_date is None:
        reference_date = datetime.date.today()
    # we want the closest date, there are probably smarter ways of doing this, but well we don't care very much :)
    candidates = [('winter', datetime.date(month=10, day=1, year=reference_date.year-1), datetime.date(month=3, day=31, year=reference_date.year)),
                  ('winter', datetime.date(month=10, day=1, year=reference_date.year), datetime.date(month=3, day=31, year=reference_date.year + 1)),
                  ('winter', datetime.date(month=10, day=1, year=reference_date.year + 1), datetime.date(month=3, day=31, year=reference_date.year + 2)),
                  ('summer', datetime.date(month=4, day=1, year=reference_date.year-1), datetime.date(month=3, day=31, year=reference_date.year-1)),
                  ('summer', datetime.date(month=4, day=1, year=reference_date.year), datetime.date(month=9, day=30, year=reference_date.year)),
                  ('summer', datetime.date(month=4, day=1, year=reference_date.year + 1), datetime.date(month=9, day=30, year=reference_date.year + 1)),
    ]
    # now we have all candidates, check which one is closest to today
    min_delta = None
    best = None
    for (term, start, end) in candidates:
        diff = abs(start - reference_date)
        if min_delta is None or (diff < min_delta):
            min_delta = diff
            best = (term, start, end)
    return best


def get_semester_start(reference_date=None):
    """
    Return the start of the next semester time span.

    See get_next_semester for more details since this function only returns the second component of this function.

    Args:
        reference_date (date): The date from which to compute the closest semester time span.

    Returns:
        date: Start of the next semester time span.
    """
    return get_next_semester(reference_date)[1]


def get_semester_end(reference_date=None):
    """
    Return the end of the next semester time span.

    See get_next_semester for more details since this function only returns the third component of this function.

    Args:
        reference_date (date): The date from which to compute the closest semester time span.

    Returns:
        date: End of the next semester time span.
        """
    return get_next_semester(reference_date)[2]


def get_semester_name(reference_date=None):
    term, next_start, _ = get_next_semester(reference_date)
    if term == 'winter':
        return 'Wintersemester %d/%d' % (next_start.year, next_start.year+1)
    else:
        return 'Sommersemester %d' % next_start.year


def next_session_date(weekday, reference_date=None):
    if reference_date is None:
        reference_date = datetime.date.today()
    return reference_date + relativedelta.relativedelta(days=+1, weekday=weekday(+1))


def get_next_session_datetime(weekday, hour, minute, reference_date=None):
    date = next_session_date(weekday, reference_date)
    time = datetime.datetime(year=date.year, month=date.month, day=date.day,
                             hour=hour, minute=minute)
    # TODO check timezone stuff...
    return make_aware(time)


def get_next_session_name(weekday, reference_date=None, format='Sitzung vom %s'):
    date = next_session_date(weekday, reference_date)
    fmt_date = formats.date_format(date, 'DATE_FORMAT')
    return format % fmt_date


def get_next_session_stura():
    config = settings.VOTING_SESSIONS_CONFIG
    return get_next_session_datetime(config['weekday'], config['hour'], config['minute'])


def get_next_session_name_stura():
    config = settings.VOTING_SESSIONS_CONFIG
    return get_next_session_name(config['weekday'])


def add_votings(parsed_collection, collection_model):
    for group_num, group in enumerate(parsed_collection.groups):
        model_group = voting_models.VotingGroup.objects.create(name=group.name,
                                                 collection=collection_model,
                                                 group_num=group_num)
        for voting_num, skel in enumerate(group.get_votings()):
            if isinstance(skel, SchulzeVotingSkeleton):
                schulze_voting = voting_models.SchulzeVoting.objects.create(
                    name=skel.name,
                    voting_num=voting_num,
                    group=model_group,
                )
                # add all options
                for option_num, option in enumerate(skel.options):
                    voting_models.SchulzeOption.objects.create(
                        option=option,
                        option_num=option_num,
                        voting=schulze_voting,
                    )
            elif isinstance(skel, MedianVotingSkeleton):
                voting_models.MedianVoting.objects.create(
                    name=skel.name,
                    value=skel.value,
                    currency=skel.currency if skel.currency is not None else '€',
                    voting_num=voting_num,
                    group=model_group,
                )
            else:
                assert False


def get_groups_template(collection):
    # see GenericVotingResult.for_overview_template
    # also returns the warnings for the session
    median_votings = results.median_votings(collection)
    schulze_votings = results.schulze_votings(collection)
    merged = results.merge_voting_results(median_votings, schulze_votings)
    groups, option_map = merged.for_overview_template()
    return groups, option_map, merged.warnings


def get_instance(klass, obj, *args, **kwargs):
    if not isinstance(obj, klass):
        obj = get_object_or_404(klass, pk=obj, *args, **kwargs)
    return obj
