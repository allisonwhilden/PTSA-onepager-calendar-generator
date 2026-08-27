"""End-to-end checks on the published artifact.

These tests follow whatever year the repo currently ships, rather than pinning
2025. Rolling to a new year is meant to be a config file and a CSV; a test that
hardcodes the year turns that roll red, and -- worse -- would keep asserting
"one page" about a year nobody is publishing any more.
"""

import datetime as dt
import difflib
import os

import pytest

from calendar_gen import events as ev
from calendar_gen import layout, render, school_year

FROZEN = dt.date(2026, 1, 15)  # so the footer date does not drift the snapshot


@pytest.fixture(scope="session")
def shipped_year(years_dir):
    """The year `python/build.py` builds by default."""
    start_year, _ = school_year.resolve_start_year(years_dir)
    return school_year.load(years_dir, start_year)


@pytest.fixture(scope="session")
def shipped_events(real_csv):
    events, _ = ev.load_events(real_csv)
    return events


@pytest.fixture(scope="session")
def rendered_html(shipped_year, shipped_events):
    by_date = layout.events_by_date(shipped_events, shipped_year)
    return render.render_html(
        shipped_year,
        layout.build_months(by_date, shipped_year),
        layout.build_important_dates(shipped_events, shipped_year),
        generated_at=FROZEN,
    )


def test_html_matches_the_snapshot(rendered_html, shipped_year, request):
    """Any change to the printed page shows up here as a reviewable diff.

    Intentional change? Re-record with:  UPDATE_GOLDEN=1 pytest python/tests
    """
    golden = (request.path.parent / "golden"
              / f"calendar-{shipped_year.label}.html")

    if os.environ.get("UPDATE_GOLDEN"):
        golden.parent.mkdir(exist_ok=True)
        golden.write_text(rendered_html, encoding="utf-8")
        pytest.skip(f"recorded {golden.name}")

    assert golden.exists(), (
        f"No snapshot for {shipped_year.label}. This year's page has never been "
        f"reviewed -- look it over, then record it with "
        f"UPDATE_GOLDEN=1 pytest python/tests/test_render.py"
    )
    expected = golden.read_text(encoding="utf-8")

    if rendered_html != expected:
        diff = "\n".join(difflib.unified_diff(
            expected.splitlines(), rendered_html.splitlines(),
            "snapshot", "current", lineterm="", n=2))
        pytest.fail("Rendered page changed:\n\n" + diff[:4000])


def test_informational_days_are_not_marked_no_school(
        shipped_year, shipped_events):
    """Regression guard for the bug that started the rewrite.

    Derived from the CSV rather than hardcoded, so it keeps guarding whichever
    year is shipping: every day whose only listed events draw nothing must stay
    an ordinary day, and must point at the dates list.
    """
    by_date = layout.events_by_date(shipped_events, shipped_year)

    invisible_dates = {
        d
        for e in shipped_events if e.type.is_invisible
        for d in e.dates()
        if shipped_year.first_printed_day <= d <= shipped_year.last_printed_day
    }
    assert invisible_dates, "no informational dates in the CSV to guard"

    for date in sorted(invisible_dates):
        day = layout.build_day(date, by_date[date], shipped_year.boxed_days)
        assert day.has_more, f"{date} should point at the dates list"
        # A day off may legitimately also carry an informational note
        # (Juneteenth plus a grades deadline), so only assert that the
        # informational event did not itself create the fill.
        real_no_school = any(
            e.type.fill == "no_school" for e in by_date[date]
        ) and any(
            e.type.name == "no_school" for e in by_date[date]
        )
        if "no_school" in day.fills:
            assert real_no_school, f"{date} wrongly marked no-school"


def test_every_listed_date_is_inside_the_printed_year(
        shipped_year, shipped_events):
    """The dates column must never point at a day the grid cannot show."""
    listed = layout.build_important_dates(shipped_events, shipped_year)
    months = {(y, m) for y, m in shipped_year.months()}
    for item in listed:
        assert (item.sort_key.year, item.sort_key.month) in months, item


# --- the actual PDF --------------------------------------------------------
# WeasyPrint needs system libraries, so the two tests below skip where it is
# absent. The skip lives in the fixture, not at module scope: a module-level
# importorskip would take the snapshot and the regression guard above down with
# it, and `UPDATE_GOLDEN=1 pytest python/tests/test_render.py` would silently
# record nothing.


@pytest.fixture(scope="module")
def built_pdf(tmp_path_factory, rendered_html):
    pytest.importorskip("weasyprint", reason="WeasyPrint needs system libraries")
    return render.write_pdf(
        rendered_html, tmp_path_factory.mktemp("pdf") / "calendar.pdf")


def test_calendar_is_exactly_one_page(built_pdf):
    """The whole point of the product. If this fails, nothing else matters."""
    pypdf = pytest.importorskip("pypdf")
    assert len(pypdf.PdfReader(built_pdf).pages) == 1


def test_page_is_us_letter(built_pdf):
    pypdf = pytest.importorskip("pypdf")
    box = pypdf.PdfReader(built_pdf).pages[0].mediabox
    assert (round(float(box.width)), round(float(box.height))) == (612, 792)


def test_the_page_is_not_empty(rendered_html, shipped_events):
    """Guards against the one-page test passing vacuously on an empty grid."""
    assert shipped_events, "no events in the shipped CSV"
    assert rendered_html.count("<td class=\"day") > 300  # 12 months x 42 cells
    assert "date-item" in rendered_html
