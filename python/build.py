"""Build the one-page PTSA calendar PDF.

    python python/build.py                     # current school year, default paths
    python python/build.py --year 2025         # a specific year
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
    for problem in problems:
        print(f"  row {problem.row}: {problem.message}", file=sys.stderr)
        if problem.hint:
            print(f"          {problem.hint}", file=sys.stderr)


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
    parser.add_argument(
        "--out", type=Path, default=None,
        help="Output PDF path (default: build/<Org>-<year>-Calendar.pdf)",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=None,
        help="Directory to write into, keeping the derived filename.",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Validate the CSV and report problems without rendering.",
    )
    parser.add_argument(
        "--print-label", action="store_true",
        help="Print the school-year label (e.g. 2025-26) and exit.",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Treat warnings as errors.",
    )
    args = parser.parse_args()

    # --- school year -----------------------------------------------------
    try:
        start_year, why = school_year.resolve_start_year(args.years_dir, args.year)
        year = school_year.load(args.years_dir, start_year)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.print_label:
        print(year.label)
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

    warnings += events_mod.outside_year(
        all_events, year.first_printed_day, year.last_printed_day
    )
    report(warnings, f"{args.data}: {len(warnings)} warning(s)")

    if warnings and args.strict:
        print("\nerror: warnings treated as errors (--strict)", file=sys.stderr)
        return 1

    if args.check:
        print(f"\nOK: {len(all_events)} events, {len(warnings)} warning(s)")
        return 0

    # --- render ----------------------------------------------------------
    by_date = layout.events_by_date(all_events, year)
    months = layout.build_months(by_date, year)
    important = layout.build_important_dates(all_events, year)
    html = render.render_html(year, months, important)

    filename = f"{year.organization.replace(' ', '')}-{year.label}-Calendar.pdf"
    if args.out:
        out_path = args.out
    else:
        out_path = (args.out_dir or DEFAULT_OUT_DIR) / filename
    render.write_pdf(html, out_path)

    print(f"Wrote {out_path} - {len(all_events)} events, {len(important)} listed dates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
