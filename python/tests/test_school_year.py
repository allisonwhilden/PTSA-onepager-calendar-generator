"""Year selection and config loading -- the part that makes rolling years cheap."""

import datetime as dt

import pytest

from calendar_gen import school_year as sy


@pytest.mark.parametrize("start,expected", [(2025, "2025-26"), (2026, "2026-27"),
                                            (2099, "2099-00")])
def test_label(start, expected):
    assert sy.label_for(start) == expected


@pytest.mark.parametrize("today,expected", [
    (dt.date(2025, 8, 1), 2025),    # August starts the new year
    (dt.date(2025, 12, 31), 2025),
    (dt.date(2026, 1, 1), 2025),    # January still belongs to it
    (dt.date(2026, 7, 31), 2025),
    (dt.date(2026, 8, 1), 2026),
])
def test_current_start_year(today, expected):
    assert sy.current_start_year(today) == expected


def test_explicit_year_wins(years_dir):
    year, why = sy.resolve_start_year(years_dir, requested=2025)
    assert year == 2025
    assert "--year" in why


def test_falls_back_to_newest_config_when_the_current_year_has_none(years_dir):
    """Today is in 2026-27, which has no config yet -- build 2025-26 and say why."""
    year, why = sy.resolve_start_year(
        years_dir, requested=None, today=dt.date(2026, 9, 1))
    assert year == 2025
    assert "2026-27" in why


def test_prefers_the_current_year_when_a_config_exists(years_dir):
    year, why = sy.resolve_start_year(
        years_dir, requested=None, today=dt.date(2025, 10, 1))
    assert year == 2025
    assert why == "current school year"


def test_asking_for_a_year_with_no_config_is_an_error(years_dir):
    with pytest.raises(FileNotFoundError) as caught:
        sy.resolve_start_year(years_dir, requested=2030)
    assert "2030-31" in str(caught.value)


def test_shipped_config_loads(years_dir):
    year = sy.load(years_dir, 2025)
    assert year.label == "2025-26"
    assert year.organization == "Horace Mann PTSA"
    assert year.early_release_start == dt.date(2025, 9, 10)


def test_printed_span_is_a_full_twelve_months(year):
    assert year.first_printed_day == dt.date(2025, 8, 1)
    assert year.last_printed_day == dt.date(2026, 7, 31)
    assert len(year.months()) == 12


def test_early_release_wednesdays_are_all_wednesdays_in_range(year):
    days = year.early_release_wednesdays()
    assert all(d.weekday() == sy.WEDNESDAY for d in days)
    assert days[0] == dt.date(2025, 9, 10)
    assert days[-1] <= year.last_day


def test_early_release_start_that_is_not_a_wednesday_moves_forward():
    monday = dt.date(2025, 9, 8)
    year = sy.SchoolYear(
        start_year=2025, organization="T",
        early_release_start=monday, last_day=dt.date(2025, 10, 1))
    assert year.early_release_wednesdays()[0] == dt.date(2025, 9, 10)


def test_missing_required_dates_is_a_clear_error(tmp_path):
    (tmp_path / "2027-28.toml").write_text(
        '[calendar]\norganization = "X"\n\n[dates]\nlast_day = 2028-06-01\n')
    with pytest.raises(ValueError) as caught:
        sy.load(tmp_path, 2027)
    assert "early_release_start" in str(caught.value)


def test_no_configs_at_all_is_a_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        sy.resolve_start_year(tmp_path)
