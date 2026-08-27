"""Turning events into the two things the template draws:
the month grid, and the Important Dates list.
"""

from __future__ import annotations

import calendar
import datetime as dt
from collections import defaultdict
from dataclasses import dataclass, field

from .event_types import REGISTRY
from .events import Event
from .school_year import SchoolYear

WEEKEND = (calendar.SATURDAY, calendar.SUNDAY)
CELLS_PER_MONTH = 42  # 6 rows of 7, so every month block is the same height

#: Auto-applied to in-session Wednesdays; not present in the CSV.
EARLY_RELEASE = REGISTRY["early_release"]


@dataclass
class Day:
    """One numbered cell in a month grid."""

    date: dt.date
    fills: list[str] = field(default_factory=list)
    boxed: bool = False
    circled: bool = False
    has_more: bool = False

    @property
    def number(self) -> int:
        return self.date.day

    @property
    def is_weekend(self) -> bool:
        return self.date.weekday() in WEEKEND


@dataclass
class Month:
    name: str
    year: int
    cells: list[Day | None]


@dataclass
class ImportantDate:
    when: str
    label: str
    is_ptsa: bool
    sort_key: dt.date


def events_by_date(events: list[Event], year: SchoolYear) -> dict[dt.date, list[Event]]:
    """Map every printed date to the events landing on it, early release included."""
    by_date: dict[dt.date, list[Event]] = defaultdict(list)
    for event in events:
        for day in event.dates():
            by_date[day].append(event)

    # Early-release Wednesdays are a rule, not data -- but a day that is already
    # off or already short does not also get marked early release.
    for day in year.early_release_wednesdays():
        fills = {e.type.fill for e in by_date.get(day, ())}
        if "no_school" in fills or "half_day" in fills:
            continue
        by_date[day].append(Event(
            start=day, end=day, type=EARLY_RELEASE,
            label="Early release", row=0,
        ))

    return by_date


def build_day(date: dt.date, events: list[Event],
              boxed_days: frozenset[dt.date] = frozenset()) -> Day:
    """One cell, styled from the types landing on it.

    The asterisk marks a day carrying an *event* the grid cannot show. A fill or
    a circle speaks for its own event; a type that draws neither leaves the cell
    looking like any other day, so the reader needs a pointer to the dates list.

    The box is deliberately not part of that test. It comes from the year config
    rather than from any event, so it says a boundary falls here without saying
    which one -- a boxed day still points at the list for the detail.
    """
    fills: list[str] = []
    for event in events:
        fill = event.type.fill
        if fill and fill not in fills:
            fills.append(fill)

    return Day(
        date=date,
        fills=fills,
        boxed=date in boxed_days,
        circled=any(e.type.circle for e in events),
        has_more=any(e.type.is_invisible for e in events),
    )


def build_months(by_date: dict[dt.date, list[Event]], year: SchoolYear) -> list[Month]:
    """The twelve month blocks, August through July."""
    months = []
    for cal_year, cal_month in year.months():
        first_weekday, days_in_month = calendar.monthrange(cal_year, cal_month)
        # monthrange gives Monday=0; the grid starts on Sunday.
        lead = (first_weekday + 1) % 7

        cells: list[Day | None] = [None] * lead
        for day_number in range(1, days_in_month + 1):
            date = dt.date(cal_year, cal_month, day_number)
            cells.append(build_day(date, by_date.get(date, []), year.boxed_days))
        cells += [None] * (CELLS_PER_MONTH - len(cells))

        months.append(Month(
            name=calendar.month_name[cal_month],
            year=cal_year,
            cells=cells,
        ))
    return months


def _format_day(date: dt.date) -> str:
    """9/2, not 09/02."""
    return f"{date.month}/{date.day}"


def _format_span(start: dt.date, end: dt.date) -> str:
    return _format_day(start) if start == end else f"{_format_day(start)}-{_format_day(end)}"


def _consolidate(dates: list[dt.date]) -> str:
    """[12/22..1/2] -> '12/22-1/2'; scattered dates -> '10/23, 2/19, 4/23'."""
    spans = []
    run_start = run_end = dates[0]
    for date in dates[1:]:
        if (date - run_end).days == 1:
            run_end = date
        else:
            spans.append(_format_span(run_start, run_end))
            run_start = run_end = date
    spans.append(_format_span(run_start, run_end))
    return ", ".join(spans)


def build_important_dates(events: list[Event], year: SchoolYear) -> list[ImportantDate]:
    """The dates list, with repeats of the same event folded into one line.

    Four separate Board Meeting rows become '10/23, 2/19, 4/23, 6/4 PTSA: Board
    Meeting' -- the page is tight, and a reader scanning for board meetings
    would rather find them together.
    """
    # Grouped by label and type only. `notes` never prints, so including it
    # would split one heading into two identical-looking lines.
    grouped: dict[tuple[str, str], list[dt.date]] = defaultdict(list)
    for event in events:
        # Clip to the printed span rather than dropping the whole event: a range
        # straddling 1 August would otherwise list dates the grid cannot show.
        dates = [d for d in event.dates()
                 if year.first_printed_day <= d <= year.last_printed_day]
        if dates:
            grouped[(event.label, event.type.name)].extend(dates)

    listed = []
    for (label, type_name), dates in grouped.items():
        event_type = REGISTRY[type_name]
        unique = sorted(set(dates))
        listed.append(ImportantDate(
            when=_consolidate(unique),
            label=f"{event_type.label_prefix}{label}",
            is_ptsa=event_type.circle,
            sort_key=unique[0],
        ))

    listed.sort(key=lambda item: (item.sort_key, item.label))
    return listed
