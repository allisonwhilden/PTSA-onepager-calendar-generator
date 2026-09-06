"""Reading and writing the event CSV.

The editor rewrites this file on every save. If the writer disturbs anything it
was not asked to change, every commit buries one edited date under sixty lines
of noise -- and the history is the whole reason for the design.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from web import csvio

REPO = Path(__file__).resolve().parent.parent.parent
SHIPPED = REPO / "data" / "all_events.csv"


def test_round_trip_of_the_shipped_csv_is_byte_identical():
    """Held against the real file, not a fixture.

    A fixture would only contain the cases someone thought of. The shipped CSV
    has the quoted multi-sentence notes, the date ranges and the same-day
    clusters that actually break writers.
    """
    original = SHIPPED.read_text(encoding="utf-8")
    assert csvio.dump(csvio.parse(original)) == original


def test_same_day_rows_keep_the_order_they_had():
    """Two rows on 2027-06-16 carry notes reading "the row above" and "the row
    below". Any tiebreak in the sort is free to swap them, which turns both
    notes into lies -- silently, in a column the printed page never shows.
    """
    rows = csvio.parse(SHIPPED.read_text(encoding="utf-8"))
    same_day = [r for r in rows if r.first_day == "2027-06-16"]
    assert len(same_day) > 1, "expected the shipped CSV to still cluster on 6/16"

    written = csvio.parse(csvio.dump(rows))
    assert [r.label for r in written if r.first_day == "2027-06-16"] == \
           [r.label for r in same_day]


def test_a_new_row_lands_in_date_order():
    rows = csvio.parse(SHIPPED.read_text(encoding="utf-8"))
    rows.append(csvio.Row(date="2026-12-05", type="ptsa_event", label="Winter Social"))

    lines = csvio.dump(rows).splitlines()
    i = next(n for n, line in enumerate(lines) if "Winter Social" in line)
    assert lines[i - 1].startswith("2026-12-03")
    assert lines[i + 1].startswith("2026-12-10")


def test_a_new_row_on_an_existing_date_goes_after_the_ones_there():
    rows = csvio.parse(SHIPPED.read_text(encoding="utf-8"))
    existing = [r.label for r in rows if r.first_day == "2027-06-16"]
    rows.append(csvio.Row(date="2027-06-16", type="ptsa_event", label="Brand New"))

    written = [r.label for r in csvio.parse(csvio.dump(rows))
               if r.first_day == "2027-06-16"]
    assert written == existing + ["Brand New"]


def test_notes_survive_a_round_trip_including_the_commas_and_quotes():
    """The notes column holds provenance nobody wants to lose -- and it is the
    only field with embedded punctuation, so it is the one that breaks."""
    rows = csvio.parse(SHIPPED.read_text(encoding="utf-8"))
    noted = [r for r in rows if r.notes]
    assert noted, "expected the shipped CSV to still carry provenance notes"

    back = {r.label: r.notes for r in csvio.parse(csvio.dump(rows))}
    for row in noted:
        assert back[row.label] == row.notes


def test_date_ranges_survive():
    rows = csvio.parse(SHIPPED.read_text(encoding="utf-8"))
    ranges = [r for r in rows if r.is_range]
    assert ranges

    back = csvio.parse(csvio.dump(rows))
    assert [(r.start_date, r.end_date) for r in back if r.is_range] == \
           [(r.start_date, r.end_date) for r in ranges]


def test_it_writes_lf_endings():
    """csv.writer defaults to CRLF. The file on disk is LF, and letting it flip
    would rewrite all 61 lines on the first save."""
    text = csvio.dump([csvio.Row(date="2026-12-05", type="ptsa_event", label="A")])
    assert "\r" not in text
    assert text.endswith("\n")


def test_a_row_being_typed_survives_being_saved():
    """Someone half way through adding an event must not lose it to a save.

    Nothing here parses dates or checks types: calendar_gen decides what is
    valid, and a second opinion in this module is a second thing to keep in
    step with the first.
    """
    rows = [csvio.Row(date="not-a-date", type="", label="Half typed")]
    back = csvio.parse(csvio.dump(rows))
    assert back[0].date == "not-a-date"
    assert back[0].label == "Half typed"
    assert back[0].parsed_date() is None


def test_unknown_columns_are_dropped_and_missing_ones_are_blank():
    rows = csvio.parse("date,type,label,colour\n2026-12-05,ptsa_event,A,red\n")
    assert rows == [csvio.Row(date="2026-12-05", type="ptsa_event", label="A")]
    assert csvio.dump(rows).splitlines()[0] == ",".join(csvio.COLUMNS)


def test_whitespace_around_values_is_trimmed():
    rows = csvio.parse("date,type,label,notes\n 2026-12-05 , ptsa_event ,  A  ,\n")
    assert rows[0].date == "2026-12-05"
    assert rows[0].label == "A"


@pytest.mark.parametrize("row,expected", [
    (csvio.Row(date="2026-12-05"), "2026-12-05"),
    (csvio.Row(start_date="2026-12-05", end_date="2026-12-07"), "2026-12-05"),
    (csvio.Row(), ""),
])
def test_first_day_prefers_the_single_date_then_the_range_start(row, expected):
    assert row.first_day == expected
