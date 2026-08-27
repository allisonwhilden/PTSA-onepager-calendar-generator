# Horace Mann PTSA Calendar Generator

Turns one CSV of dates into a single-page, print-ready school-year calendar
combining Lake Washington School District dates with PTSA events.

📅 **[View the current calendar](https://allisonwhilden.github.io/PTSA-onepager-calendar-generator/)**
· 📄 **[Download the PDF](https://allisonwhilden.github.io/PTSA-onepager-calendar-generator/calendar.pdf)**

Every push to `main` that touches `data/` or `python/` validates the data, runs
the tests, rebuilds the PDF and republishes it.

---

## The everyday task: change a date

1. Edit `data/all_events.csv`.
2. Check it: `python python/build.py --check`
3. Commit and push. The published PDF updates itself.

`--check` validates every row and reports all problems at once with line
numbers, without spending time rendering.

## Rolling to a new school year

Two files, no code changes. See **[data/years/README.md](data/years/README.md)**.

```bash
cp data/years/2025-26.toml data/years/2026-27.toml   # set the two dates inside
# replace the rows in data/all_events.csv
python python/build.py --check
```

`build.py` picks the current school year from today's date, so once the config
exists it builds automatically from August onward.

---

## Setup

WeasyPrint needs system libraries before the Python packages will work.

```bash
# macOS
brew install pango gdk-pixbuf libffi

# Debian / Ubuntu
sudo apt-get install -y python3-dev libcairo2 libpango-1.0-0 \
  libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info
```

Then:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r python/requirements.txt
```

## Building

```bash
python python/build.py                  # current school year -> build/
python python/build.py --year 2025      # a specific year
python python/build.py --check          # validate only
python python/build.py --strict         # treat warnings as errors
python python/build.py --out cal.pdf    # somewhere specific
```

Runs from any directory.

## Testing

```bash
pytest
```

67 tests covering type resolution, CSV validation, grid construction,
early-release marking, date consolidation and year selection — plus a golden
snapshot of the rendered page and an assertion that the PDF is exactly one
Letter page.

When you change the page on purpose, re-record the snapshot:

```bash
UPDATE_GOLDEN=1 pytest python/tests/test_render.py
```

---

## The data file

```csv
date,start_date,end_date,type,label,notes
2025-09-02,,,first_day,First Day (Grades 1-12),
,2025-12-22,2026-01-02,no_school,Winter Break,
2025-09-30,,,ptsa_event,Picture Day,
```

- Use `date` for a single day, **or** `start_date` + `end_date` for a range.
- `label` is what prints in the Important Dates list.
- `notes` is optional and does not print.
- Repeats of the same label fold into one line: four Board Meeting rows print as
  `10/23, 2/19, 4/23, 6/4 PTSA: Board Meeting`.

### Event types

| Type | On the calendar | In the dates list |
|---|---|---|
| `no_school` | Black cell | ✓ |
| `half_day` | Grey cell | ✓ |
| `closure_possible` | Diagonal stripes | ✓ |
| `early_release` | Bold number | ✓ |
| `ptsa_event` | Red circle | ✓ prefixed `PTSA:` |
| `first_day` / `last_day` | *(nothing — see below)* | ✓ |
| `informational` | *(nothing)* | ✓ |

Also accepted as spellings of the above: `holiday`, `first_day_k`,
`first_day_1_12`, `closure_day`, `possible_school_day`, `potential_school_day`,
`grades_due`, `kinder_family_conn`.

A day carrying something with no visual — an `informational` date, say — gets an
asterisk, pointing the reader at the dates list. Anything already drawn speaks
for itself.

**A type that isn't in this table fails the build**, naming the row. The
generator never guesses what an unknown type should look like. See
[DECISIONS.md](DECISIONS.md).

**Adding a new kind of date** is one line in `python/calendar_gen/event_types.py`
saying how it's drawn, plus a CSS rule if it needs a new fill.

### Early release and the first/last-day box

These two come from `data/years/<year>.toml`, not the CSV:

- **Early-release Wednesdays** are a rule, not data — every Wednesday between
  `early_release_start` and `last_day` is marked automatically, unless the day is
  already off or already short.
- **The first/last-day box** is drawn on the days in `boxed_days`. The CSV also
  uses `first_day`/`last_day` for per-population dates (kindergarten, SNAPS,
  secondary semester ends); those are listed but not boxed, because the legend
  promises the start and end of school.

---

## Layout

```
data/
  all_events.csv          the dates
  years/2025-26.toml      per-year config (two dates, plus the boxed days)
python/
  build.py                CLI
  calendar_gen/
    event_types.py        what each type is and how it's drawn
    events.py             CSV reading and validation
    school_year.py        year config and year selection
    layout.py             grid cells and the Important Dates list
    render.py             HTML, then PDF
  templates/  styles/     the page itself
  tests/                  including the golden snapshot
```

## License

MIT
