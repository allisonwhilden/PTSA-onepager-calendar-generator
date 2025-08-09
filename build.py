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
    # aliases
    "first_day_1_12": "first_day",
    "first_day_k": "first_day",
    "holiday": "no_school",
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
            # normalize type/scope
            t = row.get("type") or ""
            row["type"] = TYPE_NORMALIZATION.get(t, t)
            s = row.get("scope") or ""
            if "ptsa" in csv_path and not s:
                s = "ptsa"
            row["scope"] = s or "district"
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
    for d, row in expanded:
        # School years can straddle new year; we include any months that match the target school year's months.
        # We'll construct months list externally; here we just collect.
        key = (d.year, d.month)
        buckets.setdefault(key, {}).setdefault(d.day, []).append(row["type"] or "ptsa_event")
    return buckets

def school_year_months(year_start):
    """Return a list of (year, month) covering Sep..Jun for a given starting calendar year (ex: 2025 => Sep 2025..Jun 2026)."""
    seq = []
    for m in range(9, 13):  # Sep..Dec
        seq.append((year_start, m))
    for m in range(1, 7):   # Jan..Jun
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
        marks = marks_for_day.get(d, [])
        # collapse first/last into a single style token if needed
        style_marks = []
        for t in marks:
            if t in ("first_day", "last_day"):
                style_marks.append(t)
            elif t in ("no_school", "half_day", "early_release", "ptsa_event"):
                style_marks.append(t)
        style_marks = list(dict.fromkeys(style_marks))  # dedupe preserving order
        cells.append(type("Cell", (), {"day": d, "marks": style_marks}))
    while len(cells) % 7 != 0:
        cells.append("")
    # Ensure 6 rows (42 cells)
    while len(cells) < 42:
        cells.append("")
    return cells

def format_important_dates(expanded, months_span):
    """Return a sorted list of human-readable events within the months span for the Important Dates column."""
    span_set = set(months_span)
    items = {}
    for d, row in expanded:
        key = (d.year, d.month)
        if key not in span_set:
            continue
        label = row.get("label") or row.get("type")
        notes = row.get("notes") or ""
        items.setdefault((d, label, notes), True)
    # sort by date then label
    result = [{"when": d.strftime("%b %-d, %Y") if os.name != "nt" else d.strftime("%b %#d, %Y"),
               "label": label,
               "notes": notes} for (d, label, notes) in sorted(items.keys(), key=lambda x: (x[0], x[1]))]
    return result

def build_context(year_start, events_paths):
    rows = []
    for p in events_paths:
        rows.extend(read_events(p))
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
        "title": f"{year_start}-{(year_start+1)%100:02d} One-Page Calendar",
        "header": {
            "title": f"{year_start}-{(year_start+1)%100:02d} School Year — One-Page Calendar",
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
    parser.add_argument("--data", type=str, nargs="*", default=["data/events.csv", "data/ptsa_events.csv"])
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
