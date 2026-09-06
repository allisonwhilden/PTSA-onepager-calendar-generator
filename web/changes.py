"""What changed, in the words a PTSA volunteer would use.

Before publishing, someone has to be able to see what they are about to send to
every family in the school. A unified diff does not tell them that: it tells
them that a line beginning `2026-09-17,,,ptsa_event` became one beginning
`2026-09-24,,,ptsa_event`. What they need to read is "Bike Derby moved from
Sep 17 to Sep 24".

Rows have no identity in the file -- no id column -- so "moved" has to be
inferred. The rule is deliberately conservative: rows are matched by label,
because that is the part a person is least likely to change at the same time as
the date, and anything that cannot be matched is reported as an add and a
remove rather than guessed at. Overstating a change is a nuisance; understating
one hides an edit from the person checking it.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from .csvio import Row


@dataclass(frozen=True)
class Change:
    kind: str          # "added" | "removed" | "moved" | "edited"
    label: str
    detail: str

    def __str__(self) -> str:
        return f"{self.label}: {self.detail}" if self.detail else self.label


def pretty_date(iso: str) -> str:
    """2026-09-17 -> Sep 17. Anything unparseable comes back as it was typed."""
    try:
        return dt.date.fromisoformat(iso).strftime("%b %-d")
    except ValueError:
        return iso or "(no date)"


def when(row: Row) -> str:
    if row.is_range:
        start, end = pretty_date(row.start_date), pretty_date(row.end_date)
        return f"{start}-{end}" if start != end else start
    return pretty_date(row.date)


def _key(row: Row) -> str:
    return row.label.strip().casefold()


def summarise(before: list[Row], after: list[Row]) -> list[Change]:
    """The differences, as a list of things a person can check off.

    Matching is by label. Two rows sharing a label -- the repeating PTSA
    meetings do -- are matched up in the order they appear, so moving the third
    board meeting reads as one move rather than a wholesale replacement.
    """
    old_by_label: dict[str, list[Row]] = {}
    for row in before:
        old_by_label.setdefault(_key(row), []).append(row)
    new_by_label: dict[str, list[Row]] = {}
    for row in after:
        new_by_label.setdefault(_key(row), []).append(row)

    changes: list[Change] = []

    for key in list(new_by_label):
        olds = old_by_label.get(key, [])
        news = new_by_label[key]
        for old, new in zip(olds, news):
            changes.extend(_compare(old, new))
        for extra in news[len(olds):]:
            changes.append(Change("added", extra.label,
                                  f"added on {when(extra)}"))
        # Consumed, so what is left in old_by_label is genuinely gone.
        old_by_label[key] = olds[len(news):]

    for leftovers in old_by_label.values():
        for gone in leftovers:
            changes.append(Change("removed", gone.label,
                                  f"removed from {when(gone)}"))

    order = {"removed": 0, "added": 1, "moved": 2, "edited": 3}
    return sorted(changes, key=lambda c: (order.get(c.kind, 9), c.label))


def _compare(old: Row, new: Row) -> list[Change]:
    changes = []
    if (old.date, old.start_date, old.end_date) != \
            (new.date, new.start_date, new.end_date):
        changes.append(Change("moved", new.label,
                              f"moved from {when(old)} to {when(new)}"))
    if old.type != new.type:
        changes.append(Change("edited", new.label,
                              f"changed from {old.type} to {new.type}"))
    if old.notes != new.notes:
        changes.append(Change("edited", new.label, "note changed"))
    return changes


def describe(changes: list[Change]) -> str:
    """A one-line summary for a commit message.

    Names what happened when there is little enough of it to name. A commit
    reading "Allison: 1 change" is no more use than no message at all.
    """
    if not changes:
        return "no changes"
    if len(changes) <= 2:
        return "; ".join(str(c) for c in changes)
    kinds: dict[str, int] = {}
    for change in changes:
        kinds[change.kind] = kinds.get(change.kind, 0) + 1
    parts = [f"{n} {kind}" for kind, n in sorted(kinds.items())]
    return ", ".join(parts)
