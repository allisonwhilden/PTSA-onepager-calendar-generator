"""
Horace Mann PTSA Calendar Generator

Generates a single-page PDF calendar combining LWSD district dates with PTSA events.
"""

import argparse
import calendar
import csv
import datetime as dt
import os
import pathlib
import sys
from dataclasses import dataclass
from typing import Iterator

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML


# ---- Constants ----
WEDNESDAY = 2
SATURDAY = 5
SUNDAY = 6
WEEKEND_DAYS = (SATURDAY, SUNDAY)

MONTH_NAMES = [calendar.month_name[i] for i in range(13)]


# ---- School Year Configuration ----
# Hardcoded dates for 2025-26 school year. Update for future years.
SCHOOL_YEAR_CONFIG = {
    2025: {
        "early_release_start": dt.date(2025, 9, 10),
        "school_year_end": dt.date(2026, 6, 17),
        "special_diamond_days": [
            (2025, 9, 2),   # First day grades 1-12
            (2025, 9, 5),   # First day K
            (2026, 6, 17),  # Last day
        ],
    }
}


# ---- Type Normalization ----
TYPE_NORMALIZATION = {
    "no_school": "no_school",
    "half_day": "half_day",
    "first_day": "first_day",
    "last_day": "last_day",
    "early_release": "early_release",
    "ptsa_event": "ptsa_event",
    "closure_possible": "closure_possible",
    # aliases
    "first_day_1_12": "first_day",
    "first_day_k": "first_day",
    "holiday": "no_school",
    "closure_day": "closure_possible",
    "possible_school_day": "closure_possible",
    "potential_school_day": "closure_possible",
}


# ---- Data Classes ----
@dataclass
class Cell:
    """Represents a single day cell in the calendar grid."""
    day: int
    marks: list[str]
    is_weekend: bool
    has_diamond: bool
    has_circle: bool

    @property
    def show_asterisk(self) -> bool:
        """Determine if this cell should show an asterisk for additional events."""
        # No asterisk if it's a no-school or half day
        if "no_school" in self.marks or "half_day" in self.marks:
            # But show asterisk if there are multiple marks and one is early_release
            if len(self.marks) > 1 and "early_release" in self.marks and "ptsa_event" not in self.marks:
                return True
            return False

        # No asterisk if it's early release only
        if "early_release" in self.marks:
            return False

        # Show asterisk for first/last day with diamond/circle
        if "first_day" in self.marks or "last_day" in self.marks:
            return self.has_diamond or self.has_circle

        # Show asterisk if there are other marks (non-PTSA)
        return bool(self.marks) and "ptsa_event" not in self.marks


# ---- Helper Functions ----
def format_date_short(d: dt.date) -> str:
    """Format date as M/D without leading zeros (e.g., 9/2, 12/25)."""
    return f"{d.month}/{d.day}"


def format_date_range(start: dt.date, end: dt.date) -> str:
    """Format a date range as 'M/D-M/D' or just 'M/D' if same day."""
    if start == end:
        return format_date_short(start)
    return f"{format_date_short(start)}-{format_date_short(end)}"


def daterange(start: dt.date, end: dt.date) -> Iterator[dt.date]:
    """Yield each date from start to end (inclusive)."""
    current = start
    while current <= end:
        yield current
        current += dt.timedelta(days=1)


def parse_date(s: str | None) -> dt.date | None:
    """Parse a YYYY-MM-DD date string, or return None if empty/invalid."""
    if not s:
        return None
    return dt.datetime.strptime(s, "%Y-%m-%d").date()


# ---- Data Processing ----
def read_events(csv_path: str) -> list[dict]:
    """Read events from CSV file, normalizing types."""
    rows = []
    if not pathlib.Path(csv_path).exists():
        print(f"Warning: Events file not found: {csv_path}", file=sys.stderr)
        print("Calendar will be generated with no events.", file=sys.stderr)
        return rows

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for raw_row in reader:
            row = {k: (v.strip() if isinstance(v, str) else v) for k, v in raw_row.items()}
            # Normalize type
            raw_type = row.get("type") or ""
            row["type"] = TYPE_NORMALIZATION.get(raw_type, raw_type)
            rows.append(row)

    return rows


