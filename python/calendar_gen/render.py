"""Rendering the calendar to HTML, and from HTML to PDF.

Kept apart from the CLI so tests can snapshot the HTML without needing
WeasyPrint's system libraries installed.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .layout import ImportantDate, Month
from .school_year import SchoolYear

PACKAGE_DIR = Path(__file__).resolve().parent
PYTHON_DIR = PACKAGE_DIR.parent
TEMPLATES_DIR = PYTHON_DIR / "templates"


def render_html(
    year: SchoolYear,
    months: list[Month],
    important: list[ImportantDate],
    generated_at: dt.date | None = None,
) -> str:
    """The full calendar page as HTML.

    ``generated_at`` is a parameter rather than "today" so the output is
    reproducible -- otherwise the snapshot test would fail every midnight.
    """
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("calendar.html")
    return template.render(
        title=f"{year.organization} | {year.title}",
        header_lead=year.header_parts[0],
        header_accent=year.header_parts[1],
        year_label=year.label,
        months=months,
        important=important,
        generated_at=(generated_at or dt.date.today()).strftime("%b %d, %Y"),
    )


class WeasyPrintUnavailable(RuntimeError):
    """WeasyPrint, or the system libraries it needs, are not installed."""


def _load_weasyprint():
    try:
        from weasyprint import HTML
    except (ImportError, OSError) as exc:
        # OSError: the Python package is present but libpango and friends are
        # not, which raises at import. Both cases get the same clear message
        # rather than a traceback from inside the library.
        raise WeasyPrintUnavailable(
            f"WeasyPrint is unavailable ({exc}). Install its system libraries "
            f"-- see the Setup section of README.md."
        ) from exc
    return HTML


def layout_pages(html: str):
    """Lay the page out and return WeasyPrint's rendered document.

    The single place that knows the base_url the stylesheet link needs. Both
    write_pdf and count_pages go through it, so a test that measures geometry
    exercises the same wiring the real build uses.
    """
    HTML = _load_weasyprint()
    # base_url resolves the stylesheet link in base.html.
    return HTML(string=html, base_url=str(PYTHON_DIR)).render()


def write_pdf(html: str, out_path: Path) -> Path:
    """Render HTML to a PDF at ``out_path``."""
    document = layout_pages(html)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    document.write_pdf(target=str(out_path))
    return out_path


def count_pages(html: str) -> int | None:
    """How many pages this HTML renders to, or None if WeasyPrint is absent.

    Used by `--check` so the one-page promise is verified before a push, not
    only in CI where the remedy is far from whoever edited the CSV.
    """
    try:
        return len(layout_pages(html).pages)
    except WeasyPrintUnavailable:
        return None
