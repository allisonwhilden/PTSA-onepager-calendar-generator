"""School-year configuration, loaded from data/years/<label>.toml.

Rolling the calendar to a new year is adding one config file and one CSV --
no code changes. See data/years/README.md.
"""

from __future__ import annotations

import datetime as dt
import tomllib
from dataclasses import dataclass
from pathlib import Path

#: The calendar prints August through July, so the grid is a full 12 months.
FIRST_MONTH = 8
WEDNESDAY = 2  # date.weekday(): Monday is 0


def label_for(start_year: int) -> str:
    """2025 -> '2025-26'."""
    return f"{start_year}-{(start_year + 1) % 100:02d}"


@dataclass(frozen=True)
class SchoolYear:
    """Everything that changes from one school year to the next."""

    start_year: int
    organization: str
    early_release_start: dt.date
    last_day: dt.date

    #: The word in the organization name drawn in the PTSA red. Split here
    #: rather than in the template, which used to recover it by deleting the
    #: literal "PTSA" from the name -- that mangled every other name.
    accent: str = "PTSA"

    #: Days drawn with the first/last-day box. These are the school year's own
    #: boundaries, which is why they live here rather than in the CSV -- the CSV
    #: uses first_day/last_day for per-population dates too (kindergarten, SNAPS,
    #: secondary semester ends), and boxing all of those would overstate what the
    #: legend promises.
    boxed_days: frozenset[dt.date] = frozenset()

    @property
    def label(self) -> str:
        return label_for(self.start_year)

    @property
    def title(self) -> str:
        return f"{self.label} Calendar"

    @property
    def first_printed_day(self) -> dt.date:
        return dt.date(self.start_year, FIRST_MONTH, 1)

    @property
    def last_printed_day(self) -> dt.date:
        end = dt.date(self.start_year + 1, FIRST_MONTH, 1)
        return end - dt.timedelta(days=1)

    @property
    def header_parts(self) -> tuple[str, str]:
        """The title split into a plain lead and an accented tail.

        Falls back to the whole name unaccented when it does not end in the
        accent word, so an unexpected name renders plainly instead of wrongly.
        """
        if self.accent and self.organization.endswith(self.accent):
            return self.organization[: -len(self.accent)].strip(), self.accent
        return self.organization, ""

    def months(self) -> list[tuple[int, int]]:
        """(year, month) for each printed month, August through July."""
        out = []
        for i in range(12):
            month = (FIRST_MONTH - 1 + i) % 12 + 1
            year = self.start_year + (1 if month < FIRST_MONTH else 0)
            out.append((year, month))
        return out

    def early_release_wednesdays(self) -> list[dt.date]:
        """Every Wednesday from the early-release start through the last day."""
        day = self.early_release_start
        day += dt.timedelta(days=(WEDNESDAY - day.weekday()) % 7)
        out = []
        while day <= self.last_day:
            out.append(day)
            day += dt.timedelta(days=7)
        return out


def config_path(years_dir: str | Path, start_year: int) -> Path:
    return Path(years_dir) / f"{label_for(start_year)}.toml"


def available_years(years_dir: str | Path) -> list[int]:
    """Start years that have a config file, oldest first."""
    years = []
    for path in Path(years_dir).glob("*.toml"):
        head = path.stem.split("-")[0]
        if head.isdigit():
            years.append(int(head))
    return sorted(years)


def current_start_year(today: dt.date | None = None) -> int:
    """The school year that today falls in.

    August onwards belongs to the year starting now; January to July belongs to
    the year that started last August.
    """
    today = today or dt.date.today()
    return today.year if today.month >= FIRST_MONTH else today.year - 1


def resolve_start_year(
    years_dir: str | Path,
    requested: int | None = None,
    today: dt.date | None = None,
) -> tuple[int, str]:
    """Pick which school year to build, and say why.

    An explicit ``--year`` always wins. Otherwise prefer the year we are
    actually in, and fall back to the newest config on disk so the build keeps
    working in the gap before next year's dates are added.
    """
    years = available_years(years_dir)
    if not years:
        raise FileNotFoundError(
            f"No school-year configs in {years_dir}. "
            f"Add one -- see data/years/README.md."
        )

    if requested is not None:
        if requested not in years:
            have = ", ".join(label_for(y) for y in years)
            raise FileNotFoundError(
                f"No config for {label_for(requested)} in {years_dir} (have: {have})"
            )
        return requested, "requested with --year"

    current = current_start_year(today)
    if current in years:
        return current, "current school year"

    newest = years[-1]
    return newest, (
        f"no config for the current school year ({label_for(current)}) yet, "
        f"so building the newest available"
    )


def load(years_dir: str | Path, start_year: int) -> SchoolYear:
    """Read one school year's config file."""
    path = config_path(years_dir, start_year)
    if not path.exists():
        raise FileNotFoundError(f"School-year config not found: {path}")

    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    calendar = raw.get("calendar", {})
    dates = raw.get("dates", {})
    problems: list[str] = []

    for key in ("early_release_start", "last_day"):
        if key not in dates:
            problems.append(f"[dates] is missing {key}")
        elif not isinstance(dates[key], dt.date):
            problems.append(
                f"[dates] {key} must be a bare date like 2026-09-09, "
                f"not {dates[key]!r} -- quoting it makes it a string"
            )

    boxed = dates.get("boxed_days", [])
    if not isinstance(boxed, list):
        problems.append("[dates] boxed_days must be a list of dates")
        boxed = []
    for value in boxed:
        if not isinstance(value, dt.date):
            problems.append(
                f"[dates] boxed_days entry {value!r} must be a bare date "
                f"like 2026-09-01, not a quoted string"
            )

    if problems:
        raise ValueError(f"{path}:\n  " + "\n  ".join(problems))

    year = SchoolYear(
        start_year=start_year,
        organization=calendar.get("organization", "PTSA"),
        accent=calendar.get("accent", "PTSA"),
        early_release_start=dates["early_release_start"],
        last_day=dates["last_day"],
        boxed_days=frozenset(boxed),
    )

    # Dates that fall outside the printed span draw nothing at all, silently --
    # the classic symptom of a config copied forward without editing.
    if year.early_release_start > year.last_day:
        problems.append(
            f"[dates] early_release_start ({year.early_release_start}) is after "
            f"last_day ({year.last_day}), so no Wednesday would be marked"
        )
    span = (year.first_printed_day, year.last_printed_day)
    for key, value in (("early_release_start", year.early_release_start),
                       ("last_day", year.last_day)):
        if not span[0] <= value <= span[1]:
            problems.append(
                f"[dates] {key} ({value}) is outside the {year.label} calendar, "
                f"which covers {span[0]} to {span[1]}"
            )
    for value in sorted(year.boxed_days):
        if not span[0] <= value <= span[1]:
            problems.append(
                f"[dates] boxed_days entry {value} is outside the {year.label} "
                f"calendar ({span[0]} to {span[1]}), so no box would be drawn"
            )

    if problems:
        raise ValueError(f"{path}:\n  " + "\n  ".join(problems))

    return year
