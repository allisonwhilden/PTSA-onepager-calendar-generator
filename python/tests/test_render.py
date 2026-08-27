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

from calendar_gen import event_types as et
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


def test_deadline_rows_in_the_shipped_csv_draw_nothing(real_csv):
    """Regression guard for the bug that started the rewrite.

    Deliberately keyed on the *raw* CSV spelling rather than on is_invisible.
    Testing via is_invisible is tautological -- flip the alias to no_school and
    those rows simply stop being invisible, so the assertion never fires. This
    asserts the mapping itself: a row that only records a deadline must never
    resolve to a type that blacks out a school day.
    """
    import csv as _csv

    with open(real_csv, newline="", encoding="utf-8-sig") as handle:
        raw_types = {(r.get("type") or "").strip()
                     for r in _csv.DictReader(handle)}
    raw_types.discard("")

    deadline_spellings = {"grades_due", "kinder_family_conn"}
    present = raw_types & deadline_spellings
    assert present, f"expected deadline rows in the CSV, saw {sorted(raw_types)}"

    for spelling in sorted(present):
        kind = et.resolve(spelling)
        assert kind.fill is None, (
            f"{spelling!r} resolves to fill={kind.fill!r}; a deadline must not "
            f"change how the school day is drawn"
        )
        assert not kind.circle
        assert kind.is_invisible


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


def test_count_pages_reports_one_for_the_shipped_page(rendered_html):
    """`--check` uses this to protect the one-page promise before a push."""
    pytest.importorskip("weasyprint", reason="WeasyPrint needs system libraries")
    assert render.count_pages(rendered_html) == 1
