"""Reading and validating the event CSV.

Every problem in the file is collected and reported together with its row
number, so one run tells you everything that needs fixing.
"""

from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .event_types import EventType, UnknownEventType, known_names, resolve

CSV_COLUMNS = ("date", "start_date", "end_date", "type", "label", "notes")

_EXTRA = "__surplus__"

#: Longer than the printed year, so it can only be a mistyped end_date.
MAX_RANGE_DAYS = 366


@dataclass(frozen=True)
class Event:
    """One dated entry from the CSV. Single days are a range of one."""

    start: dt.date
    end: dt.date
    type: EventType
    label: str
    notes: str = ""
    row: int = 0

    @property
    def is_range(self) -> bool:
        return self.start != self.end

    def dates(self) -> Iterator[dt.date]:
        """Every date this event covers, inclusive."""
        day = self.start
        while day <= self.end:
            yield day
            day += dt.timedelta(days=1)


@dataclass(frozen=True)
class Problem:
    row: int
    message: str
    hint: str = ""


def format_problems(problems: list[Problem]) -> str:
    """Render problems or warnings identically, so the two never drift apart."""
    lines = []
    for p in problems:
        lines.append(f"  row {p.row}: {p.message}")
        if p.hint:
            lines.append(f"          {p.hint}")
    return "\n".join(lines)


class ValidationError(Exception):
    """One or more rows in the CSV could not be used."""

    def __init__(self, path: Path, problems: list[Problem]):
        self.path = path
        self.problems = problems
        n = len(problems)
        super().__init__(
            f"{path}: {n} problem{'s' if n != 1 else ''}\n\n"
            + format_problems(problems)
        )


def _parse_date(value: str) -> dt.date | None:
    if not value:
        return None
    return dt.datetime.strptime(value, "%Y-%m-%d").date()


def load_events(csv_path: str | Path) -> tuple[list[Event], list[Problem]]:
    """Read and validate the event CSV.

    Returns ``(events, warnings)``. Warnings are things worth saying out loud
    that should not stop a build. Anything that would make the calendar wrong
    raises :class:`ValidationError` instead.
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Events file not found: {path}")

    events: list[Event] = []
    problems: list[Problem] = []
    warnings: list[Problem] = []

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, restkey=_EXTRA)
        missing = [c for c in ("type", "label") if c not in (reader.fieldnames or ())]
        if missing:
            raise ValidationError(
                path,
                [Problem(1, f"missing required column(s): {', '.join(missing)}",
                         f"expected header: {','.join(CSV_COLUMNS)}")],
            )

        for raw in reader:
            # reader.line_num counts physical lines, so the number matches what
            # an editor shows even when the file has blank or quoted-multiline
            # rows -- enumerate() would drift.
            offset = reader.line_num

            surplus = raw.pop(_EXTRA, None)
            if surplus:
                problems.append(Problem(
                    offset,
                    f"has {len(surplus)} more field(s) than the header",
                    "an unquoted comma in a label or note splits the row -- "
                    'wrap the value in double quotes',
                ))
                continue

            row = {k: (v or "").strip() for k, v in raw.items() if k}

            label = row.get("label", "")
            if not label:
                problems.append(Problem(offset, "missing label"))
                continue

            try:
                event_type = resolve(row.get("type", ""))
            except UnknownEventType:
                problems.append(Problem(
                    offset,
                    f"unknown event type {row.get('type', '')!r}",
                    f"declared types: {', '.join(known_names())}",
                ))
                continue

            try:
                single = _parse_date(row.get("date", ""))
                start = _parse_date(row.get("start_date", ""))
                end = _parse_date(row.get("end_date", ""))
            except ValueError as exc:
                problems.append(Problem(offset, f"unreadable date: {exc}",
                                        "dates must be YYYY-MM-DD"))
                continue

            if single and (start or end):
                # Silently preferring one would collapse a week to a day -- the
                # exact bug this validator exists to catch.
                problems.append(Problem(
                    offset, "has both a 'date' and a date range",
                    "use one or the other, not both",
                ))
                continue

            if single:
                start = end = single
            elif start and end:
                if end < start:
                    problems.append(Problem(
                        offset, f"end_date {end} is before start_date {start}"))
                    continue
                if (end - start).days > MAX_RANGE_DAYS:
                    problems.append(Problem(
                        offset,
                        f"{label!r} spans {(end - start).days + 1} days "
                        f"({start} to {end})",
                        "check the end date -- no calendar event runs longer "
                        "than the school year",
                    ))
                    continue
                if start == end:
                    warnings.append(Problem(
                        offset,
                        f"{label!r} is a one-day range",
                        "use the 'date' column for single days, or widen the range",
                    ))
            elif start or end:
                problems.append(Problem(
                    offset, "a range needs both start_date and end_date"))
                continue
            else:
                problems.append(Problem(
                    offset, "no date given",
                    "set 'date', or both 'start_date' and 'end_date'"))
                continue

            events.append(Event(
                start=start,
                end=end,
                type=event_type,
                label=label,
                notes=row.get("notes", ""),
                row=offset,
            ))

    if problems:
        raise ValidationError(path, problems)

    return events, warnings


def outside_year(events: list[Event], first: dt.date, last: dt.date) -> list[Problem]:
    """Events that fall outside the printed span, and so never appear.

    These are *notices*, not warnings: leaving last year's rows in place, or
    staging next year's early, is a normal way to work on this file, and both
    are documented as reported-and-dropped. Escalating them under --strict
    would turn the everyday workflow into a red build.
    """
    return [
        Problem(e.row, f"{e.label!r} ({e.start}) is outside the calendar span",
                f"the calendar covers {first} to {last}, so it is not printed")
        for e in events
        if e.end < first or e.start > last
    ]
