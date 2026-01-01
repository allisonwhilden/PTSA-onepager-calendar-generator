import { CalendarEvent, EventType, TYPE_NORMALIZATION } from '../calendar/types';
import { generateId } from '../calendar/utils';

// CSV header fields
const CSV_HEADERS = ['date', 'start_date', 'end_date', 'type', 'label', 'notes'];

// Parse CSV string to events array
export function parseCSV(csvContent: string): CalendarEvent[] {
  const lines = csvContent.trim().split('\n');
  if (lines.length < 2) {
    throw new Error('CSV must have at least a header row and one data row');
  }

  // Validate header
  const headerLine = lines[0].trim();
  const headers = parseCSVLine(headerLine);

  // Map header names to indices
  const headerMap: Record<string, number> = {};
  headers.forEach((header, index) => {
    headerMap[header.toLowerCase().trim()] = index;
  });

  // Check required headers
  if (headerMap['type'] === undefined || headerMap['label'] === undefined) {
    throw new Error('CSV must have "type" and "label" columns');
  }

  const events: CalendarEvent[] = [];
  const now = new Date().toISOString();

  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;

    const values = parseCSVLine(line);

    const date = values[headerMap['date']]?.trim() || '';
    const startDate = values[headerMap['start_date']]?.trim() || '';
    const endDate = values[headerMap['end_date']]?.trim() || '';
    const rawType = values[headerMap['type']]?.trim() || '';
    const label = values[headerMap['label']]?.trim() || '';
    const notes = values[headerMap['notes']]?.trim() || '';

    if (!label) continue; // Skip rows without labels

    // Normalize event type
    const type = normalizeEventType(rawType);
    if (!type) {
      console.warn(`Skipping row ${i + 1}: unknown type "${rawType}"`);
      continue;
    }

    const event: CalendarEvent = {
      id: generateId(),
      type,
      label,
      createdAt: now,
      updatedAt: now,
    };

    if (date) {
      event.date = date;
    } else if (startDate && endDate) {
      event.startDate = startDate;
      event.endDate = endDate;
    } else {
      console.warn(`Skipping row ${i + 1}: no date or date range specified`);
      continue;
    }

    if (notes) {
      event.notes = notes;
    }

    events.push(event);
  }

  return events;
}

// Parse a single CSV line, handling quoted values
function parseCSVLine(line: string): string[] {
  const values: string[] = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    const nextChar = line[i + 1];

    if (inQuotes) {
      if (char === '"' && nextChar === '"') {
        current += '"';
        i++; // Skip next quote
      } else if (char === '"') {
        inQuotes = false;
      } else {
        current += char;
      }
    } else {
      if (char === '"') {
        inQuotes = true;
      } else if (char === ',') {
        values.push(current);
        current = '';
      } else {
        current += char;
      }
    }
  }

  values.push(current);
  return values;
}

// Normalize event type using TYPE_NORMALIZATION mapping
function normalizeEventType(rawType: string): EventType | null {
  const normalized = rawType.toLowerCase().trim();
  return TYPE_NORMALIZATION[normalized] || null;
}

// Convert events to CSV string
export function eventsToCSV(events: CalendarEvent[]): string {
  const lines: string[] = [];

  // Header
  lines.push(CSV_HEADERS.join(','));

  // Data rows
  for (const event of events) {
    const row = [
      event.date || '',
      event.startDate || '',
      event.endDate || '',
      event.type,
      escapeCSVValue(event.label),
      escapeCSVValue(event.notes || ''),
    ];
    lines.push(row.join(','));
  }

  return lines.join('\n');
}

// Escape a value for CSV (quote if contains comma, quote, or newline)
function escapeCSVValue(value: string): string {
  if (value.includes(',') || value.includes('"') || value.includes('\n')) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}
