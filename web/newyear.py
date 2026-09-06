"""Starting a new school year.

The once-a-year job: the district publishes next year's dates in the spring,
the PTSA works out its own, and somebody has to turn that into a calendar. Done
by hand it is sixty-odd rows of CSV and a config file.

The awkward part is what to do with last year's events. Sixty rows is a lot to
retype, and most of them do come back -- but a calendar that *guesses* is the
thing this project exists not to be (`CLAUDE.md`, non-negotiable #3). A shifted
date is a guess, and a guess that looks like data is worse than no data.

So nothing here writes a row on its own. It proposes: for each of last year's
events it suggests the same weekday a year on, shows what the date was, and
waits to be told. A proposal nobody ticks is not carried over. The ticking is
the review, which is why there is no "needs checking" state to store, and no
way for an unreviewed date to reach the CSV.

The suggestion is 364 days, not a year: 52 whole weeks, so a Thursday event
stays on a Thursday. That is right for "the second Thursday sort of event" and
wrong for anything pinned to a rule (Labor Day is the first Monday in
September, whatever the arithmetic says), which is exactly why every one of
them is shown to a person against last year's date.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from calendar_gen.school_year import SchoolYear, label_for

from .csvio import Row

#: 52 weeks. Keeps the weekday, which is what recurring school events are
#: actually pinned to.
SHIFT = dt.timedelta(days=364)


@dataclass
class Proposal:
    """One of last year's events, and where it might go this year."""

    previous: Row
    suggested: Row

    @property
    def label(self) -> str:
        return self.previous.label

    @property
    def type(self) -> str:
        return self.previous.type

    @property
    def was(self) -> str:
        return self.previous.first_day


# label_for comes from calendar_gen.school_year, not from here. It is the
# function available_years uses to decide which filenames it recognises, so a
# second spelling of the rule would let this module write a config that the
# renderer then refuses to see.


def _shift(iso: str) -> str:
    try:
        return (dt.date.fromisoformat(iso) + SHIFT).isoformat()
    except ValueError:
        return ""


def propose(previous_rows: list[Row], previous_start: int) -> list[Proposal]:
    """What last year's events might look like next year, in date order.

    Only rows that belong to the previous school year are offered. The CSV
    holds every year at once, so without this the list would include dates from
    years ago that nobody meant to bring forward.
    """
    # The printed span, asked of the thing that defines it. CLAUDE.md:
    # "MONTH_COUNT in school_year.py is the single source for this, and
    # last_printed_day is derived from it so the drawn months and the
    # dropped-date span cannot drift." Restating 1 Aug - 31 Jul here would be a
    # third definition, and would offer July rows that no calendar can print.
    span = SchoolYear(
        start_year=previous_start, organization="",
        early_release_start=dt.date(previous_start, 9, 1),
        last_day=dt.date(previous_start + 1, 6, 30),
    )
    first, last = span.first_printed_day, span.last_printed_day

    proposals = []
    for row in sorted(previous_rows, key=Row.sort_key):
        when = row.parsed_date()
        if when is None or not (first <= when <= last):
            continue
        proposals.append(Proposal(
            previous=row,
            suggested=Row(
                date=_shift(row.date),
                start_date=_shift(row.start_date),
                end_date=_shift(row.end_date),
                type=row.type,
                label=row.label,
                # Provenance stays with the row it belongs to. Notes on the
                # district dates say where they were verified from, and that
                # claim is about last year's date, not this one.
                notes="",
            ),
        ))
    return proposals


def config_toml(*, organization: str, label: str, early_release_start: str,
                last_day: str, boxed_days: list[str],
                source_label: str | None = None) -> str:
    """The year config file, written the way a person would write it.

    Deliberately not `tomllib`-dumped: the shipped configs carry comments
    explaining every value and where it came from, and a machine-written file
    that dropped them would make the next year's copy-forward worse than this
    one. The header says which year's dates these are and that nobody has
    checked them against the district yet -- because at this point nobody has.
    """
    boxes = ", ".join(sorted(boxed_days))
    came_from = (f" Carried forward from {source_label}."
                 if source_label else "")
    return f"""\
# {organization} calendar - {label} school year.
#
# Created in the calendar editor.{came_from}
#
# VERIFY THESE AGAINST THE DISTRICT before publishing, and re-stamp this
# header when you have:
#   https://www.lwsd.org/calendar
#
# Always start from that page rather than a saved PDF link. The file lives on a
# version-stamped CDN URL and the district republishes under a new one when
# dates change -- an older copy still says "FINAL" and still says the right
# school year, so nothing about it looks stale.

[calendar]
organization = "{organization}"

[dates]
# First Wednesday with early release. Every Wednesday from here through
# last_day is marked automatically -- these are not rows in the CSV.
early_release_start = {early_release_start}

# Last day of school. Bounds the early-release run.
last_day = {last_day}

# The days school starts and ends, drawn with the first/last-day box. Both
# first days belong here if they differ -- grades 1-12 and kindergarten --
# because each is the start of school for its population.
boxed_days = [{boxes}]
"""


def next_year_after(years_dir: Path) -> int:
    """The year to offer creating: one on from the newest config there is.

    Through available_years, which is the same list the renderer works from. A
    glob of its own here would be a third rule for what counts as a year, and
    the three would only have to disagree once.
    """
    from calendar_gen.school_year import available_years

    years = available_years(years_dir)
    return years[-1] + 1 if years else dt.date.today().year


def suggest_dates(start_year: int) -> dict[str, str]:
    """Plausible starting points for the four dates the form asks for.

    Only to save typing -- every one is overwritten by whatever the district
    actually published, and the form shows them as ordinary editable values
    rather than as anything decided.
    """
    def first_weekday_on_or_after(date: dt.date, weekday: int) -> dt.date:
        return date + dt.timedelta(days=(weekday - date.weekday()) % 7)

    september = dt.date(start_year, 9, 1)
    return {
        "first_day": first_weekday_on_or_after(
            dt.date(start_year, 8, 25), 0).isoformat(),          # a Monday
        "early_release_start": first_weekday_on_or_after(
            september, 2).isoformat(),                            # a Wednesday
        "last_day": first_weekday_on_or_after(
            dt.date(start_year + 1, 6, 10), 2).isoformat(),
        # Blank rather than guessed: whether kindergarten starts later, and
        # when, is a district decision with no arithmetic behind it. Present as
        # a key so the form and its error path both have something to echo --
        # missing, Jinja renders it as empty and silently drops whatever the
        # person had typed.
        "kindergarten_first_day": "",
    }
