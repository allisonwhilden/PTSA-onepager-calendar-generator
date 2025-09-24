import argparse, csv, datetime as dt, calendar, os, pathlib
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

# ---- Configurable legend/type mapping (CSS classes live in styles/calendar.css) ----
TYPE_NORMALIZATION = {
    "no_school": "no_school",
    "half_day": "half_day",
    "first_day": "first_day",
    "last_day": "last_day",
    "early_release": "early_release",
    "ptsa_event": "ptsa_event",
    "closure_possible": "closure_possible",
    # aliases
    "first_day_1_12": "first_day",
    "first_day_k": "first_day",
    "holiday": "no_school",
    # common alias names users might try
    "closure_day": "closure_possible",
    "possible_school_day": "closure_possible",
    "potential_school_day": "closure_possible",
}

MONTH_NAMES = [calendar.month_name[i] for i in range(13)]

def read_events(csv_path):
    rows = []
    if not pathlib.Path(csv_path).exists():
        return rows
    with open(csv_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for raw in r:
            row = {k: (v.strip() if isinstance(v, str) else v) for k,v in raw.items()}
            # normalize type
            t = row.get("type") or ""
            row["type"] = TYPE_NORMALIZATION.get(t, t)
            rows.append(row)
    return rows

def daterange(start, end):
    d = start
    while d <= end:
        yield d
        d += dt.timedelta(days=1)

def parse_date(s):
    if not s:
        return None
    return dt.datetime.strptime(s, "%Y-%m-%d").date()

def expand_events(rows):
    """Expand single-day and ranged events to a list of (date, row) tuples."""
    expanded = []
    for row in rows:
        date = parse_date(row.get("date"))
        start = parse_date(row.get("start_date"))
        end = parse_date(row.get("end_date"))
        if date:
            expanded.append((date, row))
        elif start and end:
            for d in daterange(start, end):
                expanded.append((d, row))
        else:
            # ignore rows without valid dates
            pass
    return expanded

def bucket_by_month(expanded, year):
    """Return { (year, month) : {day:int -> [types]} } for the given school year span (Aug/Sept .. Jun)"""
    buckets = {}
    
    # First collect all events from the data
    for d, row in expanded:
        key = (d.year, d.month)
        buckets.setdefault(key, {}).setdefault(d.day, []).append(row["type"] or "ptsa_event")
    
    # Now add early_release to all Wednesdays starting Sept 10, 2025 through end of school year
    # unless they're already marked as no_school or half_day
    early_release_start = dt.date(2025, 9, 10)
    school_year_end = dt.date(2026, 6, 17)  # Last day of school
    
    current = early_release_start
    while current <= school_year_end:
        if current.weekday() == 2:  # Wednesday = 2
            key = (current.year, current.month)
            day_marks = buckets.setdefault(key, {}).setdefault(current.day, [])
            # Only add early_release if it's not a no_school or half_day
            if "no_school" not in day_marks and "half_day" not in day_marks:
                if "early_release" not in day_marks:
                    day_marks.append("early_release")
        current += dt.timedelta(days=7)  # Move to next Wednesday
    
    return buckets

def school_year_months(year_start):
    """Return a list of (year, month) covering Aug..Jul for a given starting calendar year."""
    seq = []
    # Start with August of the starting year
    seq.append((year_start, 8))  # August
    for m in range(9, 13):  # Sep..Dec
        seq.append((year_start, m))
    for m in range(1, 8):   # Jan..Jul
        seq.append((year_start + 1, m))
    return seq

def make_month_cells(year, month, marks_for_day):
    """Return a list of 42 cells (7x6) with blanks before 1st and after last day; each day is a dict {day, marks[]}"""
    first_wd, num_days = calendar.monthrange(year, month)  # first_wd: Mon=0..Sun=6
    # We want Su..Sa, so compute leading blanks accordingly
    # Convert Mon=0..Sun=6 to Sun=0..Sat=6 "index of first day"
    sun_first_index = (first_wd + 1) % 7  # if Mon(0) -> 1, ..., Sun(6) -> 0
    cells = []
    for _ in range(sun_first_index):
        cells.append("")
    for d in range(1, num_days + 1):
        # Calculate day of week for this date
        date_obj = dt.date(year, month, d)
        day_of_week = date_obj.weekday()  # Mon=0, Sun=6
        is_weekend = day_of_week in (5, 6)  # Saturday=5, Sunday=6
        
        # Check if this is one of the three special diamond days
        has_diamond = False
        if (year == 2025 and month == 9 and d in [2, 5]) or (year == 2026 and month == 6 and d == 17):
            has_diamond = True
        
        marks = marks_for_day.get(d, [])
        # Check if this day has a PTSA event
        has_circle = "ptsa_event" in marks
        
        # collapse first/last into a single style token if needed
        style_marks = []
        for t in marks:
            if t in ("first_day", "last_day", "first_day_1_12", "first_day_k"):
                style_marks.append(t)
            elif t in ("no_school", "half_day", "early_release", "ptsa_event", "closure_possible"):
                style_marks.append(t)
        style_marks = list(dict.fromkeys(style_marks))  # dedupe preserving order
        cells.append(type("Cell", (), {"day": d, "marks": style_marks, "is_weekend": is_weekend, "has_diamond": has_diamond, "has_circle": has_circle}))
    while len(cells) % 7 != 0:
        cells.append("")
    # Ensure 6 rows (42 cells)
    while len(cells) < 42:
        cells.append("")
    return cells

def format_important_dates(expanded, months_span):
    """Return a sorted list of human-readable events within the months span for the Important Dates column."""
    span_set = set(months_span)
    
    # Group events by label and notes to find date ranges
    event_groups = {}
    for d, row in expanded:
        key = (d.year, d.month)
        if key not in span_set:
            continue
        label = row.get("label") or row.get("type")
        notes = row.get("notes") or ""
        event_type = row.get("type") or ""
        event_key = (label, notes, event_type)

        if event_key not in event_groups:
            event_groups[event_key] = []
        event_groups[event_key].append(d)
    
    # Format events with date ranges
    result = []
    for (label, notes, event_type), dates in event_groups.items():
        dates = sorted(dates)
        
        # Check if dates are consecutive
        if len(dates) > 1:
            # Check for consecutive date range
            date_ranges = []
            range_start = dates[0]
            range_end = dates[0]
            
            for i in range(1, len(dates)):
                if (dates[i] - dates[i-1]).days == 1:
                    range_end = dates[i]
                else:
                    # Save current range and start new one
                    if range_start == range_end:
                        date_str = range_start.strftime("%m/%d").lstrip("0").replace("/0", "/")
                        date_ranges.append(date_str)
                    else:
                        start_str = range_start.strftime("%m/%d").lstrip("0").replace("/0", "/")
                        end_str = range_end.strftime("%m/%d").lstrip("0").replace("/0", "/")
                        date_ranges.append(f"{start_str}-{end_str}")
                    range_start = dates[i]
                    range_end = dates[i]
            
            # Add the last range
            if range_start == range_end:
                date_str = range_start.strftime("%m/%d").lstrip("0").replace("/0", "/")
                date_ranges.append(date_str)
            else:
                start_str = range_start.strftime("%m/%d").lstrip("0").replace("/0", "/")
                end_str = range_end.strftime("%m/%d").lstrip("0").replace("/0", "/")
                date_ranges.append(f"{start_str}-{end_str}")
            
            # Create formatted date string
            when_str = ", ".join(date_ranges) if len(date_ranges) > 1 else date_ranges[0]
        else:
            when_str = dates[0].strftime("%m/%d")
        
        # Remove leading zeros from month
        when_str = when_str.lstrip("0").replace("/0", "/")
        
        # Add PTSA prefix for PTSA events
        if event_type == "ptsa_event":
            label = "PTSA: " + label

        result.append({
            "when": when_str,
            "label": label,
            "notes": notes,
            "is_ptsa": event_type == "ptsa_event",
            "sort_date": dates[0]  # For sorting purposes
        })
    
    # Sort by first date of each event
    result.sort(key=lambda x: x["sort_date"])
    
    # Remove sort_date from final result
    for item in result:
        del item["sort_date"]
    
    return result

def build_context(year_start, events_path):
    rows = read_events(events_path)
    expanded = expand_events(rows)
    buckets = bucket_by_month(expanded, year_start)
    months_span = school_year_months(year_start)
    months = []
    for (y, m) in months_span:
        marks_for_day = buckets.get((y, m), {})
        cells = make_month_cells(y, m, marks_for_day)
        months.append({
            "name": MONTH_NAMES[m],
            "year": y,
            "cells": cells,
            "note": ""
        })
    important = format_important_dates(expanded, months_span)

    ctx = {
        "title": f"{year_start}-{(year_start+1)%100:02d} Calendar",
        "header": {
            "title": f"{year_start}-{(year_start+1)%100:02d} Calendar",
            "subtitle": "PTSA + District Dates"
        },
        "months": months,
        "important": important,
        "meta": {
            "generated_at": dt.datetime.now().strftime("%b %d, %Y"),
            "source_note": "Data: CSV (district & PTSA)"
        }
    }
    return ctx

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True, help="Starting calendar year for the school year (e.g., 2025 for 2025–26).")
    parser.add_argument("--out", type=str, default="build/calendar.pdf", help="Output PDF path.")
    parser.add_argument("--template", type=str, default="calendar.html")
    parser.add_argument("--templates_dir", type=str, default="templates")
    parser.add_argument("--styles", type=str, nargs="*", default=["styles/calendar.css"])
    parser.add_argument("--data", type=str, default="data/all_events.csv", help="Path to CSV file with all events")
    args = parser.parse_args()

    ctx = build_context(args.year, args.data)

    env = Environment(
        loader=FileSystemLoader(args.templates_dir),
        autoescape=select_autoescape(['html', 'xml'])
    )
    tpl = env.get_template(args.template)
    html_str = tpl.render(**ctx)

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    HTML(string=html_str, base_url=os.getcwd()).write_pdf(
        target=str(out_path),
    )
    print(f"Wrote {out_path}")

if __name__ == "__main__":
    main()
