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


STYLESHEET_MARKER = "\n\n<!-- ===== python/styles/calendar.css ===== -->\n"


@pytest.fixture(scope="session")
def snapshot_text(rendered_html):
    """What the snapshot records: the page *and* the stylesheet that paints it.

    base.html links the stylesheet rather than inlining it, so an HTML-only
    snapshot saw none of the appearance. Changing the no-school fill from black
    to white left every test green and the snapshot byte-identical, while the
    printed page lost all its no-school days. CLAUDE.md promises the snapshot is
    the only review the printed page gets; recording the CSS beside the HTML is
    what makes that true.
    """
    css = (render.PYTHON_DIR / "styles" / "calendar.css").read_text(encoding="utf-8")
    return rendered_html + STYLESHEET_MARKER + css


def test_page_and_stylesheet_match_the_snapshot(snapshot_text, shipped_year, request):
    """Any change to the printed page shows up here as a reviewable diff.

    Intentional change? Re-record with:  UPDATE_GOLDEN=1 pytest python/tests
    """
    golden = (request.path.parent / "golden"
              / f"calendar-{shipped_year.label}.html")
    rendered_html = snapshot_text

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
# WeasyPrint needs system libraries, so everything below skips where it is
# absent. The skip lives in the fixtures, not at module scope: a module-level
# importorskip would take the snapshot and the regression guard above down with
# it, and `UPDATE_GOLDEN=1 pytest python/tests/test_render.py` would silently
# record nothing.


@pytest.fixture(scope="session")
def laid_out(rendered_html):
    """The page laid out once, shared by every test that needs geometry.

    Goes through render.layout_pages rather than calling WeasyPrint directly, so
    these tests exercise the same base_url wiring the real build depends on.
    """
    pytest.importorskip("weasyprint", reason="WeasyPrint needs system libraries")
    return render.layout_pages(rendered_html)


@pytest.fixture(scope="session")
def built_pdf(tmp_path_factory, rendered_html):
    """Written through render.write_pdf -- the function `build.py` itself calls.

    Deliberately not `laid_out.write_pdf(...)`: that skipped write_pdf entirely,
    so dropping its base_url or its mkdir left the suite green while
    `python python/build.py` wrote an unstyled PDF or crashed.
    """
    pytest.importorskip("weasyprint", reason="WeasyPrint needs system libraries")
    return render.write_pdf(rendered_html,
                            tmp_path_factory.mktemp("pdf") / "calendar.pdf")


def _boxes(page):
    """Every box on the page, with the chain of ancestors that reached it.

    WeasyPrint boxes carry no parent pointer, so track it on the way down.
    """
    root = getattr(page, "_page_box", None)
    if root is None:  # pragma: no cover - only on an unpinned WeasyPrint
        pytest.skip("this WeasyPrint does not expose page._page_box; "
                    "the geometry helpers need updating, not the page")

    def walk(box, chain=()):
        yield box, chain
        for child in getattr(box, "all_children", lambda: [])():
            yield from walk(child, chain + (box,))
    return walk(root)


def _week_rows(page):
    """The seven-cell rows of the twelve month grids.

    Seven cells excludes both the "Su Mo Tu..." thead rows and the two-column
    Important Dates row, which is a tbody tr as well.
    """
    rows = []
    for box, chain in _boxes(page):
        if getattr(box, "element_tag", None) != "tr":
            continue
        if not chain or getattr(chain[-1], "element_tag", None) != "tbody":
            continue
        cells = sum(1 for c in box.all_children()
                    if getattr(c, "element_tag", None) == "td")
        if cells == 7:
            rows.append(box)
    return rows


def _ptsa_circles(page):
    """(circle, enclosing week row) for every PTSA ring drawn in the grid.

    Identified by border-radius: 50%, which nothing else in a day cell uses.
    The legend circle has it too but sits outside any table row.
    """
    out = []
    for box, chain in _boxes(page):
        if getattr(box, "element_tag", None) != "span":
            continue
        radius = box.style["border_top_left_radius"][0]
        if not (radius.unit == "%" and radius.value == 50):
            continue
        row = next((a for a in reversed(chain)
                    if getattr(a, "element_tag", None) == "tr"), None)
        if row is not None:
            out.append((box, row))
    return out


def test_calendar_is_exactly_one_page(laid_out):
    """The whole point of the product. If this fails, nothing else matters."""
    assert len(laid_out.pages) == 1


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


def test_every_week_row_is_the_same_height(laid_out):
    """A PTSA circle must not make its week taller than the others.

    The circle is an inline-block in a ~14.7pt row. Sitting on the baseline at
    12pt it used to push its row to 19.3pt, so 22 of the 72 week rows were
    visibly taller. Negative vertical margins shrink what it contributes.
    """
    heights = [round(r.border_height(), 2) for r in _week_rows(laid_out.pages[0])]
    assert len(heights) == 72, f"expected 12 months x 6 rows, got {len(heights)}"
    assert len(set(heights)) == 1, (
        f"week rows are not a uniform height: {sorted(set(heights))}")


def test_ptsa_circles_stay_inside_their_row(laid_out):
    """Equal row heights are not enough -- the ring must also stay in its row.

    Shrinking the row without shrinking the circle left 34 rings drawing 4pt
    into the following week: the Nov 12 ring crossed the grid line, and where
    the day below was a black no-school cell it drew straight over it. Uniform
    height alone cannot see that, which is why this test exists beside it.
    """
    circles = _ptsa_circles(laid_out.pages[0])
    assert circles, "no PTSA circles found in the grid"

    spills = []
    for circle, row in circles:
        row_top, row_bottom = row.position_y, row.position_y + row.border_height()
        top, bottom = circle.position_y, circle.position_y + circle.border_height()
        # The ring now clears its row on both sides (~0.6px), so the tolerance
        # is only float noise -- not headroom for a partial fix.
        over = max(row_top - top, bottom - row_bottom)
        if over > 0.25:
            spills.append(round(over, 2))

    assert not spills, (
        f"{len(spills)} of {len(circles)} PTSA circles spill out of their week "
        f"row by up to {max(spills)}px"
    )
