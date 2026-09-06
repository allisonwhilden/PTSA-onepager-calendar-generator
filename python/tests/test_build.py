"""The build.py command-line contract.

`.github/workflows/build-and-deploy.yml` branches on these exit codes, and it
branches on them *by number*:

    exit 0  -- built
    exit 3  -- "the year has ended", a routine skip that publishes nothing and
               still reports success
    anything else -- a real failure that must fail the job

The workflow's own comment says why that distinction matters ("that is how a
broken build gets a green check"), and until this file nothing checked it. If
exit 3 ever started meaning something else, the deploy would quietly swallow a
real error; if a real error started returning 3, a broken calendar would be
skipped instead of shouted about, and either way the job would be green.

These run build.py as a subprocess rather than importing main(), because the
exit code is the contract -- an exception that argparse or Python turns into a
different status is exactly the sort of thing an in-process call would hide.
"""

from __future__ import annotations

import datetime as dt
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
BUILD = REPO / "python" / "build.py"

YEAR_TOML = """\
[calendar]
organization = "Test PTSA"

[dates]
early_release_start = {start}-09-09
last_day = {end}-06-16
boxed_days = [{start}-08-31, {end}-06-16]
"""

EVENTS_CSV = """\
date,start_date,end_date,type,label,notes
{start}-08-31,,,first_day,First Day,
{start}-09-07,,,no_school,Labor Day,
{start}-10-15,,,ptsa_event,Curriculum Night,
{end}-06-16,,,last_day,Last Day of School,
"""


@pytest.fixture
def workspace(tmp_path: Path):
    """A throwaway data directory, so these never depend on the shipped year.

    Returns a callable: give it the school year's starting year and it lays out
    data/years/<label>.toml and data/all_events.csv for that year.
    """

    def _make(start: int, csv_body: str | None = None, toml_body: str | None = None):
        years = tmp_path / "years"
        years.mkdir(exist_ok=True)
        label = f"{start}-{str(start + 1)[-2:]}"
        (years / f"{label}.toml").write_text(
            toml_body if toml_body is not None
            else YEAR_TOML.format(start=start, end=start + 1),
            encoding="utf-8",
        )
        csv_path = tmp_path / "all_events.csv"
        csv_path.write_text(
            textwrap.dedent(csv_body) if csv_body is not None
            else EVENTS_CSV.format(start=start, end=start + 1),
            encoding="utf-8",
        )
        return csv_path, years

    return _make


def run(*args, cwd: Path | None = None):
    """build.py with the given arguments, from an unrelated directory.

    cwd defaults to somewhere that is not the repo: build.py promises to run
    from anywhere, and defaulting to the repo root would let a path bug pass.
    """
    return subprocess.run(
        [sys.executable, str(BUILD), *map(str, args)],
        cwd=str(cwd or Path(__file__).parent),
        capture_output=True,
        text=True,
    )


# --- the codes the deploy workflow reads ------------------------------------

def test_a_year_that_has_not_started_yet_exits_3(workspace):
    """The routine skip. 2400-01 is not the current school year by any clock.

    The workflow treats 3 as "nothing to publish, this is fine" and exits 0.
    """
    csv_path, years = workspace(2400)
    result = run("--data", csv_path, "--years-dir", years,
                 "--require-current-year", "--print-label")
    assert result.returncode == 3, result.stderr
    assert "current school year" in result.stderr


def test_a_missing_config_does_not_exit_3(workspace, tmp_path):
    """A real failure must not borrow the routine-skip code.

    This is the dangerous direction: 3 here would publish nothing and report
    success, so a repo with no configs at all would look like a normal skip.
    """
    csv_path, _ = workspace(2400)
    empty = tmp_path / "no-years"
    empty.mkdir()
    result = run("--data", csv_path, "--years-dir", empty, "--require-current-year")
    assert result.returncode not in (0, 3), result.stderr
    assert "No school-year configs" in result.stderr


def test_a_broken_config_does_not_exit_3(workspace):
    """Same again for a config that exists but is wrong."""
    csv_path, years = workspace(2400, toml_body=YEAR_TOML.format(
        start=2400, end=2401).replace("last_day = 2401-06-16",
                                      'last_day = "2401-06-16"'))
    result = run("--data", csv_path, "--years-dir", years, "--require-current-year")
    assert result.returncode not in (0, 3), result.stderr


def test_print_label_prints_only_the_label(workspace):
    """The workflow captures this into a shell variable."""
    csv_path, years = workspace(2400)
    result = run("--data", csv_path, "--years-dir", years,
                 "--year", 2400, "--print-label")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "2400-01"


def test_print_organization_prints_only_the_name(workspace):
    """Interpolated into the published index page, so stray output would show."""
    csv_path, years = workspace(2400)
    result = run("--data", csv_path, "--years-dir", years,
                 "--year", 2400, "--print-organization")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "Test PTSA"