def expand_events(rows: list[dict]) -> list[tuple[dt.date, dict]]:
    """Expand single-day and ranged events to a list of (date, row) tuples."""
    expanded = []
    for row in rows:
        date = parse_date(row.get("date"))
        start = parse_date(row.get("start_date"))
        end = parse_date(row.get("end_date"))

        if date:
            expanded.append((date, row))
        elif start and end:
            for d in daterange(start, end):
                expanded.append((d, row))
        # Rows without valid dates are silently ignored

    return expanded


def bucket_by_month(expanded: list[tuple[dt.date, dict]], year: int) -> dict:
    """
    Return { (year, month) : {day:int -> [types]} } for the given school year.
    Also adds early_release to Wednesdays during the school year.
    """
    buckets: dict[tuple[int, int], dict[int, list[str]]] = {}

    # Collect all events from the data
    for d, row in expanded:
        key = (d.year, d.month)
        buckets.setdefault(key, {}).setdefault(d.day, []).append(row["type"] or "ptsa_event")

    # Add early_release to Wednesdays during school year
    config = SCHOOL_YEAR_CONFIG.get(year)
    if config is None:
        print(f"Warning: No configuration for school year {year}-{year+1}.", file=sys.stderr)
        print("Early release Wednesdays and special day markers will not be applied.", file=sys.stderr)
        config = {}
    early_release_start = config.get("early_release_start")
    school_year_end = config.get("school_year_end")

    if early_release_start and school_year_end:
        current = early_release_start
        while current <= school_year_end:
            if current.weekday() == WEDNESDAY:
                key = (current.year, current.month)
                day_marks = buckets.setdefault(key, {}).setdefault(current.day, [])
                # Only add early_release if not already a no_school or half_day
                if "no_school" not in day_marks and "half_day" not in day_marks:
                    if "early_release" not in day_marks:
                        day_marks.append("early_release")
            current += dt.timedelta(days=7)

    return buckets


def school_year_months(year_start: int) -> list[tuple[int, int]]:
    """Return a list of (year, month) covering Aug..Jul for a given starting calendar year."""
    months = [(year_start, 8)]  # August
    for m in range(9, 13):  # Sep..Dec
        months.append((year_start, m))
    for m in range(1, 8):   # Jan..Jul
        months.append((year_start + 1, m))
    return months


def is_special_diamond_day(year: int, month: int, day: int, config_year: int) -> bool:
    """Check if a date is one of the special diamond indicator days."""
    config = SCHOOL_YEAR_CONFIG.get(config_year, {})
    special_days = config.get("special_diamond_days", [])
    return (year, month, day) in special_days


def make_month_cells(year: int, month: int, marks_for_day: dict, config_year: int) -> list[Cell | str]:
    """
    Return a list of 42 cells (7x6 grid) for a month.
    Empty cells before/after the month are represented as empty strings.
    """
    first_weekday, num_days = calendar.monthrange(year, month)

    # Convert Mon=0..Sun=6 to Sun=0..Sat=6 for calendar grid
    sun_first_index = (first_weekday + 1) % 7

    cells: list[Cell | str] = []

    # Leading blank cells
    for _ in range(sun_first_index):
        cells.append("")

    # Day cells
    for day in range(1, num_days + 1):
        date_obj = dt.date(year, month, day)
        day_of_week = date_obj.weekday()
        is_weekend = day_of_week in WEEKEND_DAYS

        has_diamond = is_special_diamond_day(year, month, day, config_year)

        marks = marks_for_day.get(day, [])
        has_circle = "ptsa_event" in marks

        # Build style marks list, deduplicating
        style_marks = []
        for mark_type in marks:
            if mark_type in ("first_day", "last_day", "first_day_1_12", "first_day_k",
                            "no_school", "half_day", "early_release", "ptsa_event", "closure_possible"):
                if mark_type not in style_marks:
                    style_marks.append(mark_type)

        cells.append(Cell(
            day=day,
            marks=style_marks,
            is_weekend=is_weekend,
            has_diamond=has_diamond,
            has_circle=has_circle
        ))

    # Trailing blank cells to complete the grid
    while len(cells) % 7 != 0:
        cells.append("")
    while len(cells) < 42:
        cells.append("")

    return cells


