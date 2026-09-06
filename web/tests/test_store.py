"""The git-backed store.

These run against a real bare repository on disk rather than a mocked git.
Every interesting thing the store does -- a push being rejected, a draft
descending from main, a restore leaving history intact -- is a property of git
itself, and a fake would only ever confirm what the fake was written to
believe.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from web import csvio
from web.store import Conflict, Store, StoreError, _redact

CSV = """\
date,start_date,end_date,type,label,notes
2400-08-31,,,first_day,First Day,
2400-10-15,,,ptsa_event,Curriculum Night,
2401-06-16,,,last_day,Last Day of School,
"""

TOML = """\
[calendar]
organization = "Test PTSA"

[dates]
early_release_start = 2400-09-09
last_day = 2401-06-16
boxed_days = [2400-08-31, 2401-06-16]
"""


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def remote(tmp_path: Path) -> Path:
    """A bare repo standing in for GitHub, with one commit on main."""
    seed = tmp_path / "seed"
    (seed / "data" / "years").mkdir(parents=True)
    (seed / "data" / "all_events.csv").write_text(CSV)
    (seed / "data" / "years" / "2400-01.toml").write_text(TOML)
    git(seed, "init", "-q", "-b", "main")
    git(seed, "config", "user.name", "Seed")
    git(seed, "config", "user.email", "seed@example.com")
    git(seed, "add", "-A")
    git(seed, "commit", "-qm", "initial")

    bare = tmp_path / "remote.git"
    subprocess.run(["git", "clone", "--bare", "-q", str(seed), str(bare)], check=True)
    return bare


@pytest.fixture
def store(remote: Path, tmp_path: Path) -> Store:
    return Store.clone(str(remote), tmp_path / "clone")


def other_editor(remote: Path, tmp_path: Path, name: str = "other") -> Store:
    """A second server process editing the same repo."""
    return Store.clone(str(remote), tmp_path / name)


# --- the basics ------------------------------------------------------------

def test_a_fresh_clone_starts_on_a_draft_equal_to_main(store):
    assert store.head() == store.published_head()
    assert store.has_unpublished_changes() is False
    assert len(store.rows()) == 3


def test_saving_commits_to_the_draft_and_leaves_main_alone(store):
    rows = store.rows()
    rows.append(csvio.Row(date="2400-12-05", type="ptsa_event", label="Winter Social"))
    before = store.published_head()

    store.save(rows, "Allison", "added Winter Social")

    assert store.head() != before
    assert store.published_head() == before, "publishing must be a separate step"
    assert store.has_unpublished_changes() is True
    assert any(r.label == "Winter Social" for r in store.rows())


def test_a_save_is_pushed_immediately_so_the_server_holds_no_state(store, remote,
                                                                  tmp_path):
    """The container is disposable. Anything only on its disk is lost on
    redeploy, and losing someone's afternoon of typing to a routine restart is
    the kind of thing that stops people trusting the tool."""
    rows = store.rows()
    rows.append(csvio.Row(date="2400-12-05", type="ptsa_event", label="Winter Social"))
    store.save(rows, "Allison", "added Winter Social")

    fresh = other_editor(remote, tmp_path)
    assert any(r.label == "Winter Social" for r in fresh.rows())


def test_saving_nothing_makes_no_commit(store):
    """History is a list of things that happened. An empty commit per page
    refresh would make it useless for finding the change you are looking for."""
    before = store.head()
    assert store.save(store.rows(), "Allison", "no change at all") == before
    assert store.head() == before


def test_the_author_is_recorded_without_them_having_an_account(store):
    rows = store.rows()
    rows.append(csvio.Row(date="2400-12-05", type="ptsa_event", label="Winter Social"))
    store.save(rows, "Allison", "added Winter Social")

    latest = store.history()[0]
    assert latest.author == "Allison"
    assert latest.summary == "added Winter Social"


def test_an_unnamed_save_still_commits(store):
    """The name box is a courtesy, not a login. Leaving it blank must not be
    able to lose work."""
    rows = store.rows()
    rows.append(csvio.Row(date="2400-12-05", type="ptsa_event", label="Winter Social"))
    store.save(rows, "", "added Winter Social")
    assert store.history()[0].author == "Someone"


# --- publishing ------------------------------------------------------------

def test_publishing_fast_forwards_main(store):
    rows = store.rows()
    rows.append(csvio.Row(date="2400-12-05", type="ptsa_event", label="Winter Social"))
    store.save(rows, "Allison", "added Winter Social")

    published = store.publish()

    assert published == store.head()
    assert store.published_head() == store.head()
    assert store.has_unpublished_changes() is False


def test_publishing_reaches_the_remote_main_branch(store, remote):
    """Pushing to main is the entire publish step -- the deploy workflow
    triggers on it. If this push did not land, nothing would rebuild and the
    app would report success while the PDF stayed stale."""
    rows = store.rows()
    rows.append(csvio.Row(date="2400-12-05", type="ptsa_event", label="Winter Social"))
    store.save(rows, "Allison", "added Winter Social")
    store.publish()

    assert "Winter Social" in git(remote, "show", "main:data/all_events.csv")


def test_publishing_with_nothing_pending_is_a_no_op(store):
    before = store.published_head()
    assert store.publish() == before


def test_history_says_which_versions_are_published(store):
    rows = store.rows()
    rows.append(csvio.Row(date="2400-12-05", type="ptsa_event", label="Winter Social"))
    store.save(rows, "Allison", "added Winter Social")
    store.publish()

    rows = store.rows()
    rows.append(csvio.Row(date="2401-01-20", type="ptsa_event", label="Book Fair"))
    store.save(rows, "Sam", "added Book Fair")

    versions = store.history()
    assert [v.summary for v in versions[:2]] == ["added Book Fair",
                                                 "added Winter Social"]
    assert versions[0].published is False
    assert versions[1].published is True


# --- two people at once ----------------------------------------------------

def test_a_save_against_a_stale_base_is_refused(store, remote, tmp_path):
    """Two people editing at once must not silently overwrite each other.

    The second save is written from a page that never saw the first one, so
    saving it would drop that change with nothing to show it ever existed.
    """
    base = store.head()

    sam = other_editor(remote, tmp_path, "sam")
    rows = sam.rows()
    rows.append(csvio.Row(date="2401-01-20", type="ptsa_event", label="Book Fair"))
    sam.save(rows, "Sam", "added Book Fair")

    mine = store.rows()
    mine.append(csvio.Row(date="2400-12-05", type="ptsa_event", label="Winter Social"))
    with pytest.raises(Conflict) as caught:
        store.save(mine, "Allison", "added Winter Social", base=base)
    assert "Someone else saved" in str(caught.value)


def test_the_refused_save_did_not_lose_the_other_persons_change(store, remote,
                                                                tmp_path):
    base = store.head()
    sam = other_editor(remote, tmp_path, "sam")
    rows = sam.rows()
    rows.append(csvio.Row(date="2401-01-20", type="ptsa_event", label="Book Fair"))
    sam.save(rows, "Sam", "added Book Fair")

    with pytest.raises(Conflict):
        store.save(store.rows(), "Allison", "whatever", base=base)

    assert any(r.label == "Book Fair" for r in store.rows())


def test_saving_without_a_base_does_not_check(store):
    """The first load of a page has no base to send, and a save from it is not
    a conflict with anything."""
    rows = store.rows()
    rows.append(csvio.Row(date="2400-12-05", type="ptsa_event", label="Winter Social"))
    assert store.save(rows, "Allison", "added Winter Social") != store.published_head()


# --- restoring -------------------------------------------------------------

def test_restoring_brings_back_the_old_dates(store):
    original = store.rows()
    first = store.head()

    rows = list(original)
    rows.append(csvio.Row(date="2400-12-05", type="ptsa_event", label="Winter Social"))
    store.save(rows, "Allison", "added Winter Social")
    assert any(r.label == "Winter Social" for r in store.rows())

    store.restore(first, "Allison")
    assert [r.label for r in store.rows()] == [r.label for r in original]


def test_restoring_adds_to_history_rather_than_rewriting_it(store):
    """Someone looking later has to be able to see that a restore happened."""
    first = store.head()
    rows = store.rows()
    rows.append(csvio.Row(date="2400-12-05", type="ptsa_event", label="Winter Social"))
    store.save(rows, "Allison", "added Winter Social")

    store.restore(first, "Sam")

    summaries = [v.summary for v in store.history()]
    assert summaries[0].startswith("restored the version from")
    assert "added Winter Social" in summaries, (
        "the restored-over version disappeared from history")


def test_restoring_does_not_publish_by_itself(store, remote):
    """A mis-click must not reach families. Publishing stays a separate press."""
    first = store.head()
    rows = store.rows()
    rows.append(csvio.Row(date="2400-12-05", type="ptsa_event", label="Winter Social"))
    store.save(rows, "Allison", "added Winter Social")
    store.publish()

    store.restore(first, "Sam")
    assert store.has_unpublished_changes() is True
    assert "Winter Social" in git(remote, "show", "main:data/all_events.csv"), (
        "the restore reached the published branch without anyone publishing")


def test_restoring_an_unknown_version_says_so(store):
    with pytest.raises(StoreError) as caught:
        store.restore("0" * 40, "Allison")
    assert "No such version" in str(caught.value)


def test_restoring_to_what_is_already_there_makes_no_commit(store):
    before = store.head()
    assert store.restore(before, "Allison") == before


# --- safety ----------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "origin\thttps://x-access-token:ghp_SECRETVALUE@github.com/o/r.git (fetch)",
    "fatal: could not read from "
    "'https://x-access-token:ghp_SECRETVALUE@github.com/o/r.git'",
])
def test_redact_removes_credentials_from_a_url(text):
    """`git remote -v` prints the remote in full, token and all.

    Nothing in the store runs it today; _redact is what stops the day somebody
    adds it for diagnostics from putting a live token into an error page and
    the container logs.
    """
    cleaned = _redact(text)
    assert "ghp_SECRETVALUE" not in cleaned
    assert "***" in cleaned
    assert "github.com/o/r.git" in cleaned, "it redacted more than the credentials"


def test_a_failed_git_command_does_not_leak_the_token(store):
    """The whole message a user could be shown, end to end.

    Deliberately asserts only that the token is absent, not that _redact is
    what removed it: modern git strips credentials from its own error output,
    so pinning "***" here would have been pinning git's behaviour rather than
    ours. The earlier version of this test pointed at a directory that was not
    a repository, so git said "not a git repository" -- a message with no URL
    in it -- and the test passed with _redact stubbed out entirely.
    """
    store._git("remote", "set-url", "origin",
               "https://x-access-token:ghp_SECRETVALUE@127.0.0.1:1/o/r.git")

    with pytest.raises(StoreError) as caught:
        store._git("push", "origin", "main")

    assert "ghp_SECRETVALUE" not in str(caught.value)
    assert "127.0.0.1" in str(caught.value), (
        "git said nothing about the remote, so this proves nothing")


def test_a_restart_picks_the_draft_back_up(store, remote, tmp_path):
    """A redeploy in the middle of someone's editing session must not discard
    what they had already saved."""
    rows = store.rows()
    rows.append(csvio.Row(date="2400-12-05", type="ptsa_event", label="Winter Social"))
    store.save(rows, "Allison", "added Winter Social")

    restarted = Store.clone(str(remote), tmp_path / "after-restart")
    assert any(r.label == "Winter Social" for r in restarted.rows())
    assert restarted.has_unpublished_changes() is True
