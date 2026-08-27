"""Grid cells, the asterisk rule, and date consolidation."""

import datetime as dt

from calendar_gen import layout
from calendar_gen.event_types import resolve
from calendar_gen.events import Event
from calendar_gen.school_year import SchoolYear


def make(label, type_name, start, end=None):
    return Event(
        start=start, end=end or start,
        type=resolve(type_name), label=label, row=1,
    )


# --- the grid --------------------------------------------------------------

def test_every_month_is_a_full_six_week_block(year):
    months = layout.build_months({}, year)
    assert len(months) == 12
    assert all(len(m.cells) == layout.CELLS_PER_MONTH for m in months)


def test_calendar_runs_august_through_july(year):
    months = layout.build_months({}, year)
    assert (months[0].name, months[0].year) == ("August", 2025)
    assert (months[-1].name, months[-1].year) == ("July", 2026)


def test_leading_blanks_put_the_first_day_on_the_right_weekday(year):
    # 1 September 2025 is a Monday, so one blank for Sunday.
    september = next(m for m in layout.build_months({}, year)
                     if m.name == "September")
    assert september.cells[0] is None
    assert september.cells[1].number == 1


def test_february_length_follows_the_year(year):
    february = next(m for m in layout.build_months({}, year)
                    if m.name == "February")
    assert max(c.number for c in february.cells if c) == 28  # 2026 is common


def test_leap_day_is_drawn():
    """2027-28 spans February 2028, which has 29 days."""
    leap = SchoolYear(start_year=2027, organization="T",
                      early_release_start=dt.date(2027, 9, 8),
                      last_day=dt.date(2028, 6, 15))
    february = next(m for m in layout.build_months({}, leap)
                    if m.name == "February")
    days = [c.number for c in february.cells if c]
    assert max(days) == 29
    assert len(days) == 29


# --- early release ---------------------------------------------------------

def test_early_release_is_added_to_wednesdays_in_session(year):
    by_date = layout.events_by_date([], year)
    wednesday = dt.date(2025, 9, 17)
    assert "early_release" in layout.build_day(wednesday, by_date[wednesday]).fills


def test_early_release_does_not_start_before_its_date(year):
    by_date = layout.events_by_date([], year)
    too_early = dt.date(2025, 9, 3)  # a Wednesday, before 9/10
    assert "early_release" not in layout.build_day(too_early, by_date[too_early]).fills


def test_early_release_stops_after_the_last_day(year):
    by_date = layout.events_by_date([], year)
    after = dt.date(2026, 6, 24)  # a Wednesday, after 6/17
    assert "early_release" not in layout.build_day(after, by_date[after]).fills


def test_a_day_off_is_not_also_early_release(year):
    holiday = dt.date(2025, 11, 26)  # a Wednesday in session
    by_date = layout.events_by_date([make("Break", "no_school", holiday)], year)
    fills = layout.build_day(holiday, by_date[holiday]).fills
    assert fills == ["no_school"]


def test_a_half_day_is_not_also_early_release(year):
    half = dt.date(2025, 11, 26)
    by_date = layout.events_by_date([make("Half", "half_day", half)], year)
    assert layout.build_day(half, by_date[half]).fills == ["half_day"]


# --- the asterisk rule -----------------------------------------------------
# One rule: a day gets an asterisk when it carries something the grid cannot
# show. Anything already drawn speaks for itself.

def test_invisible_event_earns_an_asterisk():
    date = dt.date(2025, 11, 12)
    day = layout.build_day(date, [make("Grades Due", "grades_due", date)])
    assert day.has_more
    assert day.fills == []


def test_a_drawn_event_does_not_need_an_asterisk():
    date = dt.date(2025, 11, 27)
    day = layout.build_day(date, [make("Thanksgiving", "no_school", date)])
    assert not day.has_more


def test_ptsa_circle_speaks_for_itself():
    date = dt.date(2025, 10, 16)
    day = layout.build_day(date, [make("Movie Night", "ptsa_event", date)])
    assert day.circled
    assert not day.has_more


def test_an_invisible_event_beside_a_drawn_one_still_earns_the_asterisk():
    date = dt.date(2025, 9, 2)
    day = layout.build_day(date, [
        make("Conferences", "half_day", date),
        make("Kinder Connections", "kinder_family_conn", date),
    ])
    assert day.fills == ["half_day"]
    assert day.has_more