# --- validation ------------------------------------------------------------

def test_check_passes_on_a_good_year(workspace):
    csv_path, years = workspace(2400)
    result = run("--data", csv_path, "--years-dir", years, "--year", 2400, "--check")
    assert result.returncode == 0, result.stderr + result.stdout
    assert "OK:" in result.stdout


def test_an_unknown_event_type_fails_the_build(workspace):
    """The original bug in this repo: an unknown type silently became no_school
    and printed five ordinary school days as "No School"."""
    csv_path, years = workspace(2400, csv_body="""\
        date,start_date,end_date,type,label,notes
        2400-08-31,,,first_day,First Day,
        2400-10-15,,,invented_type,Something,
        2401-06-16,,,last_day,Last Day of School,
        """)
    result = run("--data", csv_path, "--years-dir", years, "--year", 2400, "--check")
    assert result.returncode == 1, result.stdout
    assert "invented_type" in result.stderr


def test_a_calendar_with_no_dates_in_range_fails(workspace):
    """The half-finished year roll: new config, last year's CSV. Without this
    the build goes green on a page with nothing on it."""
    csv_path, years = workspace(2400, csv_body="""\
        date,start_date,end_date,type,label,notes
        2001-10-15,,,ptsa_event,An event from long ago,
        """)
    result = run("--data", csv_path, "--years-dir", years, "--year", 2400, "--check")
    assert result.returncode == 1, result.stdout
    assert "blank" in result.stderr


def test_rows_for_another_year_are_a_notice_not_a_warning(workspace):
    """Staging next year's dates early must not fail --strict. This is what
    lets both years sit in the CSV at once during a roll."""
    csv_path, years = workspace(2400, csv_body="""\
        date,start_date,end_date,type,label,notes
        2400-08-31,,,first_day,First Day,
        2400-10-15,,,ptsa_event,Curriculum Night,
        2401-06-16,,,last_day,Last Day of School,
        2402-10-15,,,ptsa_event,Next year's event,
        """)
    result = run("--data", csv_path, "--years-dir", years,
                 "--year", 2400, "--check", "--strict")
    assert result.returncode == 0, result.stderr + result.stdout
    assert "not on this calendar" in result.stdout


def test_an_unreadable_csv_reports_a_path_not_a_traceback(workspace, tmp_path):
    csv_path, years = workspace(2400)
    result = run("--data", tmp_path / "nope.csv", "--years-dir", years,
                 "--year", 2400, "--check")
    assert result.returncode == 2, result.stdout
    assert "Traceback" not in result.stderr


# --- output ----------------------------------------------------------------

def test_it_writes_a_pdf_named_after_the_year(workspace, tmp_path):
    csv_path, years = workspace(2400)
    out = tmp_path / "out"
    result = run("--data", csv_path, "--years-dir", years,
                 "--year", 2400, "--out-dir", out)
    assert result.returncode == 0, result.stderr
    written = list(out.glob("*.pdf"))
    assert [p.name for p in written] == ["TestPTSA-2400-01-Calendar.pdf"]
    assert written[0].stat().st_size > 1000


def test_it_runs_from_any_directory(workspace, tmp_path):
    """CLAUDE.md: "build.py runs from any directory; if it ever needs a cd
    first, that's a bug"."""
    csv_path, years = workspace(2400)
    result = run("--data", csv_path, "--years-dir", years,
                 "--year", 2400, "--check", cwd=tmp_path)
    assert result.returncode == 0, result.stderr


def test_a_two_page_calendar_is_refused_even_without_check(workspace, tmp_path):
    """Writing a two-page PDF is never the right answer.

    The one-page fit used to be checked only under --check, so a plain build
    would write a two-page calendar and say "Wrote ..." -- and the deploy
    workflow's build step is a plain build. It was covered in practice because
    the validate step runs --check --strict first, which is a guarantee about
    the order of two steps in a YAML file rather than about the program.
    """
    # Comfortably past the ~52 listed rows the page holds. Labels are unique so
    # that nothing folds together in the dates list.
    days = [dt.date(2400, 9, 1) + dt.timedelta(days=3 * i) for i in range(70)]
    rows = "\n".join(
        f"{d.isoformat()},,,ptsa_event,Fundraiser planning meeting number {i},"
        for i, d in enumerate(days)
    )
    csv_path, years = workspace(2400, csv_body=f"""\
        date,start_date,end_date,type,label,notes
        2400-08-31,,,first_day,First Day,
        {rows}
        2401-06-16,,,last_day,Last Day of School,
        """)
    out = tmp_path / "out"
    result = run("--data", csv_path, "--years-dir", years, "--year", 2400,
                 "--out-dir", out)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "fit on one" in result.stderr
    assert not list(out.glob("*.pdf")), "a two-page PDF was written anyway"
