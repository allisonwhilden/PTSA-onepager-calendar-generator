"""Starting a new school year.

The one place in this project that proposes a date rather than being told one,
so the tests are mostly about the boundary: a suggestion has to stay a
suggestion until a person accepts it.
"""

from __future__ import annotations

import datetime as dt

import pytest

from web import newyear
from web.csvio import Row


def test_a_suggestion_keeps_the_weekday():
    """364 days, not a year. Recurring school events are pinned to "the second
    Thursday", not to a date, so a 365-day shift moves every one of them."""
    rows = [Row(date="2026-09-17", type="ptsa_event", label="Bike Derby")]
    [proposal] = newyear.propose(rows, 2026)

    was = dt.date.fromisoformat("2026-09-17")
    now = dt.date.fromisoformat(proposal.suggested.date)
    assert was.weekday() == now.weekday() == 3        # Thursday, both
    assert now.year == 2027
    assert proposal.moved_weekday is False


def test_a_date_range_is_shifted_at_both_ends():
    rows = [Row(start_date="2026-11-26", end_date="2026-11-27",
                type="no_school", label="Thanksgiving Break")]
    [proposal] = newyear.propose(rows, 2026)
    assert proposal.suggested.start_date == "2027-11-25"
    assert proposal.suggested.end_date == "2027-11-26"


def test_only_last_year_is_offered():
    """The CSV holds every year at once. Without this the carry-forward list
    would include dates from years ago that nobody meant to bring back."""
    rows = [
        Row(date="2024-10-15", type="ptsa_event", label="Ancient history"),
        Row(date="2026-10-15", type="ptsa_event", label="Curriculum Night"),
        Row(date="2028-10-15", type="ptsa_event", label="Staged even earlier"),
    ]
    assert [p.label for p in newyear.propose(rows, 2026)] == ["Curriculum Night"]


def test_provenance_notes_are_not_carried_forward():
    """A note saying where a date was verified is a claim about *that* date.
    Copied onto a shifted guess it would vouch for something nobody checked."""
    rows = [Row(date="2026-10-15", type="ptsa_event", label="Curriculum Night",
                notes="Verified against the district PDF, revision 8/2026.")]
    [proposal] = newyear.propose(rows, 2026)
    assert proposal.suggested.notes == ""
    assert proposal.previous.notes.startswith("Verified")


def test_an_unparseable_date_is_left_out_rather_than_guessed_at():
    rows = [Row(date="sometime in October", type="ptsa_event", label="Vague")]
    assert newyear.propose(rows, 2026) == []


def test_the_config_says_the_dates_are_unverified():
    """Nobody has checked them against the district at the moment it is
    written, and the file should not imply otherwise -- the shipped configs
    carry a verified-against line, and a copy that kept it would be lying."""
    toml = newyear.config_toml(
        organization="Horace Mann PTSA", label="2027-28",
        early_release_start="2027-09-08", last_day="2028-06-15",
        boxed_days=["2027-08-30", "2028-06-15"], source_label="2026-27")
    assert "VERIFY THESE AGAINST THE DISTRICT" in toml
    assert "lwsd.org" in toml
    assert 'organization = "Horace Mann PTSA"' in toml


def test_the_config_parses_and_loads(tmp_path):
    """It is written by hand as text to keep its comments, which means nothing
    checks the syntax unless this does."""
    from calendar_gen import school_year

    toml = newyear.config_toml(
        organization="Test PTSA", label="2027-28",
        early_release_start="2027-09-08", last_day="2028-06-15",
        boxed_days=["2028-06-15", "2027-08-30", "2027-09-02"])
    (tmp_path / "2027-28.toml").write_text(toml)

    year = school_year.load(tmp_path, 2027)
    assert year.organization == "Test PTSA"
    assert year.last_day == dt.date(2028, 6, 15)
    assert year.early_release_start == dt.date(2027, 9, 8)
    assert len(year.boxed_days) == 3


def test_boxed_days_are_written_in_order(tmp_path):
    toml = newyear.config_toml(
        organization="T", label="2027-28", early_release_start="2027-09-08",
        last_day="2028-06-15", boxed_days=["2028-06-15", "2027-08-30"])
    assert "boxed_days = [2027-08-30, 2028-06-15]" in toml


@pytest.mark.parametrize("labels,expected", [
    (["2025-26", "2026-27"], 2027),
    (["2026-27"], 2027),
    ([], dt.date.today().year),
])
def test_it_offers_the_year_after_the_newest_one(tmp_path, labels, expected):
    for label in labels:
        (tmp_path / f"{label}.toml").write_text("")
    assert newyear.next_year_after(tmp_path) == expected


def test_suggested_dates_land_on_the_right_weekdays():
    """Only to save typing -- but a Wednesday box prefilled with a Saturday
    would cost more attention than it saves."""
    dates = newyear.suggest_dates(2027)
    assert dt.date.fromisoformat(dates["first_day"]).weekday() == 0      # Mon
    assert dt.date.fromisoformat(dates["early_release_start"]).weekday() == 2
    assert dt.date.fromisoformat(dates["last_day"]).weekday() == 2
