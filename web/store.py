"""The repository, as the editor sees it: a draft, a published version, history.

There is no database. The calendar's data is already a CSV under version
control, and putting a copy of it in Postgres would mean two answers to "what
are this year's dates?" and a migration to get them back out again. Git gives
us history, authorship, diffs and revert for free, and -- the part that matters
for a volunteer-run tool -- if this app disappears in three years the data is
still a CSV in a repo that `build.py` still renders.

The shape:

    origin/main    what is published. Pushing to it triggers the deploy
                   workflow, which builds the PDF and pushes it to gh-pages.
    origin/draft   edits that have been saved but not published. Always
                   descends from main, so publishing is a fast-forward push.

Every save is a commit on `draft`, pushed immediately. That is what makes the
server disposable: it holds no state that is not already on GitHub, so a
restart, a redeploy or a move to another host loses nothing. On boot it clones
and carries on.
"""

from __future__ import annotations

import datetime as dt
import os
import re
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

from .csvio import Row, read as read_rows, write as write_rows

CSV_PATH = "data/all_events.csv"
YEARS_PATH = "data/years"

#: Written on every commit the app makes. Individual people are identified in
#: the commit message instead -- see `save` -- because they do not have
#: accounts, and inventing an email address for them would put a fake identity
#: in permanent history.
BOT_NAME = "PTSA Calendar Editor"
BOT_EMAIL = "calendar-editor@users.noreply.github.com"


class StoreError(Exception):
    """Something went wrong talking to git. Message is safe to show a user."""


class Conflict(StoreError):
    """Someone else saved while this person was editing.

    Carries no fix of its own on purpose: silently merging two people's idea of
    the calendar is exactly the outcome nobody could explain afterwards.
    """


@dataclass(frozen=True)
class Version:
    sha: str
    when: dt.datetime
    author: str
    summary: str
    published: bool

    @property
    def short(self) -> str:
        return self.sha[:8]

    def when_local(self, tz: dt.tzinfo | None = None) -> str:
        return self.when.astimezone(tz).strftime("%b %-d, %Y at %-I:%M %p")


def _redact(text: str) -> str:
    """Strip anything that looks like a token out of git's chatter.

    The remote URL carries a GitHub token, and git puts the remote URL in a
    good number of its error messages. Those messages get shown to users and
    written to logs.
    """
    return re.sub(r"(https://)[^@/\s]+(@)", r"\1***\2", text)


