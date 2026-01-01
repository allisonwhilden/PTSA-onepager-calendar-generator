import { CalendarEvent, CalendarCell, EventType, SchoolYearConfig } from './types';

// Days of week constants
export const WEDNESDAY = 3; // JavaScript: 0=Sun, 3=Wed
export const SATURDAY = 6;
export const SUNDAY = 0;

// Month names
export const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

// Default school year config for 2025-26
export const DEFAULT_SCHOOL_YEAR_CONFIG: SchoolYearConfig = {
  earlyReleaseStart: '2025-09-10',
  schoolYearEnd: '2026-06-17',
  specialDiamondDays: ['2025-09-02', '2025-09-05', '2026-06-17'],
};

// Generate unique ID
export function generateId(): string {
  return Math.random().toString(36).substring(2, 9);
}

// Parse date string to Date object
export function parseDate(dateStr: string): Date {
  const [year, month, day] = dateStr.split('-').map(Number);
  return new Date(year, month - 1, day);
}

// Format date as YYYY-MM-DD
export function formatDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

// Format date as M/D (no leading zeros)
export function formatDateShort(date: Date): string {
  return `${date.getMonth() + 1}/${date.getDate()}`;
}

// Format date range as M/D-M/D
export function formatDateRange(start: Date, end: Date): string {
  if (start.getTime() === end.getTime()) {
    return formatDateShort(start);
  }
  return `${formatDateShort(start)}-${formatDateShort(end)}`;
}

// Generate date range (inclusive)
export function* dateRange(start: Date, end: Date): Generator<Date> {
  const current = new Date(start);
  while (current <= end) {
    yield new Date(current);
    current.setDate(current.getDate() + 1);
  }
}

// Check if date is weekend
export function isWeekend(date: Date): boolean {
  const day = date.getDay();
  return day === SATURDAY || day === SUNDAY;
}

// Check if date is Wednesday
export function isWednesday(date: Date): boolean {
  return date.getDay() === WEDNESDAY;
}

// Expand event to individual dates
export function expandEvent(event: CalendarEvent): Date[] {
  if (event.date) {
    return [parseDate(event.date)];
  }
  if (event.startDate && event.endDate) {
    return [...dateRange(parseDate(event.startDate), parseDate(event.endDate))];
  }
  return [];
}

// Check if event is on a specific date
export function isEventOnDate(event: CalendarEvent, date: Date): boolean {
  const dateStr = formatDate(date);

  if (event.date === dateStr) {
    return true;
  }

  if (event.startDate && event.endDate) {
    return dateStr >= event.startDate && dateStr <= event.endDate;
  }

  return false;
}

// Get events for a specific date
export function getEventsForDate(events: CalendarEvent[], date: Date): CalendarEvent[] {
  return events.filter(event => isEventOnDate(event, date));
}

// Get marks (event types) for a date
export function getMarksForDate(
  events: CalendarEvent[],
  date: Date,
  config: SchoolYearConfig = DEFAULT_SCHOOL_YEAR_CONFIG
): EventType[] {
  const marks: EventType[] = [];
  const dateStr = formatDate(date);

  // Add marks from events
  const dateEvents = getEventsForDate(events, date);
  for (const event of dateEvents) {
    if (!marks.includes(event.type)) {
      marks.push(event.type);
    }
  }

  // Auto-add early release for Wednesdays during school year
  if (isWednesday(date)) {
    if (dateStr >= config.earlyReleaseStart && dateStr <= config.schoolYearEnd) {
      if (!marks.includes('no_school') && !marks.includes('half_day')) {
        if (!marks.includes('early_release')) {
          marks.push('early_release');
        }
      }
    }
  }

  return marks;
}

// Check if date is a special diamond day
export function isDiamondDay(date: Date, config: SchoolYearConfig = DEFAULT_SCHOOL_YEAR_CONFIG): boolean {
  const dateStr = formatDate(date);
  return config.specialDiamondDays.includes(dateStr);
}

// Generate school year months (Aug - Jul)
export function getSchoolYearMonths(startYear: number): Array<{ year: number; month: number }> {
  const months: Array<{ year: number; month: number }> = [];

  // August of start year
  months.push({ year: startYear, month: 7 }); // 7 = August (0-indexed)

  // September - December
  for (let m = 8; m <= 11; m++) {
    months.push({ year: startYear, month: m });
  }

  // January - July of next year
  for (let m = 0; m <= 6; m++) {
    months.push({ year: startYear + 1, month: m });
  }

  return months;
}

// Generate calendar cells for a month
export function generateMonthCells(
  year: number,
  month: number,
  events: CalendarEvent[],
  config: SchoolYearConfig = DEFAULT_SCHOOL_YEAR_CONFIG
): (CalendarCell | null)[] {
  const cells: (CalendarCell | null)[] = [];

  // Get first day of month and number of days
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);
  const numDays = lastDay.getDate();

  // Get starting weekday (0 = Sunday)
  const startWeekday = firstDay.getDay();

  // Add leading empty cells
  for (let i = 0; i < startWeekday; i++) {
    cells.push(null);
  }

  // Add day cells
  for (let day = 1; day <= numDays; day++) {
    const date = new Date(year, month, day);
    const marks = getMarksForDate(events, date, config);
    const hasDiamond = isDiamondDay(date, config);
    const hasCircle = marks.includes('ptsa_event');

    // Determine if asterisk should show
    const showAsterisk = calculateShowAsterisk(marks, hasDiamond, hasCircle);

    cells.push({
      day,
      date,
      marks,
      isWeekend: isWeekend(date),
      hasDiamond,
      hasCircle,
      showAsterisk,
    });
  }

  // Pad to complete grid (6 rows x 7 cols = 42 cells)
  while (cells.length < 42) {
    cells.push(null);
  }

  return cells;
}

// Calculate whether to show asterisk (matches Python logic)
function calculateShowAsterisk(marks: EventType[], hasDiamond: boolean, hasCircle: boolean): boolean {
  // No asterisk if it's a no-school or half day
  if (marks.includes('no_school') || marks.includes('half_day')) {
    // But show asterisk if there are multiple marks and one is early_release
    if (marks.length > 1 && marks.includes('early_release') && !marks.includes('ptsa_event')) {
      return true;
    }
    return false;
  }

  // No asterisk if it's early release only
  if (marks.includes('early_release') && marks.length === 1) {
    return false;
  }

  // Show asterisk for first/last day with diamond/circle
  if (marks.includes('first_day') || marks.includes('last_day')) {
    return hasDiamond || hasCircle;
  }

  // Show asterisk if there are other marks (non-PTSA)
  return marks.length > 0 && !marks.includes('ptsa_event');
}
