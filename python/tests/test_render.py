"""End-to-end checks on the published artifact.

These tests follow whatever year the repo currently ships, rather than pinning
2025. Rolling to a new year is meant to be a config file and a CSV; a test that
hardcodes the year turns that roll red, and -- worse -- would keep asserting
"one page" about a year nobody is publishing any more.
"""

import datetime as dt
import difflib
import os
import re

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


LINK_TAG = re.compile(r"<link\b[^>]*>")
ATTR = re.compile(r"""\b(\w+)=(?:["']([^"']*)["']|([^\s>]+))""")


def linked_stylesheets(html: str) -> list[str]:
    """The hrefs base.html actually links, in document order.

    Read out of the rendered page rather than hardcoded, so a stylesheet added
    to the template is snapshotted the moment it is linked. Hardcoding
    styles/calendar.css would leave a second sheet -- this repo has carried
    calendar-backup.css before -- free to repaint the page unreviewed.

    Attributes are parsed per tag, in any order, quoted or not. A pattern
    requiring rel= before href= silently skips `<link href=".." rel="stylesheet">`
    and one requiring quotes skips `<link rel=stylesheet href=..>`; both are
    ordinary ways to write the tag, and skipping either is exactly the blind
    spot this function exists to close, made worse by being invisible -- the
    sheet just never reaches the snapshot, and `assert hrefs` still passes on
    whichever sheet was found first.
    """
    out = []
    for tag in LINK_TAG.findall(html):
        attrs = {name: quoted or bare
                 for name, quoted, bare in ATTR.findall(tag)}
        if attrs.get("rel", "").lower() == "stylesheet" and attrs.get("href"):
            out.append(attrs["href"])
    return out


@pytest.fixture(scope="session")
def snapshot_text(rendered_html):
    """What the snapshot records: the page *and* the stylesheets that paint it.

    base.html links its stylesheet rather than inlining it, so an HTML-only
    snapshot saw none of the appearance. Changing the no-school fill from black
    to white left every test green and the snapshot byte-identical, while the
    printed page lost all its no-school days. CLAUDE.md promises the snapshot is
    the only review the printed page gets; recording the CSS beside the HTML is
    what makes that true.
    """
    hrefs = linked_stylesheets(rendered_html)
    assert hrefs, "the page links no stylesheet -- it would print unstyled"
    parts = [rendered_html]
    for href in hrefs:
        css = (render.PYTHON_DIR / href).read_text(encoding="utf-8")
        parts.append(f"\n\n<!-- ===== python/{href} ===== -->\n{css}")
    return "".join(parts)


