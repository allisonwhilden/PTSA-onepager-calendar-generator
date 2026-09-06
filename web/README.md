# The calendar editor

A web form over `data/all_events.csv`, so that someone on the PTSA board can
change a date without touching a CSV, a terminal, or GitHub.

**It does not draw the calendar.** It edits the data, asks
`calendar_gen.pipeline` whether the result is valid, shows the page that the
same pipeline renders, and pushes to `main` so the existing deploy workflow
publishes the PDF exactly as it always has. If a rule about dates or drawing
ends up in this directory, it is in the wrong place — see the non-negotiables
in [CLAUDE.md](../CLAUDE.md).

## How it hangs together

```
  someone edits a date
        │
        ▼
  web/  ── writes ──▶  data/all_events.csv  (in a clone the container holds)
        │                     │
        │                     └── calendar_gen.pipeline ──▶ preview (~1s)
        │
        ├── save    ──▶  commit + push to origin/draft
        └── publish ──▶  push draft to origin/main
                                │
                                ▼
                   .github/workflows/build-and-deploy.yml
                                │
                                ▼
                    gh-pages: calendar.pdf   ← what the school website links
```

Two properties this shape is chosen for:

**The editor being down does not take the calendar down.** The published PDF is
on gh-pages and the dates are a CSV in the repo. If this app breaks, or its host
disappears, families still see the calendar and the dates can still be edited on
GitHub directly.

**A suggestion never becomes data on its own.** Starting a new school year
offers each of last year's events 364 days on -- 52 whole weeks, so a Thursday
event stays on a Thursday -- next to the date it had. Nothing is carried over
until someone ticks it. That is why there is no "needs checking" state stored
anywhere: the ticking *is* the check, and an unticked row is not submitted at
all, so an unreviewed guess has no route into the CSV.

**The server holds nothing.** Every save is committed and pushed as it happens,
so a restart, a redeploy or a move to a different host loses no one's work. On
boot it clones and carries on.

## The pieces

| | |
|---|---|
| `app.py` | routes and pages; decides nothing about dates |
| `store.py` | the repo as draft / published / history — git is the database |
| `csvio.py` | reads and writes the CSV without disturbing it |
| `changes.py` | "Bike Derby moved from Sep 17 to Sep 24" |
| `auth.py` | one shared password, a signed cookie |
| `newyear.py` | proposes last year's dates a year on; writes nothing on its own |

## Running it locally

```bash
pip install -r python/requirements.txt -r web/requirements.txt

export EDITOR_PASSWORD_HASH="$(python -c \
  'import sys; sys.path.insert(0, "."); from web.auth import hash_password; \
   print(hash_password("whatever you like"))')"
export SECURE_COOKIES=false      # no HTTPS in front of it locally

PYTHONPATH=.:python uvicorn web.app:factory --factory --reload --port 8000
```

With no `REPO_REMOTE` set it edits *this* checkout, and "publish" moves the
local `main`. Nothing is pushed anywhere.

## Deploying it

See [../docs/deploying-the-editor.md](../docs/deploying-the-editor.md).

## Settings

| Variable | | |
|---|---|---|
| `EDITOR_PASSWORD_HASH` | **required** | argon2 hash of the shared password. Generate with `hash_password` above; never store the password itself. |
| `REPO_REMOTE` | | Clone URL. Without it the editor works on the checkout it is running from. |
| `GITHUB_TOKEN` | | A token that may push to the repo. Injected into the remote URL; redacted from every error message the app can produce. |
| `WORKDIR` | `/data/repo` | Where the clone lives. Disposable. |
| `PUBLISHED_PDF_URL` | | Shown as a link after publishing. |
| `SECURE_COOKIES` | `true` | Session cookie's Secure flag. Only turn it off without HTTPS. |
| `SESSION_SECRET` | password hash | Signing key. Defaults so there is one secret to manage, and so changing the password signs everyone out. |

## Tests

```bash
pytest web/tests
```

They drive the real app over HTTP against a real git repository — a bare one in
a temp directory. The interesting things here are the joins (a form post
becoming a commit; a broken calendar still being editable; publishing being a
separate act from saving), and a mocked store would hold exactly those apart.
