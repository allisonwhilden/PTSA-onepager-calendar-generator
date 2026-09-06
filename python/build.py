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
from calendar_gen import pipeline, render

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
        help="School year to build, as its starting year (2026 means 2026-27). "
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
        help="Print the school-year label (e.g. 2026-27) and exit.",
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

    # Every rule about what makes a calendar valid lives in calendar_gen.pipeline,
    # because the web editor asks the same questions and the two must not drift.
    # build.py's remaining job is to turn the answer into exit codes and stderr.
    try:
        if args.print_label or args.print_organization:
            year, _ = pipeline.load_year(
                args.years_dir, args.year, args.require_current_year)
            print(year.label if args.print_label else year.organization)
            return 0

        result = pipeline.build(
            args.data, args.years_dir, args.year, args.require_current_year)
    except pipeline.Blocked as exc:
        # Say which year, and which rows fell outside it, before the error --
        # for a half-finished year roll those row numbers are the diagnosis.
        if exc.year is not None:
            print(f"Building {exc.year.label} ({exc.why})")
        report(exc.notices,
               f"{args.data}: {len(exc.notices)} row(s) not on this calendar")
        print(f"error: {exc}", file=sys.stderr)
        return exc.code

    print(f"Building {result.label} ({result.why})")

    report(result.warnings, f"{args.data}: {len(result.warnings)} warning(s)")
    report(result.notices,
           f"{args.data}: {len(result.notices)} row(s) not on this calendar")

    counts = (f"{len(result.events)} events, {len(result.important)} listed dates")

    problems = result.publish_problems(strict=args.strict)
    if problems:
        print("\nerror: " + "\n       ".join(problems), file=sys.stderr)
        return 1

    if args.check:
        if result.page_count() is None:
            print(f"\nOK: {counts}, {len(result.warnings)} warning(s), "
                  f"{len(result.notices)} not on this calendar"
                  f"\nNote: WeasyPrint is not installed, so the one-page check "
                  f"was skipped.")
            return 0
        print(f"\nOK: {counts}, one page, {len(result.warnings)} warning(s), "
              f"{len(result.notices)} not on this calendar")
        return 0

    out_path = args.out or (args.out_dir or DEFAULT_OUT_DIR) / result.filename
    try:
        result.write_pdf(out_path)
    except render.WeasyPrintUnavailable as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Wrote {out_path} - {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
