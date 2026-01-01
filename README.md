# Horace Mann PTSA Calendar Generator

A one-page PDF calendar generator for the 2025-26 school year that combines Lake Washington School District (LWSD) dates with PTSA-specific events. Creates a compact, print-ready Letter-size calendar using Python, Jinja2, and WeasyPrint.

## Live Calendar

📅 **[View Current Calendar](https://allisonwhilden.github.io/PTSA-onepager-calendar-generator/)**  
📄 **[Direct PDF Download](https://allisonwhilden.github.io/PTSA-onepager-calendar-generator/calendar.pdf)**

## Features

- **Single-page PDF** optimized for Letter-size printing
- **Full school year** coverage (September 2025 - August 2026)
- **Visual event indicators**:
  - 🟥 Black background = No school days
  - 🔲 Grey background = Half days  
  - ⭕ Red circles = PTSA events
  - ⬜ Square boxes = First/Last days
  - **Bold** = Early release Wednesdays
- **Automatic date consolidation** (e.g., "12/22-1/2" for Winter Break)
- **PTSA branding** with red theme (#C40A0C)

## Quick Start

### 1. Install System Dependencies

WeasyPrint requires system-level libraries:

**macOS (Homebrew):**
```bash
brew install pygobject3 cairo pango gdk-pixbuf libffi
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y python3-dev python3-pip libcairo2 libpango-1.0-0 \
  libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info
```

### 2. Setup Python Environment

```bash
# Create and activate virtual environment (REQUIRED)
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\activate      # Windows

# Install Python dependencies
pip install -r requirements.txt
```

### 3. Edit Event Data

Modify the CSV file in the `data/` directory:
- `data/all_events.csv` - Combined file with all LWSD district dates and PTSA events (57 total events)

### 4. Generate Calendar

```bash
# Build the PDF
python build.py --year 2025 --data data/all_events.csv --out build/HoraceMann-PTSA-2025-26-Calendar.pdf

# Open the result (macOS)
open build/HoraceMann-PTSA-2025-26-Calendar.pdf
```

## CSV Data Format

The event file uses this schema:

```csv
date,start_date,end_date,type,label,notes
2025-09-02,,,first_day,First Day (Grades 1-12),
,2025-12-22,2026-01-02,no_school,Winter Break,
2025-10-10,,,ptsa_event,Picture Day,
```

- Use `date` for single-day events OR `start_date`+`end_date` for ranges
- `type` determines visual styling and event category (no_school, half_day, ptsa_event, first_day, etc.)
- `label` appears in the Important Dates section

## Customization

### Styling
Edit `styles/calendar.css` to modify:
- Colors and themes
- Font sizes and spacing
- Page margins (currently 8pt for maximum content)

### Templates
Modify `templates/calendar.html` to change:
- Header text and branding
- Layout structure
- Legend entries

### Event Types
Add new event types in `build.py`:
- Update `TYPE_NORMALIZATION` dictionary
- Add corresponding CSS classes

## Automatic Deployment

The included GitHub Actions workflow automatically:
1. Builds the PDF on every push to `main`
2. Deploys to GitHub Pages for easy sharing
3. Creates a web viewer with download button

After pushing changes, your calendar will be available at:
- `https://[your-username].github.io/[repo-name]/calendar.pdf`

## Project Structure

```
├── build.py                 # Main generator script
├── data/
│   └── all_events.csv      # Combined LWSD district and PTSA events
├── templates/
│   ├── base.html           # HTML structure
│   └── calendar.html       # Calendar layout
├── styles/
│   └── calendar.css        # All styling
└── .github/
    └── workflows/
        └── build-and-deploy.yml  # CI/CD automation
```

## Notes

- Early release Wednesdays are automatically marked starting Sept 10, 2025
- Preschool events have been removed from district data
- Virtual environment activation is REQUIRED for WeasyPrint to work
- The calendar fits on a single Letter-size page when printed

## License

MIT