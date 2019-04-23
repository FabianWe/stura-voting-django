# -*- coding: utf-8 -*-

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

"""This modul defines some utility functions that might be handy.

"""

import datetime

from dateutil import relativedelta

from django.utils.timezone import make_aware
from django.utils import formats
from django.conf import settings
from django.shortcuts import get_object_or_404

# otherwise some really ugly import issues
from . import models as voting_models
from . import results
from . fraction import *

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
    # we want the closest date, there are probably smarter ways of doing this,
    # but well we don't care very much :)
    candidates = [
        ('winter',
         datetime.date(
             month=10,
             day=1,
             year=reference_date.year - 1),
            datetime.date(
             month=3,
             day=31,
             year=reference_date.year)),
        ('winter',
         datetime.date(
             month=10,
             day=1,
             year=reference_date.year),
         datetime.date(
             month=3,
             day=31,
             year=reference_date.year + 1)),
        ('winter',
         datetime.date(
             month=10,
             day=1,
             year=reference_date.year + 1),
         datetime.date(
             month=3,
             day=31,
             year=reference_date.year + 2)),
        ('summer',
         datetime.date(
             month=4,
             day=1,
             year=reference_date.year - 1),
         datetime.date(
             month=3,
             day=31,
             year=reference_date.year - 1)),
        ('summer',
         datetime.date(
             month=4,
             day=1,
             year=reference_date.year),
         datetime.date(
             month=9,
             day=30,
             year=reference_date.year)),
        ('summer',
         datetime.date(
             month=4,
             day=1,
             year=reference_date.year + 1),
         datetime.date(
             month=9,
             day=30,
             year=reference_date.year + 1)),
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

    """Returns the name of the next semester as computed by get_next_semester.

    Args:
        reference_date (date): The date from which to compute the closest semester time span.

    Returns:
        str: The formatted name of the next semester.
    """
    term, next_start, _ = get_next_semester(reference_date)
    if term == 'winter':
        return 'Wintersemester %d/%d' % (next_start.year, next_start.year + 1)
    else:
        return 'Sommersemester %d' % next_start.year


def next_session_date(weekday, reference_date=None):
    """Computes the next session day given the weekday on which the session takes place.
    The weekday is used from the dateutil package, so for example you would use
    dateutil.relativedelta.TH.

    Args:
        weekday: Weekday from dateutil.relativedelta.
        reference_date (date): The reference date from which to compute the next session,
            the default is datetime.date.today().

    Returns:
        datetime.datetime: The date of the next session.
    """
    if reference_date is None:
        reference_date = datetime.date.today()
    return reference_date + \
        relativedelta.relativedelta(days=+1, weekday=weekday(+1))


def get_next_session_datetime(weekday, hour, minute, reference_date=None):
    """Returns the datetime (with date, hour and minute) as computed by next_session_date.

    That is it computes next_session_date and adds hour and minute information.
    The returned result is wrapped by make_aware from Django.

    Args:
        weekday: Weekday from dateutil.relativedelta.
        hour: The hour of the session (in the current timezone).
        minute: The minutes of the session (in the current timezone).
        reference_date (date): The reference date from which to compute the next session,
            the default is datetime.date.today().

    Returns:
        datetime.datetime: Returns an aware datetime that represents the date of the next
        session (with hours and minutes).
    """
    date = next_session_date(weekday, reference_date)
    time = datetime.datetime(year=date.year, month=date.month, day=date.day,
                             hour=hour, minute=minute)
    # TODO check timezone stuff...
    return make_aware(time, is_dst=True)


def get_next_session_name(
        weekday,
        reference_date=None,
        format='Sitzung vom %s'):
    """Returns the formatted Name of the next session.

    The format is used the format the result, it defaults to 'Sitzung vom %s'.
    The format must have one placeholder that accepts the formatted date.
    The date is formatted with formats.date_format from Django.
    Probably we should use a lazy_gettext or something like this instead.

    Args:
        weekday: Weekday from dateutil.relativedelta.
        reference_date (date): The reference date from which to compute the next session,
            the default is datetime.date.today().
        format (str): The format for the result, must contain one placeholder %s that is
        replaced by the foratted date.

    Returns:
        str: The formated session name.
    """
    date = next_session_date(weekday, reference_date)
    fmt_date = formats.date_format(date, 'DATE_FORMAT')
    return format % fmt_date


def get_next_session_stura():
    """Returns the datetime (with date, hour and minute) as computed by next_session_date
    given the settings in VOTING_SESSIONS_CONFIG in the settings file.
    That is it looksup 'weekday', 'hour' and 'minute' from the config and applies
    get_next_session_datetime. The default reference date is used.

    Used as the model default function.

    Returns:
        datetime.datetime: Returns an aware datetime that represents the date of the next
        session (with hours and minutes).
    """
    config = settings.VOTING_SESSIONS_CONFIG
    return get_next_session_datetime(
        config['weekday'],
        config['hour'],
        config['minute'])


def get_next_session_name_stura():
    """Returns the session name as computed by get_next_session_name given the settings
    in VOTING_SESSIONS_CONFIG in the settings file. That is it looksup 'weekday' from the config.
    The default reference date and formats are used.

    Used as the model default function.

    Returns:
        str: The formated session name.
    """
    config = settings.VOTING_SESSIONS_CONFIG
    return get_next_session_name(config['weekday'])


def compute_majority(majority, votes_sum):
    # majority: either a fraction <= 1 or a model description for a fraction:
    # FIFTY_MAJORITY or TWO_THIRDS_MAJORITY
    """Computes the majority required for a vote.

    majority must either be a Fraction instance <= (for example 1/2) or a description string.
    The string must be one of the constants FIFTY_MAJORITY or TWO_THIRDS_MAJORITY as defined
    in the models.
    In order to avoid rounding errors with floating point numbers a majority is based on
    fractions.
    It computes the number of votes required given the sum of all votes.
    For example: 51 voters and majority 1/2 ==> 25, that is > 25 votes are required.

    Args:
        majority (Fraction or str): A fraction <= 1 or a string description from the models
            module. 1/2 would mean that more than 0.5 * votes_sum votes are required.
        votes_sum: The number of voting weights to compute the majority from (for example
            51 voters each with weight 1).

    Returns:
        int: The number of votes required for a majority.
    """
    if not isinstance(majority, Fraction):
        if majority == voting_models.FIFTY_MAJORITY:
            majority = Fraction(1, 2)
        elif majority == voting_models.TWO_THIRDS_MAJORITY:
            majority = Fraction(2, 3)
        else:
            raise ValueError('Invalid majority description %s' % str(majority))
    required_fraction = majority * Fraction(votes_sum, 1)
    votes_required, _ = required_fraction.split()
    return votes_required


def add_votings(parsed_collection, collection_model):
    """Inserts all voting instances for a parsed collection.

    The parsed collection must be an instance of stura_voting_utils.VotingCollection
    (for example obtained from stura_voting_utils.parse_voting_collection).
    It adds all MedianVoting and SchulzeVoting (with options) to the collection.
    The collection ust be an models.VotingCollection instance already saved to the database.
    It creates all groups and votings.

    Args:
        parsed_collection (stura_voting_utils.VotingCollection): The generic instance
            containing all groups and votings.
        collection_model (VotingCollection): The instance from models, already saved to the
            database.
    """
    for group_num, group in enumerate(parsed_collection.groups):
        model_group = voting_models.VotingGroup.objects.create(
            name=group.name, collection=collection_model, group_num=group_num)
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


def get_groups_template(collection, empty_groups=False):
    """Returns all groups and voting information to be used inside the session views.

     It will do the following: It queries all votings for the given collection with
     results.median_votings and results.schulze_votings. The results are merged with
     results.CombinedVotingResult. See details for that methods for more details.

     It returns the groups and option_map from CombinedVotingResult.for_overview_template
     and the combined warnings.

     Note that empty groups will not be present, if you want to force empty groups to
     appear use empty_groups=True.

    Args:
        collection (VotingCollection): The voting collection to gather the results for.
        empty_groups (bool): If true all groups will be fetched, even those without a voting.
            Defaults to False.

    Returns:
        groups, option_map, list of warnings: See CombinedVotingResult.for_overview_template.
    """
    median_votings = results.median_votings(collection=collection)
    schulze_votings = results.schulze_votings(collection=collection)
    merged = results.CombinedVotingResult(median_votings, schulze_votings)
    groups, option_map = None, None
    if empty_groups:
        groups, option_map = merged.for_overview_template(all_groups=collection)
    else:
        groups, option_map = merged.for_overview_template()
    return groups, option_map, merged.warnings


def get_instance(klass, obj, *args, **kwargs):
    """Returns an instance of a given model class.

    The argument object must be either an instance of klass (in which case the object is
    simply returned) or the primary key for the model instance.
    This way we can use pre-existing instances as well as previously received keys.
    If a primary key is used get_object_or_404 is called with that primary key.

    Args:
        klass (class): The model class type.
        obj (instance of klass or primary key): Either an instance of klass that is returned
            directly or the primary key of class klass.
        *args: Additional arguments, passed to get_object_or_404.
        **kwargs: Additional arguments, passed to get_object_or_404.

    Returns:
        An instance of klass, either obj directly or through a lookup. Might
        raise an exception via get_object_or_404.
    """
    if not isinstance(obj, klass):
        obj = get_object_or_404(klass, pk=obj, *args, **kwargs)
    return obj
