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


def write_pdf(html: str, out_path: Path) -> Path:
    """Render HTML to a PDF at ``out_path``."""
    from weasyprint import HTML  # slow import, and needs system libraries

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # base_url resolves the stylesheet link in base.html.
    HTML(string=html, base_url=str(PYTHON_DIR)).write_pdf(target=str(out_path))
    return out_path