def test_page_and_stylesheet_match_the_snapshot(snapshot_text, shipped_year, request):
    """Any change to the printed page shows up here as a reviewable diff.

    Intentional change? Re-record with:  UPDATE_GOLDEN=1 pytest python/tests
    """
    golden = (request.path.parent / "golden"
              / f"calendar-{shipped_year.label}.html")

    if os.environ.get("UPDATE_GOLDEN"):
        golden.parent.mkdir(exist_ok=True)
        golden.write_text(snapshot_text, encoding="utf-8")
        pytest.skip(f"recorded {golden.name}")

    assert golden.exists(), (
        f"No snapshot for {shipped_year.label}. This year's page has never been "
        f"reviewed -- look it over, then record it with "
        f"UPDATE_GOLDEN=1 pytest python/tests/test_render.py"
    )
    expected = golden.read_text(encoding="utf-8")

    if snapshot_text != expected:
        diff = "\n".join(difflib.unified_diff(
            expected.splitlines(), snapshot_text.splitlines(),
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


def _require_weasyprint():
    """Skip unless WeasyPrint can actually be used.

    Deliberately not pytest.importorskip: that catches ImportError only, and the
    failure this suite promises to skip on -- the Python package installed but
    libpango and friends absent -- raises OSError at import. With importorskip
    those tests failed with a traceback from inside the library on exactly the
    machine the README tells contributors they will skip on.

    render._load_weasyprint already collapses both cases into one clear error,
    and it is the path the real build takes, so going through it keeps the two
    in step.
    """
    try:
        render._load_weasyprint()
    except render.WeasyPrintUnavailable as exc:
        pytest.skip(str(exc))


@pytest.fixture(scope="session")
def laid_out(rendered_html):
    """The page laid out once, shared by every test that needs geometry.

    Goes through render.layout_pages rather than calling WeasyPrint directly, so
    these tests exercise the same base_url wiring the real build depends on.
    """
    _require_weasyprint()
    return render.layout_pages(rendered_html)


@pytest.fixture(scope="session")
def built_pdf(tmp_path_factory, rendered_html):
    """Written through render.write_pdf -- the function `build.py` itself calls.

    Deliberately not `laid_out.write_pdf(...)`: that skipped write_pdf entirely,
    so dropping its base_url or its mkdir left the suite green while
    `python python/build.py` wrote an unstyled PDF or crashed.
    """
    _require_weasyprint()
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


def _boxes_of(box, chain=()):
    """Every box under `box`, with the ancestors that reached it."""
    yield box, chain
    for child in getattr(box, "all_children", lambda: [])():
        yield from _boxes_of(child, chain + (box,))


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


PAPER = (1.0, 1.0, 1.0)


def _over(rgba, backdrop=PAPER):
    """`rgba` composited onto `backdrop`, as (r, g, b).

    Alpha is not optional. Reading the raw channels and ignoring it scores
    rgba(0, 0, 0, 0.12) -- a near-white cell -- as pure black, and
    rgba(255, 255, 255, 0.05) as pure white.
    """
    r, g, b, a = rgba
    return tuple(a * c + (1 - a) * back for c, back in zip((r, g, b), backdrop))


def _luminance(rgb):
    def channel(v):
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(fg_rgb, bg_rgb):
    a, b = _luminance(fg_rgb), _luminance(bg_rgb)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def _spills(circles, tolerance: float = 0.01) -> list[float]:
    """How far each mark is drawn outside its week row, where that is at all.

    Measured as ink, not layout: from border_box_y() (position_y is the *margin*
    box, and these marks carry a negative margin-top -- mixing the two is how a
    guard once certified 34 rings as inside their row while every one of them
    sat 0.59px above it) and widened by outline_width, since an outline draws
    outside the border box and .day.diamond.circle span has one.

    One implementation, two callers: this measurement has been wrong once
    already, and it should not be possible to fix it in one test and not the
    other. The tolerance is float noise, not headroom for a partial fix -- it
    was 0.05 and hid a mark drawing 0.04px below its row, so it is 0.01 now.
    Every mark currently clears by more than half a pixel.
    """
    out = []
    for circle, row in circles:
        row_top, row_bottom = row.position_y, row.position_y + row.border_height()
        outline = circle.style["outline_width"]
        top = circle.border_box_y() - outline
        bottom = circle.border_box_y() + circle.border_height() + outline
        over = max(row_top - top, bottom - row_bottom)
        if over > tolerance:
            out.append(round(over, 2))
    return out


def test_calendar_is_exactly_one_page(built_pdf):
    """The whole point of the product. If this fails, nothing else matters.

    Counted in the written PDF, because the PDF is what goes home with
    families. Counting `laid_out.pages` instead would be the very call
    test_count_pages_reports_one_for_the_shipped_page already makes --
    count_pages is `len(layout_pages(html).pages)` -- so the one-page promise
    would rest on the same computation twice and on nothing that opens the
    file. built_pdf is already rendered for test_page_is_us_letter.
    """
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
    _require_weasyprint()
    assert render.count_pages(rendered_html) == 1


@pytest.fixture(scope="session")
def stress_page():
    """A page where one day carries every mark at once: boxed, circled, closed.

    No day in the shipped CSV is both boxed and circled, so
    `.day.diamond.circle span` -- and the no-school recolouring of it -- render
    nowhere on the real page. Two review rounds asserted things about those
    rules that no test could see. They exist for the year a first or last day
    lands on a PTSA event or inside a closure, which is precisely the year
    nobody will be reading the CSS, so this builds that day on purpose.
    """
    _require_weasyprint()
    # Two digits on purpose: a bold "31" is 8.9px wide, and it was a
    # single-digit stress day that let a mark ship whose content box was 8.0px.
    # 8/31 is also a real boxed day in the shipped config.
    marked = dt.date(2026, 8, 31)
    year = school_year.SchoolYear(
        start_year=2026,
        organization="Horace Mann PTSA",
        early_release_start=dt.date(2026, 9, 9),
        last_day=dt.date(2027, 6, 16),
        boxed_days=frozenset({marked}),
    )
    events = [
        ev.Event(marked, marked, et.resolve("ptsa_event"), "Ring"),
        ev.Event(marked, marked, et.resolve("no_school"), "Closed"),
    ]
    html = render.render_html(
        year,
        layout.build_months(layout.events_by_date(events, year), year),
        layout.build_important_dates(events, year),
        generated_at=FROZEN,
    )
    return render.layout_pages(html)


def _marked_span(page):
    """The span on the stress page's every-mark day, with the cell it sits in.

    The cell is the *outermost* td-tagged ancestor. WeasyPrint wraps cell
    content in anonymous LineBox and TextBox boxes that report element_tag "td"
    as well but paint nothing, and those are the innermost ones: taking the last
    td in the chain returns a LineBox whose background is transparent black.
    Read that way, this test's "is the cell really black?" precondition passed
    on rgba(0, 0, 0, 0) no matter what the stylesheet said.
    """
    for box, chain in _boxes(page):
        if getattr(box, "element_tag", None) != "span":
            continue
        cell = next((a for a in chain
                     if getattr(a, "element_tag", None) == "td"
                     and getattr(a, "background", None) is not None), None)
        if cell is None:
            continue
        classes = set(cell.element.get("class", "").split())
        if {"mark-no_school", "diamond", "circle"} <= classes:
            return box, cell
    pytest.fail("the stress page never drew a boxed, circled, no-school day")


def test_a_day_carrying_every_mark_stays_inside_its_row(stress_page):
    """The combined mark is the widest thing the stylesheet puts in a cell.

    An outline draws outside the border box, so this mark needs more room than
    the plain ring and is the one that overflows first.
    """
    circles = _ptsa_circles(stress_page.pages[0])
    outlined = [(c, r) for c, r in circles if c.style["outline_width"]]
    assert outlined, "the stress page drew no outlined mark"

    spills = _spills(outlined)
    assert not spills, (
        f"{len(spills)} of {len(outlined)} boxed-and-circled marks spill out of "
        f"their week row by up to {max(spills)}px"
    )


def test_the_date_fits_inside_every_mark(stress_page, laid_out):
    """A mark sized to fit its row must still hold the date it encircles.

    Shrinking the boxed-and-circled mark to clear the week row left an 8.0px
    content box around a bold two-digit date 8.9px wide, so "31" overran its own
    ring on both sides. The row-fit guard could not see it -- overflowing text
    does not change the box -- and the stress day was single-digit, so nothing
    rendered a case where it showed.
    """
    for page, what in ((stress_page.pages[0], "stress"), (laid_out.pages[0], "shipped")):
        marks = [c for c, _ in _ptsa_circles(page)]
        assert marks, f"no marks found on the {what} page"
        for mark in marks:
            for box, _ in _boxes_of(mark):
                text = getattr(box, "text", None)
                if not text:
                    continue
                assert box.width <= mark.width, (
                    f"{text!r} is {box.width:.2f}px wide in a {mark.width:.2f}px "
                    f"mark on the {what} page, so it overruns its own ring"
                )


def test_marks_on_a_no_school_cell_are_visible(stress_page):
    """A no-school cell is solid black, so a black mark on it draws nothing.

    The ring was recoloured white when 8/27 (Colt Corral) sat inside the August
    LEAP block; the box and its outline were left black, which on a closure day
    would print a black box on a black cell while the legend still promised a
    First/Last key. That August block is out of the CSV now, so no shipped day
    exercises either branch -- which is why this runs on stress_page rather than
    pointing at a date on the real calendar.
    """
    span, cell = _marked_span(stress_page.pages[0])

    cell_rgb = _over(cell.style["background_color"])
    assert _luminance(cell_rgb) < 0.2, (
        f"expected a black no-school cell to test against, got {cell_rgb}")

    marks = {"border": span.style["border_top_color"]}
    if span.style["outline_width"]:
        marks["outline"] = span.style["outline_color"]

    invisible = {name: tuple(round(c, 2) for c in _over(colour, cell_rgb))
                 for name, colour in marks.items()
                 if _luminance(_over(colour, cell_rgb)) < 0.5}
    assert not invisible, (
        f"drawn dark on a black no-school cell, so invisible: {invisible}")


def test_every_day_number_is_legible_on_its_cell(laid_out):
    """No date may disappear into the fill behind it.

    In practice this pins one thing: how light the weekend grey may go. Every
    fill -- no-school, half-day, closure -- sets its own colour in a rule that
    comes after .day.weekend, so a weekend that lands on one keeps that rule's
    black or white numeral and is never at risk. I wrote this test believing a
    closure crossing a Saturday would strand grey-on-grey; it would not, and
    the first version of this docstring said so wrongly.

    Weekend numerals are deliberately light -- nobody looks up a Saturday -- and
    sit at 3.36:1 on paper, under the 4.5:1 you would want for text meant to be
    read. That is the intent, so the floor is 3:1 and it is close enough to
    bite: the #999 the stylesheet started with is 2.85:1 and fails here.

    Cells are taken one per element, outermost first. WeasyPrint wraps cell
    content in anonymous LineBox and TextBox boxes that also report element_tag
    "td"; and filtering on `background is not None` -- which an earlier version
    did to skip them -- silently dropped every unfilled cell, which is all 315
    weekend days, leaving the test vacuous and green.
    """
    faint = []
    seen = set()
    for box, _ in _boxes(laid_out.pages[0]):
        if getattr(box, "element_tag", None) != "td":
            continue
        element = getattr(box, "element", None)
        if element is None or id(element) in seen:
            continue
        seen.add(id(element))
        classes = set((element.get("class") or "").split())
        if "day" not in classes or "empty" in classes:
            continue
        text = "".join(t.text for t, _ in _boxes_of(box) if getattr(t, "text", None))
        if not text.strip():
            continue
        cell_rgb = _over(box.style["background_color"])
        ink_rgb = _over(box.style["color"], cell_rgb)
        ratio = _contrast(ink_rgb, cell_rgb)
        if ratio < 3.0:
            faint.append((text.strip(), sorted(classes - {"day"}), round(ratio, 2)))

    assert len(seen) > 500, f"only inspected {len(seen)} day cells; expected ~1000"
    assert not faint, (
        f"{len(faint)} day numbers fall below 3:1 against their own cell: "
        f"{faint[:5]}"
    )


def test_the_footer_sits_at_the_bottom_of_the_page(laid_out):
    """The "Updated ..." line belongs on the bottom edge, not under the list.

    It is put there by exactly two declarations -- display:flex on
    .page-wrapper and flex:1 on .page-main -- and removing either drops it 55pt
    back up the page. Everything that looks like it would do the job instead
    (min-height:100%, min-height:calc(), margin-top:auto on the footer) computes
    away to nothing in this WeasyPrint and leaves the footer mid-page with the
    suite green. That is why this is a test and not a comment.
    """
    page = laid_out.pages[0]
    root = page._page_box
    html_box = next(b for b, _ in _boxes(page)
                    if getattr(b, "element_tag", None) == "html")
    printable_bottom = html_box.position_y + root.height

    footers = [b for b, _ in _boxes(page)
               if getattr(b, "element", None) is not None
               and "page-footer" in (b.element.get("class") or "").split()]
    assert footers, "no footer on the page"
    bottom = max(f.position_y + f.border_height() for f in footers)

    gap_pt = (printable_bottom - bottom) / (96 / 72)
    assert -0.5 <= gap_pt <= 4, (
        f"the footer ends {gap_pt:.1f}pt above the bottom of the printable "
        f"area; it should sit on it"
    )


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

    Measured from border_box_y(), not position_y. position_y is the *margin*
    box, and .day.circle span carries a negative margin-top; adding a border
    height to a margin-box origin under-reports the top overhang by exactly that
    margin. The first version of this test did that, so it passed while all 34
    rings sat 0.59px above their row -- it reported "inside" for the defect it
    existed to catch, and failed once the CSS was actually correct.
    """
    circles = _ptsa_circles(laid_out.pages[0])
    assert circles, "no PTSA circles found in the grid"
    spills = _spills(circles)
    assert not spills, (
        f"{len(spills)} of {len(circles)} PTSA circles spill out of their week "
        f"row by up to {max(spills)}px"
    )
