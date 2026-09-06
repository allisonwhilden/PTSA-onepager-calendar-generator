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

    #: Draw the PTSA circle around the number.
    circle: bool = False

    #: Prefix used when the event is listed in Important Dates.
    label_prefix: str = ""

    #: What to call this type to someone choosing it in the editor, and a
    #: sentence saying what it does to the page. Deliberately fuller than the
    #: printed legend, which is hand-set for a page with no room to spare and
    #: which only names the types that draw something. Both exist because they
    #: are read by different people in different places; this one is here so
    #: that adding a type cannot leave the editor offering a stale list.
    human: str = ""
    hint: str = ""

    @property
    def title(self) -> str:
        return self.human or self.name.replace("_", " ").title()

    @property
    def is_invisible(self) -> bool:
        """True when this type leaves no trace on the calendar grid.

        Days carrying an invisible event get an asterisk, because the grid alone
        gives the reader no hint that something is listed for that day.
        """
        return self.fill is None and not self.circle


#: Every type the calendar can draw. Adding a kind of date means adding a line here.
REGISTRY: dict[str, EventType] = {
    t.name: t
    for t in (
        EventType("no_school", fill="no_school", human="No school",
                  hint="Filled black on the grid. Holidays, breaks, staff days."),
        EventType("half_day", fill="half_day", human="Half day",
                  hint="Filled grey. Conference days and the last day."),
        EventType("early_release", fill="early_release",
                  human="Early release (one-off)",
                  hint="Bold. Ordinary Wednesdays are marked automatically -- "
                       "use this only for an early release that is not one."),
        EventType("closure_possible", fill="closure_possible",
                  human="Possible make-up day",
                  hint="Hatched. Days school runs only if snow days were used."),
        # Listed dates, drawn with nothing of their own. The first/last-day box
        # is a year-level mark set in the year config -- see boxed_days -- not a
        # property of these types.
        EventType("first_day", human="First day",
                  hint="Listed in the dates. The box on the grid comes from "
                       "boxed_days in the year config, not from this type."),
        EventType("last_day", human="Last day",
                  hint="Listed in the dates. Also used for quarter and "
                       "semester ends, which are not year boundaries."),
        EventType("ptsa_event", circle=True, label_prefix="PTSA: ",
                  human="PTSA event",
                  hint="Red circle on the grid, red in the dates list."),
        # Listed in Important Dates, but changes nothing about the school day.
        # Grades-due dates, deadlines, community events on an ordinary day.
        EventType("informational", human="Just listed",
                  hint="Appears in the dates list and changes nothing on the "
                       "grid. The day gets an asterisk so the grid points at it."),
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



def choices() -> list[EventType]:
    """The types to offer in the editor, in the order they are declared.

    Only the canonical ones. The aliases exist so that spellings already in the
    CSV keep working; offering them as new choices would spread them further.
    """
    return list(REGISTRY.values())


def known_names() -> list[str]:
    """Every accepted spelling, for error messages."""
    return sorted(set(REGISTRY) | set(ALIASES))