def format_important_dates(expanded: list[tuple[dt.date, dict]], months_span: list[tuple[int, int]]) -> list[dict]:
    """
    Return a sorted list of events for the Important Dates column.
    Consolidates consecutive dates into ranges.
    """
    span_set = set(months_span)

    # Group events by label and notes to find date ranges
    event_groups: dict[tuple[str, str, str], list[dt.date]] = {}

    for d, row in expanded:
        if (d.year, d.month) not in span_set:
            continue

        label = row.get("label") or row.get("type")
        notes = row.get("notes") or ""
        event_type = row.get("type") or ""
        event_key = (label, notes, event_type)

        if event_key not in event_groups:
            event_groups[event_key] = []
        event_groups[event_key].append(d)

    # Format events with date ranges
    result = []
    for (label, notes, event_type), dates in event_groups.items():
        dates = sorted(dates)

        # Build date ranges from consecutive dates
        date_ranges = []
        range_start = dates[0]
        range_end = dates[0]

        for i in range(1, len(dates)):
            if (dates[i] - dates[i-1]).days == 1:
                range_end = dates[i]
            else:
                date_ranges.append(format_date_range(range_start, range_end))
                range_start = dates[i]
                range_end = dates[i]

        # Add the final range
        date_ranges.append(format_date_range(range_start, range_end))

        when_str = ", ".join(date_ranges)

        # Add PTSA prefix for PTSA events
        display_label = f"PTSA: {label}" if event_type == "ptsa_event" else label

        result.append({
            "when": when_str,
            "label": display_label,
            "notes": notes,
            "is_ptsa": event_type == "ptsa_event",
            "sort_date": dates[0],
        })

    # Sort by first date
    result.sort(key=lambda x: x["sort_date"])

    # Remove sort_date from final result
    for item in result:
        del item["sort_date"]

    return result


def build_context(year_start: int, events_path: str) -> dict:
    """Build the complete template context for the calendar."""
    rows = read_events(events_path)
    expanded = expand_events(rows)
    buckets = bucket_by_month(expanded, year_start)
    months_span = school_year_months(year_start)

    months = []
    for (y, m) in months_span:
        marks_for_day = buckets.get((y, m), {})
        cells = make_month_cells(y, m, marks_for_day, year_start)
        months.append({
            "name": MONTH_NAMES[m],
            "year": y,
            "cells": cells,
            "note": "",
        })

    important = format_important_dates(expanded, months_span)

    return {
        "title": f"{year_start}-{(year_start + 1) % 100:02d} Calendar",
        "header": {
            "title": f"{year_start}-{(year_start + 1) % 100:02d} Calendar",
            "subtitle": "PTSA + District Dates",
        },
        "months": months,
        "important": important,
        "meta": {
            "generated_at": dt.datetime.now().strftime("%b %d, %Y"),
            "source_note": "Data: CSV (district & PTSA)",
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Generate PTSA calendar PDF")
    parser.add_argument(
        "--year",
        type=int,
        required=True,
        help="Starting calendar year for the school year (e.g., 2025 for 2025-26)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="build/HoraceMann-PTSA-2025-26-Calendar.pdf",
        help="Output PDF path",
    )
    parser.add_argument("--template", type=str, default="calendar.html")
    parser.add_argument("--templates_dir", type=str, default="templates")
    parser.add_argument("--styles", type=str, nargs="*", default=["styles/calendar.css"])
    parser.add_argument(
        "--data",
        type=str,
        default="data/all_events.csv",
        help="Path to CSV file with all events",
    )
    args = parser.parse_args()

    ctx = build_context(args.year, args.data)

    env = Environment(
        loader=FileSystemLoader(args.templates_dir),
        autoescape=select_autoescape(["html", "xml"]),
    )
    tpl = env.get_template(args.template)
    html_str = tpl.render(**ctx)

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    HTML(string=html_str, base_url=os.getcwd()).write_pdf(target=str(out_path))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
