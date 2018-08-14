import datetime

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


def get_collections():
    pass