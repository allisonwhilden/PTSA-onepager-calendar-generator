"""Reading and writing `data/all_events.csv` without disturbing it.

The editor rewrites this file on every save, and every save is a commit someone
may later read to answer "what changed?". A writer that reordered rows, or
re-quoted fields, or flipped line endings would bury one moved date in sixty
lines of noise and make the history useless -- which would take away the one
thing the whole design is for.

So the rule here is: a file read and written back unchanged must come out byte
for byte identical. `test_round_trip_is_byte_identical` holds that against the
real shipped CSV, not a fixture, because the real one is the one that matters.

This module deliberately knows nothing about what the types mean or which dates
are valid. That is `calendar_gen`'s job, and asking it twice is how the two
answers drift apart.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
from dataclasses import dataclass, field, fields
from pathlib import Path

#: The column order in the file. Fixed, not discovered, so a rewrite cannot
#: silently reorder columns when a row happens to be missing one.
COLUMNS = ["date", "start_date", "end_date", "type", "label", "notes"]


@dataclass
class Row:
    """One line of the CSV.

    Everything is a string, exactly as stored. Dates are *not* parsed into
    date objects here: a row someone is halfway through typing has to survive
    being saved, and `calendar_gen.events` is what says whether it is valid.
    Parsing early would mean this module rejecting rows on its own terms.
    """

    date: str = ""
    start_date: str = ""
    end_date: str = ""
    type: str = ""
    label: str = ""
    notes: str = ""

    @property
    def is_range(self) -> bool:
        return bool(self.start_date or self.end_date)

    @property
    def first_day(self) -> str:
        """The date this row sorts and displays by."""
        return self.date or self.start_date

    def sort_key(self) -> str:
        """The day this row sorts by, and deliberately nothing else.

        Sorting rows that share a date -- by type, or label, or end date --
        looks tidier and is wrong. Two rows on 2027-06-16 carry notes reading
        "the row above" and "the row below"; any tiebreak is free to swap them
        and turn both notes into lies, silently, in a column the page never
        prints. Python's sort is stable, so with the date alone same-day rows
        keep the order the file already had, and a newly added row lands at the
        end of its day.
        """
        return self.first_day

    def as_dict(self) -> dict[str, str]:
        return {c: getattr(self, c) for c in COLUMNS}

    def parsed_date(self) -> dt.date | None:
        """The first day as a date, or None if it is blank or malformed.

        For sorting and grouping in the UI only. Never for validation.
        """
        try:
            return dt.date.fromisoformat(self.first_day)
        except ValueError:
            return None


def parse(text: str) -> list[Row]:
    """Rows from CSV text. Unknown columns are dropped, missing ones blank."""
    reader = csv.DictReader(io.StringIO(text))
    known = {f.name for f in fields(Row)}
    rows = []
    for raw in reader:
        rows.append(Row(**{k: (v or "").strip()
                           for k, v in raw.items() if k in known}))
    return rows


def dump(rows: list[Row], *, sort: bool = True) -> str:
    """CSV text for these rows.

    Written with an explicit LF terminator rather than csv's default CRLF: the
    file on disk is LF, and letting it flip would rewrite all 61 lines on the
    first save and make that commit unreadable.
    """
    ordered = sorted(rows, key=Row.sort_key) if sort else list(rows)
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in ordered:
        writer.writerow(row.as_dict())
    return out.getvalue()


def read(path: Path) -> list[Row]:
    return parse(Path(path).read_text(encoding="utf-8"))


def write(path: Path, rows: list[Row], *, sort: bool = True) -> None:
    Path(path).write_text(dump(rows, sort=sort), encoding="utf-8")