class Store:
    """A working clone of the calendar repo.

    Writes are serialised: this is one clone on one disk, and two requests
    running `git commit` in it at the same moment would interleave in ways that
    are not worth reasoning about. The lock is per-process, which is correct
    because the app runs as a single process; running two copies against one
    repo is not supported and would need real locking.
    """

    def __init__(self, repo: Path, remote: str | None = None,
                 main: str = "main", draft: str = "draft"):
        self.repo = Path(repo)
        self.remote = remote
        self.main = main
        self.draft = draft
        self.lock = threading.Lock()

    # --- git plumbing ------------------------------------------------------

    def _git(self, *args: str, check: bool = True) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.repo), *args],
            capture_output=True, text=True,
            # Never let git stop for a credential prompt: in a container there
            # is no terminal to answer it and the request would hang until it
            # timed out, with no clue why.
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        if check and result.returncode != 0:
            raise StoreError(
                f"git {' '.join(args[:2])} failed: "
                f"{_redact(result.stderr.strip() or result.stdout.strip())}"
            )
        return result.stdout.strip()

    # --- setup -------------------------------------------------------------

    @classmethod
    def clone(cls, remote: str, into: Path, **kw) -> "Store":
        into = Path(into)
        if not (into / ".git").exists():
            into.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                ["git", "clone", remote, str(into)],
                capture_output=True, text=True,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            )
            if result.returncode != 0:
                raise StoreError(f"could not clone: {_redact(result.stderr)}")
        store = cls(into, remote=remote, **kw)
        store.sync()
        return store

    def sync(self) -> None:
        """Fetch, and put the working tree on the draft branch.

        Called on boot and before any save. The draft branch is created from
        main the first time, and always *reset* to the remote rather than
        merged into: the remote is the truth, and a local clone that has
        drifted from it is a container that has been up too long, not an edit
        anyone made.
        """
        self._git("config", "user.name", BOT_NAME)
        self._git("config", "user.email", BOT_EMAIL)
        if self.remote:
            self._git("fetch", "origin", self.main, self.draft, check=False)
            self._git("fetch", "origin", self.main)

        remote_draft = f"origin/{self.draft}"
        start = remote_draft if self._exists(remote_draft) else f"origin/{self.main}"
        self._git("checkout", "-B", self.draft, start)

        if self.remote:
            # Keep the local main ref honest. Nothing reads it -- published_head
            # uses origin/main -- but a clone where `git show main:...` returns
            # a stale file is a trap for whoever is next debugging this on the
            # server, and it costs one command not to leave one lying around.
            # After the checkout above, not before: git refuses to force-move
            # the branch that HEAD is on, and on a fresh clone that is main.
            self._git("branch", "-f", self.main, f"origin/{self.main}")

    def _exists(self, ref: str) -> bool:
        return subprocess.run(
            ["git", "-C", str(self.repo), "rev-parse", "--verify", "--quiet", ref],
            capture_output=True,
        ).returncode == 0

    # --- reading -----------------------------------------------------------

    @property
    def csv_path(self) -> Path:
        return self.repo / CSV_PATH

    @property
    def years_dir(self) -> Path:
        return self.repo / YEARS_PATH

    def head(self) -> str:
        return self._git("rev-parse", "HEAD")

    def published_head(self) -> str:
        ref = f"origin/{self.main}" if self.remote else self.main
        return self._git("rev-parse", ref)

    def rows(self) -> list[Row]:
        return read_rows(self.csv_path)

    def rows_at(self, sha: str) -> list[Row]:
        from .csvio import parse
        return parse(self._git("show", f"{sha}:{CSV_PATH}"))

    def has_unpublished_changes(self) -> bool:
        """True when the draft differs from what is published.

        Compares the *data*, not the commits: restoring an old version creates
        a new commit whose content matches main, and telling someone they have
        unpublished changes when the calendar would come out identical is a
        prompt to publish nothing.
        """
        return bool(self._git("diff", "--name-only",
                              self.published_head(), "HEAD", "--", "data"))

    def history(self, limit: int = 50) -> list[Version]:
        """Recent versions, newest first, flagged by whether they are published."""
        published = set(self._git(
            "rev-list", self.published_head(), f"--max-count={limit * 4}"
        ).split())
        sep = "\x1f"
        raw = self._git(
            "log", f"--max-count={limit}", f"--format=%H{sep}%aI{sep}%s", "HEAD",
            "--", "data",
        )
        versions = []
        for line in filter(None, raw.splitlines()):
            sha, when, summary = line.split(sep, 2)
            author, _, rest = summary.partition(": ")
            if not rest:            # a commit not made by the editor
                author, rest = "", summary
            versions.append(Version(
                sha=sha,
                when=dt.datetime.fromisoformat(when),
                author=author,
                summary=rest,
                published=sha in published,
            ))
        return versions

    # --- writing -----------------------------------------------------------

    def save(self, rows: list[Row], author: str, summary: str,
             base: str | None = None) -> str:
        """Write the rows, commit, push. Returns the new draft sha.

        ``base`` is the sha the editing session started from. If the draft has
        moved on since, this raises Conflict rather than overwriting: the other
        person's save is already committed and pushed, and quietly replacing
        the file with a version that never saw their change is how someone's
        work disappears without anyone noticing.
        """
        with self.lock:
            self.sync()
            if base is not None and base != self.head():
                raise Conflict(
                    "Someone else saved a change while you were editing. "
                    "Reload to pick up their version -- your edits are not lost, "
                    "but they need re-applying on top."
                )
            write_rows(self.csv_path, rows)
            return self._commit(author, summary)

    def _commit(self, author: str, summary: str) -> str:
        """Commit whatever is staged in data/, or return HEAD if nothing moved.

        A save that changes nothing must not make an empty commit -- the
        history is meant to be a list of things that happened.
        """
        self._git("add", "--", "data")
        if not self._git("diff", "--cached", "--name-only"):
            return self.head()

        who = (author or "").strip() or "Someone"
        self._git("commit", "-m", f"{who}: {summary}")
        self._push(self.draft)
        return self.head()

    def _push(self, branch: str, target: str | None = None) -> None:
        if not self.remote:
            return
        self._git("push", "origin", f"{branch}:{target or branch}")

    def publish(self) -> str:
        """Fast-forward main to the draft. Returns the published sha.

        A plain push, because the draft always descends from main -- which is
        also what makes this safe. If it ever does not, git refuses rather than
        forcing, and the refusal is the right outcome: something changed main
        behind the app's back and a person should look.

        Pushing to main is the whole publish step. The deploy workflow already
        triggers on pushes to main that touch data/, so it builds the PDF and
        pushes it to gh-pages on its own. Nothing here builds or uploads a PDF:
        one publisher, so there is nothing for a second one to disagree with.
        """
        with self.lock:
            self.sync()
            if not self.has_unpublished_changes():
                return self.published_head()
            if self.remote:
                self._push(self.draft, self.main)
            else:
                self._git("branch", "-f", self.main, "HEAD")
            return self.head()

    def restore(self, sha: str, author: str) -> str:
        """Put an old version's data back as a new draft commit.

        Deliberately forward-only: a new commit that happens to contain old
        content, never a rewrite of history. Whoever comes looking later can
        see that a restore happened and what it restored, and the person doing
        it still has to publish, so a mis-click is not live.
        """
        with self.lock:
            self.sync()
            try:
                when = self._git("show", "-s", "--format=%aI", sha)
                subject = self._git("show", "-s", "--format=%s", sha)
            except StoreError as exc:
                raise StoreError(f"No such version: {sha[:8]}") from exc
            self._git("checkout", sha, "--", "data")
            date = dt.datetime.fromisoformat(when).strftime("%b %-d")
            return self._commit(
                author, f"restored the version from {date} ({subject})")
