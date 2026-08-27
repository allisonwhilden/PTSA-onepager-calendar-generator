# Agent Instructions

A one-page, print-ready school-year calendar for the Horace Mann PTSA, generated
from a single CSV by `python/build.py`.

**[CLAUDE.md](CLAUDE.md) is the full guide** — read it before changing anything.
This file is the short version for agents that don't read CLAUDE.md, and
[DECISIONS.md](DECISIONS.md) records the choices that are expensive to reverse.

## The four rules

1. **One renderer.** `python/build.py` is the only thing that draws the calendar.
   Do not add a second implementation in any language. One already existed and
   the two drifted into disagreeing about what the calendar said.

2. **Never guess at data.** An event type not declared in
   `python/calendar_gen/event_types.py` must fail the build with its row number.
   The original bug here was a lookup that silently mapped an unknown type to
   `no_school`, printing five ordinary school days as "No School".

3. **The renderer does not choose which dates appear.** If a row is in the CSV,
   it is shown. The registry declares only *how* each type is drawn.

4. **It must stay one page.** `test_calendar_is_exactly_one_page` guards this.
   Fix the layout rather than the test.

## Commands

```bash
source .venv/bin/activate
pip install -r python/requirements.txt

python python/build.py            # build the current school year into build/
python python/build.py --check    # validate the CSV, render nothing
pytest                            # 83 tests, ~2s
```

Everything runs from any directory. If a command needs a `cd` first, that's a bug.

After changing anything that affects the printed page, run `pytest`. The golden
snapshot will show you the diff — **read it** before committing. It is the only
review the printed page gets. If the change was intentional:

```bash
UPDATE_GOLDEN=1 pytest python/tests/test_render.py
```

## Issue tracking

None. This repo previously carried `bd` (beads) scaffolding that never held a
single issue; it has been removed. Use GitHub issues if something needs tracking,
and otherwise just say what's left in your handoff.

## Finishing a session

- Commit logically separate changes separately, with messages that say *why*.
- Push to the branch you were asked to work on. Never push to `main` without
  being asked.
- Run `pytest` before you commit anything touching `python/` or `data/`.
- **If the remote rejects your push, read the error before retrying.** Permission
  and email-privacy rejections are not transient — retrying in a loop will not
  fix them. Say plainly what is blocked and what the human needs to do. Leaving
  work committed locally with a clear explanation is a fine outcome; silently
  retrying is not.
- Report honestly. If tests fail, say so and show the output. If you skipped
  something, say that too.
