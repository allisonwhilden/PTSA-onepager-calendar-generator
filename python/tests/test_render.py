"""End-to-end checks on the published artifact.

The snapshot covers *what the page says*; the PDF checks cover the one promise
the product actually makes -- that it prints on a single Letter page.
"""

import datetime as dt
import difflib
import os

import pytest

from calendar_gen import events as ev
from calendar_gen import layout, render, school_year

FROZEN = dt.date(2026, 1, 15)  # so the footer date does not drift the snapshot
GOLDEN = "calendar-2025-26.html"


def build_html(real_csv, years_dir) -> str:
    year = school_year.load(years_dir, 2025)
    events, _ = ev.load_events(real_csv)
    by_date = layout.events_by_date(events, year)
    return render.render_html(
        year,
        layout.build_months(by_date, year),
        layout.build_important_dates(events, year),
        generated_at=FROZEN,
    )


def test_html_matches_the_snapshot(real_csv, years_dir, request):
    """Any change to the printed page shows up here as a reviewable diff.

    Intentional change? Re-record with:  UPDATE_GOLDEN=1 pytest python/tests
    """
    golden = request.path.parent / "golden" / GOLDEN
    actual = build_html(real_csv, years_dir)

    if os.environ.get("UPDATE_GOLDEN"):
        golden.parent.mkdir(exist_ok=True)
        golden.write_text(actual, encoding="utf-8")
        pytest.skip(f"recorded {golden.name}")

    assert golden.exists(), f"missing snapshot; record it with UPDATE_GOLDEN=1"
    expected = golden.read_text(encoding="utf-8")

    if actual != expected:
        diff = "\n".join(difflib.unified_diff(
            expected.splitlines(), actual.splitlines(),
            "snapshot", "current", lineterm="", n=2))
        pytest.fail("Rendered page changed:\n\n" + diff[:4000])


def test_the_grades_due_days_are_not_black(real_csv, years_dir):
    """Regression guard for the bug that started the rewrite.

    2025-11-12 is an ordinary school day with a grades deadline. It must not
    render as a no-school cell.
    """
    year = school_year.load(years_dir, 2025)
    events, _ = ev.load_events(real_csv)
    by_date = layout.events_by_date(events, year)

    for date in (dt.date(2025, 11, 12), dt.date(2026, 1, 21), dt.date(2026, 2, 2),
                 dt.date(2026, 4, 10), dt.date(2026, 6, 10)):
        day = layout.build_day(date, by_date[date], year.boxed_days)
        assert "no_school" not in day.fills, f"{date} wrongly marked no-school"
        assert day.has_more, f"{date} should point at the dates list"


# --- the actual PDF --------------------------------------------------------

weasyprint = pytest.importorskip(
    "weasyprint", reason="WeasyPrint needs system libraries; skipped where absent")


@pytest.fixture(scope="module")
def built_pdf(tmp_path_factory, real_csv, years_dir):
    year = school_year.load(years_dir, 2025)
    events, _ = ev.load_events(real_csv)
    by_date = layout.events_by_date(events, year)
    html = render.render_html(
        year, layout.build_months(by_date, year),
        layout.build_important_dates(events, year), generated_at=FROZEN)
    return render.write_pdf(html, tmp_path_factory.mktemp("pdf") / "calendar.pdf")


def test_calendar_is_exactly_one_page(built_pdf):
    """The whole point of the product. If this fails, nothing else matters."""
    pypdf = pytest.importorskip("pypdf")
    assert len(pypdf.PdfReader(built_pdf).pages) == 1


def test_page_is_us_letter(built_pdf):
    pypdf = pytest.importorskip("pypdf")
    box = pypdf.PdfReader(built_pdf).pages[0].mediabox
    assert (round(float(box.width)), round(float(box.height))) == (612, 792)
