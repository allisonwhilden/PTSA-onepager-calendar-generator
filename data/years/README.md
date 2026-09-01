# School-year configs

One file per school year, named for the year it covers: `2026-27.toml`.

## Where the district dates come from

The **[LWSD calendar page](https://www.lwsd.org/calendar)** — always that page,
never a saved PDF link.

The one-page PDF sits on a version-stamped CDN URL, and LWSD republishes under a
*new* URL when dates change. An older copy still reads "FINAL" and still covers
the right school year, so there is no visible sign it has been superseded. Check
the "Updated M/YYYY" line in the bottom-right against the copy the calendar page
links today.

This is not hypothetical: between the 7/2026 and 8/2026 revisions of the 2026-27
calendar, Elementary Grades Due moved from Jan 13 to Jan 20.

Preschool dates are deliberately left out of this calendar — see commit 64e3061.

The **August LEAP week** is left out too. Those are staff days before school
starts, so they tell a parent nothing while costing a solid black week on the
grid and a line in the dates list. LWSD prints the block every year (`Aug. 24-28`
for 2026-27, `Aug. 25-29` the year before), so at a roll it looks like a date you
forgot — it isn't. The *single* LEAP Days during the year are no-school days for
students and are kept.

## Rolling to a new year

1. **Copy the newest config.**

   ```bash
   cp data/years/2026-27.toml data/years/2027-28.toml
   ```

2. **Re-stamp the header.** The comment at the top of the file you just copied
   records which LWSD revision its dates were checked against — the whole point
   of the section above. Copied forward unedited it becomes a false claim, in
   the one place meant to protect you from exactly that. Replace the revision
   line, and delete the worked example of what moved between revisions; it
   belongs to the year you copied from.

3. **Set the three values** in the new file:
   - `early_release_start` — the first early-release Wednesday
   - `last_day` — the last day of school
   - `boxed_days` — the days school starts and ends, drawn with the box

   All three must fall inside the year being built. Dates left over from the
   previous year are rejected with a message saying so, rather than quietly
   drawing nothing.

   Nothing validates the header, so unlike these three a stale one fails
   silently. Do it first.

4. **Add the year's events to `data/all_events.csv`** — *add*, alongside the
   rows already there. The calendar prints August through July of the year being
   built, so rows outside that span are reported as *notices* and never appear.
   Notices do not fail the build even under `--strict`, which is what lets both
   years sit in the file at once.

   **Do not delete the outgoing year's rows until its year has ended.** Until
   then `build.py` is still building it, and a CSV holding only next year's
   dates leaves it with nothing to draw: `--check --strict` exits 1 with *"none
   of the N rows fall inside <year>, so the calendar would be blank"*, and
   because CI runs the same command, the merge to `main` fails with it. Delete
   them on the far side of the roll, when the new year is the one being built.

5. **Check it before you build:**

   ```bash
   python python/build.py --check --strict
   ```

   This validates every row and tells you about anything questionable, without
   spending time rendering.

6. **Review the new page and record it.** The golden snapshot is per-year, so
   the first run for a new year fails on purpose:

   ```
   No snapshot for 2027-28. This year's page has never been reviewed
   ```

   Build it, look the PDF over, then record it so future changes show as a diff:

   ```bash
   UPDATE_GOLDEN=1 pytest python/tests/test_render.py
   ```

   Until you do, `pytest` fails and the workflow will not publish.

7. **Build it:**

   ```bash
   python python/build.py
   ```

No code changes and no workflow changes -- but step 6 is not optional: the
snapshot is the only review the printed page gets.

`build.py` builds the school year that *today* falls in. A config added early
simply waits: it takes over on the August its own year begins, and until then
the current year keeps building normally — provided the current year still has
its rows in the CSV, which is what step 4 is about. The fallback only applies when the
current school year has no config at all -- then the build uses the newest
config it has, says so, and **publishing is skipped** rather than serving a
calendar that has already ended.

To build a specific year regardless of today's date: `--year 2026`.
Only years whose rows are still in the CSV can be built -- asking for a
year whose rows have been replaced fails with "the calendar would be
blank" rather than printing an empty page.

## Why these two dates and nothing else

Early-release Wednesdays are a *rule*, not data — every Wednesday in session gets
marked, so listing ~38 of them in the CSV would be noise. The rule needs a start
and an end, which is what this file holds.

Everything else the calendar knows comes from the CSV, so that adding a date is
always the same action no matter what kind of date it is.
