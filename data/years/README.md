# School-year configs

One file per school year, named for the year it covers: `2026-27.toml`.

## Rolling to a new year

1. **Copy the newest config.**

   ```bash
   cp data/years/2025-26.toml data/years/2026-27.toml
   ```

2. **Set the three values** in the new file:
   - `early_release_start` — the first early-release Wednesday
   - `last_day` — the last day of school
   - `boxed_days` — the days school starts and ends, drawn with the box

   All three must fall inside the year being built. Dates left over from the
   previous year are rejected with a message saying so, rather than quietly
   drawing nothing.

3. **Put the year's events in `data/all_events.csv`.** Replace the old year's rows;
   the calendar prints August through July of the year being built, so leftovers
   from a previous year are reported as *notices* and never appear. Notices do
   not fail the build even under `--strict`, so you can stage next year's dates
   alongside this year's while you work.

4. **Check it before you build:**

   ```bash
   python python/build.py --check
   ```

   This validates every row and tells you about anything questionable, without
   spending time rendering.

5. **Build it:**

   ```bash
   python python/build.py
   ```

No code changes, and no workflow changes. `build.py` picks the current school year
by today's date, so once `2026-27.toml` exists it builds automatically from August
onward. Until then it builds the newest year it has and says so.

To build a specific year regardless of today's date: `--year 2025`.

## Why these two dates and nothing else

Early-release Wednesdays are a *rule*, not data — every Wednesday in session gets
marked, so listing ~38 of them in the CSV would be noise. The rule needs a start
and an end, which is what this file holds.

Everything else the calendar knows comes from the CSV, so that adding a date is
always the same action no matter what kind of date it is.
