"""Reading and validating the CSV."""

import datetime as dt

import pytest

from calendar_gen import events as ev

HEADER = "date,start_date,end_date,type,label,notes\n"


def test_single_day_event(write_csv):
    events, warnings = ev.load_events(write_csv(
        HEADER + "2025-09-02,,,first_day,First Day,\n"))
    assert len(events) == 1
    assert events[0].start == events[0].end == dt.date(2025, 9, 2)
    assert not events[0].is_range
    assert warnings == []


def test_range_expands_inclusively(write_csv):
    events, _ = ev.load_events(write_csv(
        HEADER + ",2025-12-22,2025-12-26,no_school,Winter Break,\n"))
    assert [d.day for d in events[0].dates()] == [22, 23, 24, 25, 26]


def test_every_problem_is_reported_together_with_its_row(write_csv):
    path = write_csv(
        HEADER
        + "2025-09-02,,,first_day,Fine,\n"          # line 2
        + "2025-10-01,,,pizza_party,Unknown,\n"     # line 3
        + "2025-11-03,,,no_school,,\n"              # line 4
        + ",2026-02-10,2026-02-03,no_school,Back,\n"  # line 5
        + ",,,ptsa_event,No date,\n"                # line 6
    )
    with pytest.raises(ev.ValidationError) as caught:
        ev.load_events(path)

    assert {p.row for p in caught.value.problems} == {3, 4, 5, 6}


def test_row_numbers_are_file_lines_not_record_counts(write_csv):
    """A blank line must not shift every later number.

    csv skips blank rows without consuming a record, so counting records drifts
    and points the reader at the wrong line -- exactly when the file has been
    hand-edited or round-tripped through a spreadsheet.
    """
    path = write_csv(
        HEADER
        + "2025-09-02,,,first_day,Fine,\n"      # line 2
        + "\n"                                   # line 3, blank
        + "2025-10-01,,,pizza_party,Bad,\n"     # line 4
    )
    with pytest.raises(ev.ValidationError) as caught:
        ev.load_events(path)

    assert [p.row for p in caught.value.problems] == [4]


def test_unknown_type_message_names_the_type_and_the_alternatives(write_csv):
    with pytest.raises(ev.ValidationError) as caught:
        ev.load_events(write_csv(HEADER + "2025-10-01,,,pizza_party,Party,\n"))
    text = str(caught.value)
    assert "pizza_party" in text
    assert "no_school" in text  # the hint lists what is declared


def test_backwards_range_is_an_error_not_a_silent_empty_event(write_csv):
    with pytest.raises(ev.ValidationError):
        ev.load_events(write_csv(
            HEADER + ",2026-02-10,2026-02-03,no_school,Backwards,\n"))


def test_half_a_range_is_an_error(write_csv):
    with pytest.raises(ev.ValidationError):
        ev.load_events(write_csv(HEADER + ",2026-02-10,,no_school,Half,\n"))


def test_one_day_range_warns_but_still_builds(write_csv):
    events, warnings = ev.load_events(write_csv(
        HEADER + ",2026-05-08,2026-05-08,ptsa_event,Staff Appreciation Week,\n"))
    assert len(events) == 1
    assert len(warnings) == 1
    assert "one-day range" in warnings[0].message


def test_missing_required_column_is_an_error(write_csv):
    with pytest.raises(ev.ValidationError) as caught:
        ev.load_events(write_csv("date,type,notes\n2025-09-02,no_school,\n"))
    assert "label" in str(caught.value)


def test_missing_file_says_so(tmp_path):
    with pytest.raises(FileNotFoundError):
        ev.load_events(tmp_path / "nope.csv")


def test_events_outside_the_printed_span_are_reported(write_csv, year):
    events, _ = ev.load_events(write_csv(
        HEADER + "2019-01-01,,,ptsa_event,Ancient History,\n"))
    problems = ev.outside_year(
        events, year.first_printed_day, year.last_printed_day)
    assert len(problems) == 1
    assert "Ancient History" in problems[0].message


def test_shipped_csv_is_valid(real_csv):
    """The data we actually publish must always pass validation."""
    events, _ = ev.load_events(real_csv)
    assert len(events) > 0


def test_both_a_date_and_a_range_is_an_error(write_csv):
    """Silently preferring one collapses a week to a day -- the Staff
    Appreciation Week bug, but passing --strict clean."""
    with pytest.raises(ev.ValidationError) as caught:
        ev.load_events(write_csv(
            HEADER + "2026-05-04,2026-05-04,2026-05-08,ptsa_event,Staff Week,\n"))
    assert "both" in str(caught.value)


def test_problem_formatting_is_shared(write_csv):
    """build.py prints warnings and events.py prints errors; one formatter."""
    problems = [ev.Problem(7, "something", "a hint")]
    rendered = ev.format_problems(problems)
    assert "row 7: something" in rendered
    assert "a hint" in rendered
    try:
        ev.load_events(write_csv(HEADER + "2025-10-01,,,nope,X,\n"))
    except ev.ValidationError as exc:
        assert ev.format_problems(exc.problems) in str(exc)
