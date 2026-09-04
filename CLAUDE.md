# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

A one-page, print-ready school-year calendar for the Horace Mann PTSA, generated
from a single CSV. District dates and PTSA events are combined onto one Letter
page that goes home with families.

**The printed page is the product.** Everything else exists to produce it
correctly.

## Non-negotiables

1. **One renderer.** `python/build.py` is the only thing that draws the calendar.
   Do not add a second implementation in any language. A Next.js app previously
   did exactly this and the two drifted into disagreeing about what the calendar
   said — see [DECISIONS.md](DECISIONS.md). It is parked on `web-ui-parked`.

2. **Never guess at data.** An event type that isn't declared in
   `python/calendar_gen/event_types.py` must fail the build with its row number.
   The original bug in this repo was a lookup that silently mapped an unknown
   type to `no_school`, printing five ordinary school days as "No School".

3. **The renderer does not decide which dates appear.** If a row is in the CSV it
   is shown. The registry declares only *how* each type is drawn. Never filter
   rows out because they seem unimportant.

4. **It must stay one page.** `test_calendar_is_exactly_one_page` guards this. If
   a change breaks it, fix the layout — do not relax the test.

## Commands

```bash
source .venv/bin/activate

python python/build.py            # build the current school year into build/
python python/build.py --check    # validate the CSV and the one-page fit
python python/build.py --year 2026
pytest                            # 107 tests, ~4s
```

`build.py` runs from any directory; if it ever needs a `cd` first, that's
a bug. Run `pytest` from the repo root — pytest only honours `testpaths` when
invoked from the directory holding `pytest.ini`.

After changing anything that affects the printed page, run `pytest` — the golden
snapshot will show you the diff. If the change was intentional, re-record it:

```bash
UPDATE_GOLDEN=1 pytest python/tests/test_render.py
```

Review that diff before committing. It is the only review the printed page gets.

## Where things live

| Concern | File |
|---|---|
| What a type is, how it's drawn | `python/calendar_gen/event_types.py` |
| CSV reading and validation | `python/calendar_gen/events.py` |
| Year config, year selection | `python/calendar_gen/school_year.py` |
| Grid cells, Important Dates | `python/calendar_gen/layout.py` |
| HTML then PDF | `python/calendar_gen/render.py` |
| The page itself | `python/templates/`, `python/styles/calendar.css` |
| The dates | `data/all_events.csv` |
| Per-year config | `data/years/<label>.toml` |

## Rules that are easy to get wrong

- **Early-release Wednesdays are generated, not data.** Every Wednesday between
  `early_release_start` and `last_day` is marked, unless the day is already
  `no_school` or `half_day`. They are not CSV rows.

- **The first/last-day box comes from `boxed_days` in the year config**, not from
  `first_day`/`last_day` rows. It marks the days school starts and ends — both
  first days count, grades 1-12 and kindergarten. The CSV also uses those types
  for dates that are not year boundaries (SNAPS, quarter and semester ends);
  those are listed but not boxed.

- **The asterisk has one rule:** a day gets `*` when it carries an *event* whose
  type draws nothing — no fill, no circle — so the grid gives the reader no hint
  that something is listed. A fill or a circle speaks for that event.
  The first/last-day box does not, because it comes from the year config rather
  than from any event: it says a boundary falls here, not which one, so a boxed
  day still points at the list. Do not add special cases; the previous version
  had eight and nobody could predict its output.

- **Repeat events fold together** in the dates list, grouped by label. This is
  deliberate — the page is tight.

- **The calendar prints August through June** — the school year plus the August
  it starts in. Eleven months, so the grid is 3 + 3 + 3 + 2 with one empty slot.
  July is deliberately off: nothing in a school year falls in it. `MONTH_COUNT`
  in `school_year.py` is the single source for this, and `last_printed_day` is
  derived from it so the drawn months and the dropped-date span cannot drift.
  Rows outside that span are reported as *notices* and dropped —
  deliberately not warnings, so `--strict` does not fail the build when you
  stage next year's dates early or leave last year's in place.

## Rolling to a new school year

A config file and a CSV. No code changes, no workflow changes. See
[data/years/README.md](data/years/README.md). If a year roll ever requires
editing Python, that is a bug worth fixing instead.

## Publishing

`.github/workflows/build-and-deploy.yml` validates, tests, builds and pushes the
PDF to the `gh-pages` branch on every push to `main` touching `data/` or
`python/`. The path filters must match where the files actually are — they
silently stopped matching once before, and the published PDF went stale for
eight months without anyone noticing.

The deploy step runs `--require-current-year` first and **skips publishing** if
the only buildable year has already ended, writing the reason to the job
summary. Republishing an ended calendar behind a link the README calls "the
current calendar" is the same silent staleness, just with a green check.
