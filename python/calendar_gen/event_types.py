"""The one place an event type is defined.

A type that appears in the CSV but is not declared here is a validation error,
never a guess. See DECISIONS.md #2 for why.

This registry says *how* a type is drawn. It says nothing about which dates
belong on the calendar -- that is the CSV author's call.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class EventType:
    """How one kind of event is drawn."""

    name: str

    #: Fill/weight applied to the day cell, as a CSS class suffix (``mark-<fill>``).
    #: ``None`` means the day looks like any other day.
    fill: str | None = None

    #: Draw the first/last-day box around the number.
    box: bool = False

    #: Draw the PTSA circle around the number.
    circle: bool = False

    #: Prefix used when the event is listed in Important Dates.
    label_prefix: str = ""

    @property
    def is_invisible(self) -> bool:
        """True when this type leaves no trace on the calendar grid.

        Days carrying an invisible event get an asterisk, because the grid alone
        gives the reader no hint that something is listed for that day.
        """
        return self.fill is None and not self.box and not self.circle


#: Every type the calendar can draw. Adding a kind of date means adding a line here.
REGISTRY: dict[str, EventType] = {
    t.name: t
    for t in (
        EventType("no_school", fill="no_school"),
        EventType("half_day", fill="half_day"),
        EventType("early_release", fill="early_release"),
        EventType("closure_possible", fill="closure_possible"),
        # These are listed dates, not the box. The box is a year-level
        # boundary set in the year config -- see SchoolYear.boxed_days.
        EventType("first_day"),
        EventType("last_day"),
        EventType("ptsa_event", circle=True, label_prefix="PTSA: "),
        # Listed in Important Dates, but changes nothing about the school day.
        # Grades-due dates, deadlines, community events on an ordinary day.
        EventType("informational"),
    )
}


#: Spellings accepted from the CSV that resolve to a declared type.
ALIASES: dict[str, str] = {
    "first_day_1_12": "first_day",
    "first_day_k": "first_day",
    "holiday": "no_school",
    "closure_day": "closure_possible",
    "possible_school_day": "closure_possible",
    "potential_school_day": "closure_possible",
    # Dates that are worth listing but do not change the school day.
    "grades_due": "informational",
    "kinder_family_conn": "informational",
}


class UnknownEventType(KeyError):
    """Raised for a type that is neither declared nor aliased."""


def resolve(raw: str) -> EventType:
    """Look up a CSV ``type`` value. Raises :class:`UnknownEventType` if undeclared."""
    key = (raw or "").strip().lower()
    key = ALIASES.get(key, key)
    try:
        return REGISTRY[key]
    except KeyError:
        raise UnknownEventType(raw) from None



def known_names() -> list[str]:
    """Every accepted spelling, for error messages."""
    return sorted(set(REGISTRY) | set(ALIASES))
