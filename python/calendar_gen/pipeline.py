"""Everything between "here is a CSV and a config" and "here is a page".

`build.py` and the web editor both come through here. They ask the same
question -- *may this calendar be published?* -- and they have to get the same
answer, because the whole point of the editor is that the PDF you preview is
the PDF that goes home with families.

The only reliable way to make two callers agree is to give them one
implementation. `DECISIONS.md` records what happened last time this project had
two: a second renderer drifted from the first until they disagreed about what
the calendar said, and five ordinary school days printed as "No School". A
second *validator* would fail the same way and be harder to see, because
nothing would look wrong until the day someone published a blank page.

So: the rules live here. `build.py` turns the result into exit codes and
stderr; the editor turns it into things to click. Neither decides anything.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

from . import events as events_mod
from . import layout, render, school_year
from .school_year import SchoolYear


class Blocked(Exception):
    """A calendar that cannot be built at all.

    Distinct from a calendar that builds but should not be *published*: this is
    a missing config, an unparseable CSV, an unknown event type. Carries the
    exit code build.py has always used for its kind, so the deploy workflow --
    which branches on those numbers -- keeps reading them the same way.
    """

    def __init__(self, message: str, code: int = 1, year=None, why: str = "",
                 notices=None):
        super().__init__(message)
        self.code = code
        #: What was known before the failure, so the caller can still say which
        #: year it was building and which rows fell outside it. The blank-page
        #: error is most often a half-finished year roll, and the row numbers
        #: are the whole diagnosis -- printing only "the calendar would be
        #: blank" leaves someone to find them by eye.
        self.year = year
        self.why = why
        self.notices = notices or []


@dataclass
class Build:
    """A built calendar, plus everything anyone needs to judge it.

    `warnings` and `notices` are deliberately separate. A notice means a row
    sits outside the printed span -- next year's dates staged early, last
    year's left in place -- which is a normal state during a year roll and must
    never fail a build. Warnings are the ones worth acting on.
    """

    year: SchoolYear
    why: str
    events: list
    warnings: list
    notices: list
    months: list
    important: list
    html: str
    generated_at: dt.date | None = None
    _doc: object | None = field(default=None, repr=False)
    _laid_out: bool = field(default=False, repr=False)

    @property
    def label(self) -> str:
        return self.year.label

    @property
    def filename(self) -> str:
        """What the PDF is called. The published copy is renamed by the deploy
        workflow; this is the name a person downloading it should see."""
        return f"{self.year.organization.replace(' ', '')}-{self.year.label}-Calendar.pdf"

    def document(self):
        """The laid-out page, or None if WeasyPrint is unavailable.

        Laid out at most once. Counting the pages and writing the PDF are the
        same work done twice otherwise, and the editor does both on every save:
        one layout is most of the second it has to answer in.
        """
        if not self._laid_out:
            self._laid_out = True
            try:
                self._doc = render.layout_pages(self.html)
            except render.WeasyPrintUnavailable:
                self._doc = None
        return self._doc

    def page_count(self) -> int | None:
        """None when WeasyPrint is missing, which is not the same as unknown --
        callers must not treat it as a failure."""
        doc = self.document()
        return None if doc is None else len(doc.pages)

    def fits_one_page(self) -> bool | None:
        pages = self.page_count()
        return None if pages is None else pages == 1

    def _require_document(self):
        doc = self.document()
        if doc is None:
            # Raises WeasyPrintUnavailable with the real message, which names
            # the missing system libraries rather than saying "None". Returned
            # rather than discarded: if this call ever succeeds where the first
            # failed, callers got None back and an AttributeError instead of
            # either a PDF or the clear error this line exists to produce.
            return render.layout_pages(self.html)
        return doc

    def pdf_bytes(self) -> bytes:
        return self._require_document().write_pdf()

    def write_pdf(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._require_document().write_pdf(target=str(path))
        return path

    def publish_problems(self, strict: bool = False) -> list[str]:
        """Reasons this calendar should not be published, in plain English.

        Empty means go. Everything here is a condition the calendar survives --
        it renders, you can look at it -- but that no one should put behind a
        link families rely on.
        """
        problems = []
        pages = self.page_count()
        if pages is not None and pages != 1:
            problems.append(
                f"The calendar renders on {pages} pages. It has to fit on one -- "
                f"remove or shorten a few entries."
            )
        if strict and self.warnings:
            problems.append(
                f"{len(self.warnings)} warning(s) treated as errors (--strict). "
                f"They are listed above."
            )
        return problems


def load_year(years_dir: Path, requested: int | None = None,
              require_current: bool = False) -> tuple[SchoolYear, str]:
    """Pick and load the school year, or raise Blocked with build.py's code.

    ``require_current`` raises with code 3, which the deploy workflow reads as
    "the year has ended, publish nothing, this is routine". Every other failure
    here is a real one and must not borrow that number -- a real error reported
    as a routine skip is how a broken build gets a green check.
    """
    try:
        start_year, why = school_year.resolve_start_year(years_dir, requested)
        year = school_year.load(years_dir, start_year)
    except (FileNotFoundError, ValueError) as exc:
        raise Blocked(str(exc), code=2) from exc

    if require_current:
        current = school_year.current_start_year()
        if start_year != current:
            wanted = school_year.label_for(current)
            raise Blocked(
                f"the current school year is {wanted}, but this build is "
                f"{year.label} ({why}).\n"
                f"       Add data/years/{wanted}.toml and this year's rows in "
                f"the event CSV before publishing.",
                code=3,
            )
    return year, why


def build(data_csv: Path, years_dir: Path, requested: int | None = None,
          require_current: bool = False,
          generated_at: dt.date | None = None) -> Build:
    """Validate and lay out one school year. Raises Blocked if it cannot."""
    year, why = load_year(years_dir, requested, require_current)

    try:
        all_events, warnings = events_mod.load_events(data_csv)
    except events_mod.ValidationError as exc:
        raise Blocked(str(exc), code=1) from exc
    except FileNotFoundError as exc:
        raise Blocked(str(exc), code=2) from exc

    notices = events_mod.outside_year(
        all_events, year.first_printed_day, year.last_printed_day
    )

    by_date = layout.events_by_date(all_events, year)
    months = layout.build_months(by_date, year)
    important = layout.build_important_dates(all_events, year)

    # The half-finished year roll -- a new config against last year's CSV --
    # otherwise passes every other check and renders a page with nothing on it.
    if not important:
        name = Path(data_csv).name
        if all_events:
            reason = (f"none of the {len(all_events)} rows in {name} fall inside "
                      f"{year.label} ({year.first_printed_day} to "
                      f"{year.last_printed_day})")
        else:
            reason = f"{name} has no event rows"
        raise Blocked(f"{reason}, so the calendar would be blank.", code=1,
                      year=year, why=why, notices=notices)

    # render_html already treats None as today.
    html = render.render_html(year, months, important, generated_at=generated_at)

    return Build(
        year=year, why=why, events=all_events, warnings=warnings,
        notices=notices, months=months, important=important, html=html,
        generated_at=generated_at,
    )
