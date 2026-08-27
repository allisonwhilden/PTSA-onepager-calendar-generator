import datetime as dt
import sys
import textwrap
from pathlib import Path

import pytest

# Tests import calendar_gen the same way build.py does.
PYTHON_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PYTHON_DIR))

REPO = PYTHON_DIR.parent

from calendar_gen.school_year import SchoolYear  # noqa: E402


@pytest.fixture(scope="session")
def repo() -> Path:
    return REPO


@pytest.fixture(scope="session")
def real_csv(repo: Path) -> Path:
    return repo / "data" / "all_events.csv"


@pytest.fixture(scope="session")
def years_dir(repo: Path) -> Path:
    return repo / "data" / "years"


@pytest.fixture
def year() -> SchoolYear:
    """A stand-in school year, so tests do not depend on the shipped config."""
    return SchoolYear(
        start_year=2025,
        organization="Test PTSA",
        early_release_start=dt.date(2025, 9, 10),
        last_day=dt.date(2026, 6, 17),
        boxed_days=frozenset({dt.date(2025, 9, 2), dt.date(2026, 6, 17)}),
    )


@pytest.fixture
def write_csv(tmp_path: Path):
    """Write a CSV from an indented string and return its path."""

    def _write(body: str, name: str = "events.csv") -> Path:
        path = tmp_path / name
        path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
        return path

    return _write
