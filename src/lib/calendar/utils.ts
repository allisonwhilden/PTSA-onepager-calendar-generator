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

// Get the start of the week (Sunday) for a date
export function getWeekStart(date: Date): Date {
  const result = new Date(date);
  const day = result.getDay();
  result.setDate(result.getDate() - day);
  result.setHours(0, 0, 0, 0);
  return result;
}

// Get the end of the week (Saturday) for a date
export function getWeekEnd(date: Date): Date {
  const result = new Date(date);
  const day = result.getDay();
  result.setDate(result.getDate() + (6 - day));
  result.setHours(23, 59, 59, 999);
  return result;
}

// Get event's effective start date
export function getEventStartDate(event: CalendarEvent): string {
  return event.date || event.startDate || '';
}

// Check if event falls within a date range
export function isEventInRange(event: CalendarEvent, start: Date, end: Date): boolean {
  const startStr = formatDate(start);
  const endStr = formatDate(end);

  // Single day event
  if (event.date) {
    return event.date >= startStr && event.date <= endStr;
  }

  // Range event - check if any part overlaps
  if (event.startDate && event.endDate) {
    return event.startDate <= endStr && event.endDate >= startStr;
  }

  return false;
}

// Get upcoming events grouped by time period
export interface UpcomingEventsGroup {
  label: string;
  events: CalendarEvent[];
  startDate: Date;
  endDate: Date;
}

export function getUpcomingEvents(
  events: CalendarEvent[],
  referenceDate: Date = new Date()
): UpcomingEventsGroup[] {
  const groups: UpcomingEventsGroup[] = [];
  const today = new Date(referenceDate);
  today.setHours(0, 0, 0, 0);

  // This Week (rest of current week)
  const thisWeekEnd = getWeekEnd(today);
  const thisWeekEvents = events.filter(e => isEventInRange(e, today, thisWeekEnd));
  if (thisWeekEvents.length > 0) {
    groups.push({
      label: 'This Week',
      events: thisWeekEvents.sort((a, b) => getEventStartDate(a).localeCompare(getEventStartDate(b))),
      startDate: today,
      endDate: thisWeekEnd,
    });
  }

  // Next Week
  const nextWeekStart = new Date(thisWeekEnd);
  nextWeekStart.setDate(nextWeekStart.getDate() + 1);
  nextWeekStart.setHours(0, 0, 0, 0);
  const nextWeekEnd = getWeekEnd(nextWeekStart);
  const nextWeekEvents = events.filter(e => isEventInRange(e, nextWeekStart, nextWeekEnd));
  if (nextWeekEvents.length > 0) {
    groups.push({
      label: 'Next Week',
      events: nextWeekEvents.sort((a, b) => getEventStartDate(a).localeCompare(getEventStartDate(b))),
      startDate: nextWeekStart,
      endDate: nextWeekEnd,
    });
  }

  // Later This Month (rest of current month after next week)
  const laterStart = new Date(nextWeekEnd);
  laterStart.setDate(laterStart.getDate() + 1);
  laterStart.setHours(0, 0, 0, 0);
  const monthEnd = new Date(today.getFullYear(), today.getMonth() + 1, 0);
  monthEnd.setHours(23, 59, 59, 999);

  if (laterStart <= monthEnd) {
    const laterEvents = events.filter(e => isEventInRange(e, laterStart, monthEnd));
    if (laterEvents.length > 0) {
      groups.push({
        label: 'Later This Month',
        events: laterEvents.sort((a, b) => getEventStartDate(a).localeCompare(getEventStartDate(b))),
        startDate: laterStart,
        endDate: monthEnd,
      });
    }
  }

  // Next Month (just to give more context)
  const nextMonthStart = new Date(today.getFullYear(), today.getMonth() + 1, 1);
  const nextMonthEnd = new Date(today.getFullYear(), today.getMonth() + 2, 0);
  nextMonthEnd.setHours(23, 59, 59, 999);
  const nextMonthEvents = events.filter(e => isEventInRange(e, nextMonthStart, nextMonthEnd));
  if (nextMonthEvents.length > 0) {
    const nextMonthName = MONTH_NAMES[nextMonthStart.getMonth()];
    groups.push({
      label: nextMonthName,
      events: nextMonthEvents.sort((a, b) => getEventStartDate(a).localeCompare(getEventStartDate(b))),
      startDate: nextMonthStart,
      endDate: nextMonthEnd,
    });
  }

  return groups;
}

// Group events by month for the "View All" display
export interface MonthEventsGroup {
  year: number;
  month: number;
  label: string;
  events: CalendarEvent[];
}

export function groupEventsByMonth(events: CalendarEvent[]): MonthEventsGroup[] {
  const monthMap = new Map<string, CalendarEvent[]>();

  // Group events by their start date's month
  events.forEach((event) => {
    const dateStr = event.date || event.startDate || '';
    if (!dateStr) return;

    const [year, month] = dateStr.split('-').map(Number);
    const key = `${year}-${String(month).padStart(2, '0')}`;

    if (!monthMap.has(key)) {
      monthMap.set(key, []);
    }
    monthMap.get(key)!.push(event);
  });

  // Convert to array and sort by date
  const groups: MonthEventsGroup[] = [];
  const sortedKeys = Array.from(monthMap.keys()).sort();

  for (const key of sortedKeys) {
    const [year, month] = key.split('-').map(Number);
    const monthEvents = monthMap.get(key)!;

    // Sort events within month by date
    monthEvents.sort((a, b) => {
      const dateA = a.date || a.startDate || '';
      const dateB = b.date || b.startDate || '';
      return dateA.localeCompare(dateB);
    });

    groups.push({
      year,
      month,
      label: `${MONTH_NAMES[month - 1]} ${year}`,
      events: monthEvents,
    });
  }

  return groups;
}
