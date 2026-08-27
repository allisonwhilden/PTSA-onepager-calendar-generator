"""The registry is the guard against the bug that started all this.

A type nobody declared must stop the build. It must never quietly become a
different type -- least of all no_school, which turns a school day black.
"""

import pytest

from calendar_gen import event_types as et


def test_unknown_type_raises_rather_than_guessing():
    with pytest.raises(et.UnknownEventType):
        et.resolve("pizza_party")


def test_grades_due_is_listed_but_leaves_the_school_day_alone():
    # The original bug: grades_due resolved to no_school, so five ordinary
    # school days printed as black "No School" cells.
    resolved = et.resolve("grades_due")
    assert resolved.name == "informational"
    assert resolved.fill is None
    assert not resolved.circle
    assert resolved.is_invisible


def test_no_alias_resolves_to_no_school_except_holiday():
    """Only an actual day off may produce a no-school cell."""
    offenders = [
        raw for raw in et.ALIASES
        if et.resolve(raw).fill == "no_school" and raw != "holiday"
    ]
    assert offenders == []


def test_invisible_types_are_exactly_the_ones_with_no_drawing():
    """The box is not in this test on purpose: it comes from the year config,
    not from an event type. See DECISIONS.md."""
    for name, kind in et.REGISTRY.items():
        drawn = bool(kind.fill) or kind.circle
        assert kind.is_invisible is not drawn, name


def test_ptsa_events_are_circled_and_prefixed():
    ptsa = et.resolve("ptsa_event")
    assert ptsa.circle
    assert ptsa.label_prefix == "PTSA: "


@pytest.mark.parametrize("raw,expected", [
    ("no_school", "no_school"),
    ("holiday", "no_school"),
    ("first_day_k", "first_day"),
    ("first_day_1_12", "first_day"),
    ("closure_day", "closure_possible"),
    ("potential_school_day", "closure_possible"),
    ("kinder_family_conn", "informational"),
    ("  PTSA_Event  ", "ptsa_event"),
])
def test_aliases_and_whitespace(raw, expected):
    assert et.resolve(raw).name == expected


def test_every_alias_points_at_a_declared_type():
    for alias, target in et.ALIASES.items():
        assert target in et.REGISTRY, f"{alias} -> {target}"
