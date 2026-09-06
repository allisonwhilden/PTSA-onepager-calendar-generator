"""The deploy workflow's shell, actually executed.

This step is the publishing path -- it decides what lands on gh-pages and
therefore what families see -- and nothing ran it until this file. It is also
shell inside YAML, which no linter in this repo reads.

The bug that prompted these: a variable was used six lines before it was
assigned. The step runs under `set -euo pipefail`, so `set -u` made that fatal,
and *every* push and every scheduled run would have died there -- after
building the PDF and before publishing it. `bash -n` does not catch it, because
it is a runtime error and the syntax is perfectly good. Only running it does.

Nothing is stubbed. The clone's origin is a throwaway bare repository in a
temp directory, so pushes are real and land somewhere harmless -- which is what
lets the second run see the gh-pages branch the first one made, and so lets
these check the "already published" path that stops the daily schedule
committing every day.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO = Path(__file__).resolve().parent.parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "build-and-deploy.yml"

#: What the clone sits on between deploys. The deploy step ends on gh-pages.
SOURCE_BRANCH = "under-test"


def deploy_script() -> str:
    steps = yaml.safe_load(WORKFLOW.read_text())["jobs"]["build"]["steps"]
    step = next(s for s in steps if s.get("name") == "Deploy to GitHub Pages")
    return step["run"]


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    """A clone whose origin is a throwaway bare repo, so pushes are real.

    Real rather than stubbed because gh-pages only exists on the *remote*
    between runs -- the script looks for origin/gh-pages and falls back to
    creating an orphan branch. With a stubbed push the second run never finds
    the first run's branch, and the "already published" path, which is the
    whole reason the daily schedule is safe, could not be tested at all.
    """
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(REPO), str(origin)],
                   check=True)
    clone = tmp_path / "repo"
    subprocess.run(["git", "clone", "-q", str(origin), str(clone)], check=True)
    for key, value in (("user.email", "t@e.st"), ("user.name", "Test")):
        subprocess.run(["git", "-C", str(clone), "config", key, value], check=True)
    subprocess.run(["git", "-C", str(clone), "checkout", "-q", "-B", SOURCE_BRANCH],
                   check=True)
    return clone


def run_deploy(sandbox: Path, tmp_path: Path, sha: str = "abc123def456"):
    """Build the PDF the way the workflow's earlier step does, then deploy.

    Puts the clone back on the source branch first. The deploy leaves it on
    gh-pages, which has no python/ in it; in CI every run starts from a fresh
    checkout, so a second run here has to start from one too.
    """
    subprocess.run(["git", "-C", str(sandbox), "checkout", "-q", SOURCE_BRANCH],
                   check=True)
    built = subprocess.run(
        ["python", "python/build.py", "--out-dir", "dist"],
        cwd=sandbox, capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    pdf = next((sandbox / "dist").glob("*.pdf"))

    summary = tmp_path / "summary.md"
    summary.write_text("")          # one run's summary, not the accumulation
    return subprocess.run(
        ["bash", "-c", deploy_script()],
        cwd=sandbox, capture_output=True, text=True,
        env={**os.environ,
             "PDF": str(pdf.relative_to(sandbox)),
             "GITHUB_SHA": sha,
             "GITHUB_STEP_SUMMARY": str(summary)},
    ), summary


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
def test_the_deploy_step_runs_to_completion(sandbox, tmp_path):
    """The one that would have caught the unbound variable."""
    result, _ = run_deploy(sandbox, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "unbound variable" not in result.stderr
    published = subprocess.run(
        ["git", "-C", str(sandbox), "ls-remote", "--heads", "origin", "gh-pages"],
        capture_output=True, text=True, check=True).stdout
    assert "gh-pages" in published, "it never got as far as publishing"


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
def test_it_publishes_the_stable_link_and_a_year_stamped_copy(sandbox, tmp_path):
    """calendar.pdf is what the school website links, permanently. The
    year-stamped copy is what somebody shares when they want a particular
    year."""
    run_deploy(sandbox, tmp_path)
    files = subprocess.run(
        ["git", "-C", str(sandbox), "show", "--name-only", "--format=",
         "origin/gh-pages"],
        capture_output=True, text=True, check=True).stdout.split()

    assert "calendar.pdf" in files
    assert any(f.startswith("calendar-2") and f.endswith(".pdf") for f in files), \
        f"no year-stamped copy in {files}"
    assert "index.html" in files


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
def test_a_second_run_on_unchanged_source_publishes_nothing(sandbox, tmp_path):
    """index.html carries today's date and so does the PDF footer, so the
    ordinary "no changes" guard can never fire. Without the stamp, the daily
    schedule would add a commit and a fresh PDF blob to gh-pages every day."""
    run_deploy(sandbox, tmp_path)
    first = subprocess.run(["git", "-C", str(sandbox), "rev-parse", "origin/gh-pages"],
                           capture_output=True, text=True, check=True).stdout

    result, summary = run_deploy(sandbox, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Already published" in summary.read_text()

    second = subprocess.run(["git", "-C", str(sandbox), "rev-parse", "origin/gh-pages"],
                            capture_output=True, text=True, check=True).stdout
    assert first == second, "it committed again with nothing changed"


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
def test_a_new_source_commit_publishes_again(sandbox, tmp_path):
    """The other half: the stamp must not wedge it shut."""
    run_deploy(sandbox, tmp_path)
    before = subprocess.run(["git", "-C", str(sandbox), "rev-parse", "origin/gh-pages"],
                            capture_output=True, text=True, check=True).stdout

    result, _ = run_deploy(sandbox, tmp_path, sha="0000feedbeef")
    assert result.returncode == 0, result.stdout + result.stderr

    after = subprocess.run(["git", "-C", str(sandbox), "rev-parse", "origin/gh-pages"],
                           capture_output=True, text=True, check=True).stdout
    assert before != after, "a changed source did not publish"


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
def test_a_half_staged_next_year_still_publishes_this_one(sandbox, tmp_path):
    """A config for next year normally appears before next year's dates. That
    is the ordinary middle of a year roll, and it must not take the current
    calendar off the website."""
    from calendar_gen import school_year

    nxt = school_year.current_start_year() + 1
    label = school_year.label_for(nxt)
    (sandbox / "data" / "years" / f"{label}.toml").write_text(
        f'[calendar]\norganization = "Horace Mann PTSA"\n\n[dates]\n'
        f'early_release_start = {nxt}-09-09\nlast_day = {nxt + 1}-06-16\n'
        f'boxed_days = [{nxt}-08-31, {nxt + 1}-06-16]\n')
    subprocess.run(["git", "-C", str(sandbox), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(sandbox), "commit", "-qm", "stage next year"],
                   check=True)

    result, summary = run_deploy(sandbox, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"{label} is not ready to preview" in summary.read_text()

    files = subprocess.run(
        ["git", "-C", str(sandbox), "show", "--name-only", "--format=",
         "origin/gh-pages"],
        capture_output=True, text=True, check=True).stdout
    assert "calendar.pdf" in files, "this year stopped publishing"
    assert f"calendar-{label}.pdf" not in files
