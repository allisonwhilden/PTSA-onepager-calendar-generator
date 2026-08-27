"""Build the one-page PTSA calendar PDF.

    python python/build.py                     # current school year, default paths
    python python/build.py --year 2026         # a specific year
    python python/build.py --check             # validate the CSV, render nothing

Runs from any working directory.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from calendar_gen import events as events_mod
from calendar_gen import layout, render, school_year

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

DEFAULT_DATA = REPO / "data" / "all_events.csv"
DEFAULT_YEARS = REPO / "data" / "years"
DEFAULT_OUT_DIR = REPO / "build"



def report(problems, heading: str) -> None:
    if not problems:
        return
    print(f"\n{heading}", file=sys.stderr)
    print(events_mod.format_problems(problems), file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the one-page PTSA calendar PDF.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--year", type=int, default=None,
        help="School year to build, as its starting year (2025 means 2025-26). "
             "Defaults to the current school year.",
    )
    parser.add_argument(
        "--data", type=Path, default=DEFAULT_DATA,
        help=f"Event CSV (default: {DEFAULT_DATA.relative_to(REPO)})",
    )
    parser.add_argument(
        "--years-dir", type=Path, default=DEFAULT_YEARS,
        help=f"School-year configs (default: {DEFAULT_YEARS.relative_to(REPO)})",
    )
    where = parser.add_mutually_exclusive_group()
    where.add_argument(
        "--out", type=Path, default=None,
        help="Output PDF path (default: build/<Org>-<year>-Calendar.pdf)",
    )
    where.add_argument(
        "--out-dir", type=Path, default=None,
        help="Directory to write into, keeping the derived filename.",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Validate the CSV and report problems without rendering.",
    )
    show = parser.add_mutually_exclusive_group()
    show.add_argument(
        "--print-label", action="store_true",
        help="Print the school-year label (e.g. 2025-26) and exit.",
    )
    show.add_argument(
        "--print-organization", action="store_true",
        help="Print the organization name from the year config and exit.",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Treat warnings as errors.",
    )
    parser.add_argument(
        "--require-current-year", action="store_true",
        help="Fail unless the year being built is the current school year. "
             "Used before publishing, so an ended year is never served as "
             "the current calendar.",
    )
    args = parser.parse_args()

    # --- school year -----------------------------------------------------
    try:
        start_year, why = school_year.resolve_start_year(args.years_dir, args.year)
        year = school_year.load(args.years_dir, start_year)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.require_current_year:
        current = school_year.current_start_year()
        if start_year != current:
            wanted = school_year.label_for(current)
            print(
                f"error: the current school year is {wanted}, but this build is "
                f"{year.label} ({why}).\n"
                f"       Add data/years/{wanted}.toml and this year's rows in "
                f"{args.data.name} before publishing.",
                file=sys.stderr,
            )
            return 3

    if args.print_label:
        print(year.label)
        return 0

    if args.print_organization:
        print(year.organization)
        return 0

    print(f"Building {year.label} ({why})")

    # --- events ----------------------------------------------------------
    try:
        all_events, warnings = events_mod.load_events(args.data)
    except events_mod.ValidationError as exc:
        print(f"\nerror: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    # Notices are separate from warnings on purpose: rows for another school
    # year are dropped by design, so --strict must not turn the ordinary act of
    # staging next year's dates into a red build.
    notices = events_mod.outside_year(
        all_events, year.first_printed_day, year.last_printed_day
    )
    report(warnings, f"{args.data}: {len(warnings)} warning(s)")
    report(notices, f"{args.data}: {len(notices)} row(s) not on this calendar")

    if warnings and args.strict:
        print("\nerror: warnings treated as errors (--strict)", file=sys.stderr)
        return 1

    # --- render ----------------------------------------------------------
    by_date = layout.events_by_date(all_events, year)
    months = layout.build_months(by_date, year)
    important = layout.build_important_dates(all_events, year)

    # Every row landing outside the span means a blank calendar. Without this
    # the usual half-finished year roll -- new config, last year's CSV -- passes
    # --check --strict and CI goes green on a page with nothing on it.
    if not important:
        if all_events:
            reason = (f"none of the {len(all_events)} rows in {args.data.name} "
                      f"fall inside {year.label} ({year.first_printed_day} to "
                      f"{year.last_printed_day})")
        else:
            reason = f"{args.data.name} has no event rows"
        print(f"\nerror: {reason}, so the calendar would be blank.",
              file=sys.stderr)
        return 1

    html = render.render_html(year, months, important)

    if args.check:
        pages = render.count_pages(html)
        if pages is None:
            print(f"\nOK: {len(all_events)} events, {len(important)} listed dates, "
                  f"{len(warnings)} warning(s), {len(notices)} not on this calendar"
                  f"\nNote: WeasyPrint is not installed, so the one-page check "
                  f"was skipped.")
            return 0
        if pages != 1:
            print(
                f"\nerror: the calendar renders on {pages} pages. It must fit on "
                f"one.\n       Remove or shorten a few entries in "
                f"{args.data.name} -- the page is tight.",
                file=sys.stderr,
            )
            return 1
        print(f"\nOK: {len(all_events)} events, {len(important)} listed dates, "
              f"one page, {len(warnings)} warning(s), "
              f"{len(notices)} not on this calendar")
        return 0

    filename = f"{year.organization.replace(' ', '')}-{year.label}-Calendar.pdf"
    if args.out:
        out_path = args.out
    else:
        out_path = (args.out_dir or DEFAULT_OUT_DIR) / filename
    try:
        render.write_pdf(html, out_path)
    except render.WeasyPrintUnavailable as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Wrote {out_path} - {len(all_events)} events, {len(important)} listed dates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
