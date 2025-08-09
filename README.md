# One-Page Calendar (WeasyPrint + Jinja)

This starter lets you generate a single-page PDF calendar from CSV data using Python, Jinja templates, and WeasyPrint.

## Quick start

1) **Install system deps** (WeasyPrint uses Cairo, Pango, GDK-PixBuf):
   - **macOS** (Homebrew):
     ```bash
     brew install pygobject3 cairo pango gdk-pixbuf libffi
     ```
   - **Ubuntu/Debian**:
     ```bash
     sudo apt-get update
     sudo apt-get install -y python3-dev python3-pip libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info
     ```

2) **Create & activate a virtualenv**, then install Python deps:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3) **Edit CSVs** under `data/` for district + PTSA-specific events.
   - `events.csv` = district data
   - `ptsa_events.csv` = school/PTSA data

4) **Build the PDF**:
   ```bash
   python build.py --year 2025 --out build/LWSD-2025-26-onepage.pdf
   ```

5) Output appears under `build/`. The template renders 12 mini-months + a right-hand Important Dates + Legend.

---

## CSV schema

`data/events.csv` and `data/ptsa_events.csv` share the same columns:

```
date,start_date,end_date,type,scope,label,notes
```

- Use **either** `date` (single-day) **or** `start_date`+`end_date` (inclusive range). ISO format (`YYYY-MM-DD`).
- `type` is a short token used for coloring/legend (e.g., `no_school`, `half_day`, `first_day`, `last_day`, `early_release`, `conf_elem`, etc.).
- `scope` is `district` or `ptsa`. Data from `ptsa_events.csv` is automatically tagged `ptsa` if the column is left blank.
- `label` is what appears in the Important Dates list.
- `notes` are optional and can show in the Important Dates.

Examples in `data/*.csv` are placeholders—replace with your 2025–26 dates.

---

## Theming

Edit `styles/calendar.css` and `templates/calendar.html` to adjust layout, fonts, and colors. Update the legend map & color tokens inside `build.py` if you add new `type`s.

---

## GitHub Actions (optional)

The provided workflow (`.github/workflows/build.yml`) builds the PDF on every push to `main` and uploads it as a CI artifact. You can extend this to push to GitHub Pages or attach to a Release.

---

## License

MIT