def test_boxed_days_come_from_the_year_config(year):
    boxed = dt.date(2025, 9, 2)
    assert layout.build_day(boxed, [], year.boxed_days).boxed
    assert not layout.build_day(dt.date(2025, 9, 3), [], year.boxed_days).boxed


def test_a_first_day_row_alone_does_not_draw_the_box(year):
    """Per-population first days are listed, not boxed. See DECISIONS.md."""
    snaps = dt.date(2025, 9, 18)
    day = layout.build_day(snaps, [make("First Day of SNAPS", "first_day", snaps)],
                           year.boxed_days)
    assert not day.boxed
    assert day.has_more  # but it is still pointed at


# --- important dates -------------------------------------------------------

def test_consecutive_dates_collapse_into_a_span(year):
    listed = layout.build_important_dates(
        [make("Winter Break", "no_school", dt.date(2025, 12, 22), dt.date(2026, 1, 2))],
        year)
    assert listed[0].when == "12/22-1/2"


def test_repeats_of_one_event_fold_into_a_single_line(year):
    meetings = [make("Board Meeting", "ptsa_event", d) for d in (
        dt.date(2025, 10, 23), dt.date(2026, 2, 19), dt.date(2026, 4, 23))]
    listed = layout.build_important_dates(meetings, year)
    assert len(listed) == 1
    assert listed[0].when == "10/23, 2/19, 4/23"
    assert listed[0].label == "PTSA: Board Meeting"


def test_dates_have_no_leading_zeros(year):
    listed = layout.build_important_dates(
        [make("Labor Day", "no_school", dt.date(2025, 9, 1))], year)
    assert listed[0].when == "9/1"


def test_listed_dates_are_sorted_and_deterministic(year):
    events = [
        make("Zebra", "ptsa_event", dt.date(2025, 9, 2)),
        make("Apple", "ptsa_event", dt.date(2025, 9, 2)),
        make("Earlier", "ptsa_event", dt.date(2025, 9, 1)),
    ]
    labels = [d.label for d in layout.build_important_dates(events, year)]
    assert labels == ["PTSA: Earlier", "PTSA: Apple", "PTSA: Zebra"]


def test_events_outside_the_span_are_not_listed(year):
    listed = layout.build_important_dates(
        [make("Ancient", "ptsa_event", dt.date(2019, 1, 1))], year)
    assert listed == []


def test_a_csv_early_release_row_is_not_duplicated(year):
    """The CSV already carries 'Wednesday early release begins'; the generated
    rule must not append a second event to the same day."""
    wednesday = dt.date(2025, 9, 10)
    by_date = layout.events_by_date(
        [make("Early release begins", "early_release", wednesday)], year)
    assert len(by_date[wednesday]) == 1


def test_dates_outside_the_printed_year_are_not_expanded(year):
    """One mistyped end_date must not build millions of entries."""
    long_run = make("Typo", "no_school", dt.date(2025, 9, 1), dt.date(2030, 9, 1))
    by_date = layout.events_by_date([long_run], year)
    assert all(year.first_printed_day <= d <= year.last_printed_day
               for d in by_date)


def test_the_most_severe_background_wins():
    """A snow day inside a week of half-day conferences is a closed day.

    Left to CSS this was decided by source order at equal specificity, which
    printed the closed day as a grey half-day.
    """
    date = dt.date(2026, 1, 28)
    day = layout.build_day(date, [
        make("Conferences", "half_day", date),
        make("Snow Day", "no_school", date),
    ])
    assert day.fills == ["no_school"]


def test_early_release_rides_alongside_a_background():
    date = dt.date(2026, 5, 6)
    day = layout.build_day(date, [
        make("Make-up", "closure_possible", date),
        make("ER", "early_release", date),
    ])
    assert day.fills == ["closure_possible", "early_release"]


def test_only_one_background_is_ever_emitted():
    date = dt.date(2026, 1, 28)
    day = layout.build_day(date, [
        make("A", "closure_possible", date),
        make("B", "half_day", date),
        make("C", "no_school", date),
    ])
    backgrounds = [f for f in day.fills if f in layout.BACKGROUND_SEVERITY]
    assert backgrounds == ["no_school"]
