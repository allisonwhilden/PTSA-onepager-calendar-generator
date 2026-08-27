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


@pytest.fixture
def fake_years(tmp_path):
    """Build a years directory on demand.

    Year-selection tests must not read data/years -- adding next year's config
    is the documented, code-free year roll, and it must never turn CI red.
    """

    def _make(*start_years: int):
        for start in start_years:
            (tmp_path / f"{sy.label_for(start)}.toml").write_text(
                '[calendar]\norganization = "Test PTSA"\n\n'
                "[dates]\n"
                f"early_release_start = {start}-09-10\n"
                f"last_day = {start + 1}-06-17\n"
            )
        return tmp_path

    return _make


def test_explicit_year_wins(fake_years):
    year, why = sy.resolve_start_year(fake_years(2025, 2026), requested=2025)
    assert year == 2025
    assert "--year" in why


def test_falls_back_to_newest_config_when_the_current_year_has_none(fake_years):
    """No config for the year we are in -- build the newest there is, and say why."""
    year, why = sy.resolve_start_year(
        fake_years(2024, 2025), requested=None, today=dt.date(2026, 9, 1))
    assert year == 2025
    assert "2026-27" in why


def test_prefers_the_current_year_when_a_config_exists(fake_years):
    year, why = sy.resolve_start_year(
        fake_years(2025, 2026), requested=None, today=dt.date(2026, 10, 1))
    assert year == 2026
    assert why == "current school year"


def test_adding_next_years_config_is_all_it_takes(fake_years):
    """The year roll: drop in a config and the build follows today's date."""
    today = dt.date(2026, 9, 1)
    assert sy.resolve_start_year(fake_years(2025), today=today)[0] == 2025
    assert sy.resolve_start_year(fake_years(2025, 2026), today=today)[0] == 2026


def test_asking_for_a_year_with_no_config_is_an_error(fake_years):
    with pytest.raises(FileNotFoundError) as caught:
        sy.resolve_start_year(fake_years(2025), requested=2030)
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


# --- config validation -----------------------------------------------------
# A wrong value here draws nothing at all rather than drawing something wrong,
# which is the hardest kind of bug to notice on a printed page.

def write_year(tmp_path, body: str, label: str = "2026-27"):
    (tmp_path / f"{label}.toml").write_text(
        '[calendar]\norganization = "T"\n\n[dates]\n' + body)
    return tmp_path


def test_quoted_date_is_rejected_with_a_clear_message(tmp_path):
    d = write_year(tmp_path, 'early_release_start = 2026-09-09\nlast_day = "2027-06-16"\n')
    with pytest.raises(ValueError) as caught:
        sy.load(d, 2026)
    assert "last_day" in str(caught.value) and "quot" in str(caught.value)


def test_quoted_boxed_day_is_rejected(tmp_path):
    d = write_year(tmp_path, 'early_release_start = 2026-09-09\nlast_day = 2027-06-16\n'
                             'boxed_days = ["2026-09-01"]\n')
    with pytest.raises(ValueError) as caught:
        sy.load(d, 2026)
    assert "boxed_days" in str(caught.value)


def test_boxed_days_left_over_from_last_year_are_rejected(tmp_path):
    """Copying the config forward without editing boxed_days would draw no box
    at all, while the legend still advertises one."""
    d = write_year(tmp_path, 'early_release_start = 2026-09-09\nlast_day = 2027-06-16\n'
                             'boxed_days = [2025-09-02]\n')
    with pytest.raises(ValueError) as caught:
        sy.load(d, 2026)
    assert "outside" in str(caught.value)


def test_early_release_after_last_day_is_rejected(tmp_path):
    d = write_year(tmp_path, 'early_release_start = 2027-06-16\nlast_day = 2026-09-09\n')
    with pytest.raises(ValueError) as caught:
        sy.load(d, 2026)
    assert "no Wednesday" in str(caught.value)


def test_dates_outside_the_printed_year_are_rejected(tmp_path):
    d = write_year(tmp_path, 'early_release_start = 2026-09-09\nlast_day = 2030-06-16\n')
    with pytest.raises(ValueError) as caught:
        sy.load(d, 2026)
    assert "outside" in str(caught.value)


# --- the accented header ---------------------------------------------------

@pytest.mark.parametrize("org,expected", [
    ("Horace Mann PTSA", ("Horace Mann", "PTSA")),
    ("Horace Mann PTA", ("Horace Mann PTA", "")),   # no accent rather than mangled
    ("Lakeside Parents", ("Lakeside Parents", "")),
])
def test_header_splits_without_mangling_the_name(org, expected):
    year = sy.SchoolYear(2025, org, dt.date(2025, 9, 10), dt.date(2026, 6, 17))
    assert year.header_parts == expected


def test_shipped_config_still_accents_ptsa(years_dir):
    assert sy.load(years_dir, 2025).header_parts == ("Horace Mann", "PTSA")


def test_a_date_time_is_rejected_rather_than_crashing_later(tmp_path):
    """datetime subclasses date, so a bare isinstance check lets it through and
    it explodes on the first comparison instead of giving a clear message."""
    d = write_year(tmp_path,
                   'early_release_start = 2026-09-09T00:00:00\nlast_day = 2027-06-16\n')
    with pytest.raises(ValueError) as caught:
        sy.load(d, 2026)
    assert "early_release_start" in str(caught.value)


def test_a_misspelled_dates_key_is_rejected(tmp_path):
    """`boxed_day` would otherwise load as an empty set: no box drawn, while the
    legend still advertises one."""
    d = write_year(tmp_path, 'early_release_start = 2026-09-09\nlast_day = 2027-06-16\n'
                             'boxed_day = [2026-09-01]\n')
    with pytest.raises(ValueError) as caught:
        sy.load(d, 2026)
    assert "boxed_day" in str(caught.value)


def test_a_missing_organization_is_rejected(tmp_path):
    (tmp_path / "2026-27.toml").write_text(
        "[dates]\nearly_release_start = 2026-09-09\nlast_day = 2027-06-16\n")
    with pytest.raises(ValueError) as caught:
        sy.load(tmp_path, 2026)
    assert "organization" in str(caught.value)


def test_a_non_canonical_filename_is_ignored(tmp_path):
    """2026-2027.toml would resolve to year 2026 and then fail opening
    2026-27.toml -- an error naming a file the user never created."""
    (tmp_path / "2026-2027.toml").write_text("[calendar]\norganization = 'T'\n")
    (tmp_path / "2025-26.toml").write_text(
        "[calendar]\norganization = 'T'\n\n[dates]\n"
        "early_release_start = 2025-09-10\nlast_day = 2026-06-17\n")
    assert sy.available_years(tmp_path) == [2025]
