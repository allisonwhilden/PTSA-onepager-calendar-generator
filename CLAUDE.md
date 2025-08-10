# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Horace Mann PTSA Calendar Generator - A one-page PDF calendar generator for the 2025-26 school year that combines Lake Washington School District (LWSD) dates with PTSA-specific events. Built with Python, Jinja2 templates, and WeasyPrint to generate a compact, print-ready Letter-size calendar.

## Key Features

- **Single-page PDF** optimized for Letter-size printing
- **3x4 month grid** layout (September through June + July/August)
- **Visual event marking system**:
  - Black background: No school days
  - Grey background (#ccc): Half days
  - Bold text: Early release Wednesdays (auto-marked starting Sept 10, 2025)
  - Square boxes: First/Last days (Sept 2, Sept 5, June 17)
  - Red circles (#C40A0C): PTSA events
  - Grey text: Weekend days
- **Two-column Important Dates** section with date range consolidation
- **PTSA branding**: Red header bar with "Horace Mann PTSA | 2025-26 Calendar"
- **Automatic deployment** to GitHub Pages for easy sharing

## Development Commands

### Setup Environment
```bash
# Create and activate virtual environment (REQUIRED)
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### Build Calendar
```bash
# Always activate venv first!
source .venv/bin/activate

# Generate PDF for 2025-26 school year
python build.py --year 2025 --out build/LWSD-2025-26-onepage.pdf

# Open the generated PDF (macOS)
open build/LWSD-2025-26-onepage.pdf
```

## Architecture

### Core Components

1. **build.py**: Main generator script with key enhancements:
   - Date range consolidation for Important Dates (e.g., "12/22-1/2" for Winter Break)
   - Automatic early release Wednesday marking (starting Sept 10, 2025)
   - Special diamond/circle marking for specific dates
   - PTSA event differentiation with "PTSA:" prefix
   - Removal of leading zeros from dates for cleaner display

2. **Data Files**:
   - `data/events.csv`: 37 LWSD district dates (after preschool removal)
   - `data/ptsa_events.csv`: 22 PTSA-specific events
   - Both files use same CSV schema (see below)

3. **Visual Styling** (`styles/calendar.css`):
   - Red theme (#C40A0C) for PTSA branding
   - Optimized spacing for single-page fit (8pt margins, 14pt cell height)
   - District events in Important Dates: grey text (#555) on light grey background
   - PTSA events in Important Dates: red text (#C40A0C)

### Data Schema

CSV format for both event files:
```csv
date,start_date,end_date,type,scope,label,notes
2025-09-02,,,first_day_1_12,district,First Day (Grades 1-12),
,2025-12-22,2026-01-02,no_school,district,Winter Break,
2025-10-10,,,ptsa_event,ptsa,Fall Carnival,5-7pm
```

### Key Functions in build.py

- `bucket_by_month()`: Enhanced to auto-mark early release Wednesdays
- `consolidated_important_dates()`: New function for date range formatting
- `generate_calendar_months()`: Adds diamond/circle marking logic
- `format_important_dates()`: Sorts and prefixes PTSA events

### Template Enhancements

- Red header bar with PTSA branding
- Square/circle visual indicators in calendar cells
- Two-column Important Dates with background differentiation
- Updated Key section with all event type explanations

## System Dependencies

WeasyPrint requires system-level libraries:
- macOS: `brew install pygobject3 cairo pango gdk-pixbuf libffi`
- Ubuntu/Debian: `sudo apt-get install -y python3-dev python3-pip libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info`

## CI/CD & Deployment

### GitHub Actions Workflow
`.github/workflows/build-and-deploy.yml` automatically:
1. Builds PDF on push to main
2. Deploys to GitHub Pages (gh-pages branch)
3. Creates web viewer with embedded PDF

### Access Published Calendar
- Direct PDF: `https://allisonwhilden.github.io/PTSA-onepager-calendar-generator/calendar.pdf`
- Web viewer: `https://allisonwhilden.github.io/PTSA-onepager-calendar-generator/`

Note: Enable GitHub Pages in repo settings (Settings → Pages → Source: gh-pages)

## Testing & Debugging

```bash
# Run linting/type checking if available
npm run lint      # If configured
npm run typecheck # If configured

# Generate debug HTML without PDF conversion
python debug_html.py  # Creates build/debug.html for inspection
```

## Project-Specific Notes

- **Virtual environment is REQUIRED** - WeasyPrint won't work without it
- Calendar covers September 2025 through August 2026
- Preschool events have been removed from district data
- Early release Wednesdays are automatically marked starting Sept 10, 2025
- Date ranges in Important Dates are consolidated to save space
- PTSA events are visually distinct with red coloring throughout