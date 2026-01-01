# PTSA Calendar Web UI

A web-based calendar editor for the Horace Mann PTSA school calendar.

## Features

- **Interactive Calendar Grid**: 3x4 month layout showing the full school year
- **Event Management**: Add, edit, and delete events by clicking on days
- **Visual Markers**: No school (black), half day (grey), early release (bold), PTSA events (circle), first/last days (diamond)
- **PDF Generation**: Download the calendar as a PDF directly from the browser
- **CSV Import/Export**: Import events from CSV (replace or append modes) and export current events
- **Clear All**: Reset all events with confirmation

## Getting Started

### Development

```bash
# Install dependencies
pnpm install

# Run development server
pnpm dev

# Open http://localhost:3000
```

### Production Build

```bash
# Build for production
pnpm build

# Start production server
pnpm start
```

## Event Types

| Type | Display | Description |
|------|---------|-------------|
| `no_school` | Black background | No school day |
| `half_day` | Grey background | Half day schedule |
| `ptsa_event` | Red circle | PTSA event |
| `first_day` | Diamond | First day of school |
| `last_day` | Diamond | Last day of school |
| `early_release` | Bold text | Early release (auto-marked on Wednesdays) |
| `closure_possible` | Light grey | Potential make-up day |

## CSV Format

The CSV file should have the following columns:

```csv
date,start_date,end_date,type,label,notes
2025-09-02,,,first_day,First Day (Grades 1-12),
,2025-12-22,2026-01-02,no_school,Winter Break,
2025-10-10,,,ptsa_event,Picture Day,
```

- Use `date` for single-day events
- Use `start_date` and `end_date` for date ranges
- `type` must match one of the event types listed above
- `notes` is optional

## Data Storage

Events are stored in `data/events.json`. This file is automatically created when you add your first event.

**Note**: For Vercel deployment, you'll need to configure Vercel Blob or KV for persistent storage, as the serverless filesystem is read-only.

## Tech Stack

- **Framework**: Next.js 14+ (App Router)
- **Styling**: Tailwind CSS + shadcn/ui
- **PDF Generation**: @react-pdf/renderer
- **Storage**: JSON file (local) / Vercel Blob (production)

## Related Files

- Original Python generator: `python/build.py`
- Original CSS styles: `python/styles/calendar.css`
- Original HTML template: `python/templates/calendar.html`
