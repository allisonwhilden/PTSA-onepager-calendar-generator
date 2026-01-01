// Event types matching Python build.py TYPE_NORMALIZATION
export type EventType =
  | 'no_school'
  | 'half_day'
  | 'ptsa_event'
  | 'first_day'
  | 'last_day'
  | 'early_release'
  | 'closure_possible';

// Calendar event - matches CSV format
export interface CalendarEvent {
  id: string;
  date?: string;           // Single day (YYYY-MM-DD)
  startDate?: string;      // Range start (YYYY-MM-DD)
  endDate?: string;        // Range end (YYYY-MM-DD)
  type: EventType;
  label: string;
  notes?: string;
  createdAt: string;
  updatedAt: string;
}

// Events store structure
export interface EventsStore {
  schoolYear: number;      // Starting year (e.g., 2025 for 2025-26)
  events: CalendarEvent[];
  lastModified: string;
}

// School year configuration
export interface SchoolYearConfig {
  earlyReleaseStart: string;  // YYYY-MM-DD
  schoolYearEnd: string;      // YYYY-MM-DD
  specialDiamondDays: string[]; // Array of YYYY-MM-DD
}

// Cell for calendar grid rendering
export interface CalendarCell {
  day: number;
  date: Date;
  marks: EventType[];
  isWeekend: boolean;
  hasDiamond: boolean;
  hasCircle: boolean;
  showAsterisk: boolean;
}

// Month data for rendering
export interface MonthData {
  name: string;
  year: number;
  month: number; // 0-11
  cells: (CalendarCell | null)[];
}

// Important date for the sidebar list
export interface ImportantDate {
  when: string;
  label: string;
  notes?: string;
  isPtsa: boolean;
  sortDate: Date;
}

// Event type display configuration
export const EVENT_TYPE_CONFIG: Record<EventType, {
  label: string;
  color: string;
  bgColor: string;
}> = {
  no_school: {
    label: 'No School',
    color: '#ffffff',
    bgColor: '#000000',
  },
  half_day: {
    label: 'Half Day',
    color: '#000000',
    bgColor: '#cccccc',
  },
  ptsa_event: {
    label: 'PTSA Event',
    color: '#C40A0C',
    bgColor: 'transparent',
  },
  first_day: {
    label: 'First Day',
    color: '#000000',
    bgColor: 'transparent',
  },
  last_day: {
    label: 'Last Day',
    color: '#000000',
    bgColor: 'transparent',
  },
  early_release: {
    label: 'Early Release',
    color: '#000000',
    bgColor: 'transparent',
  },
  closure_possible: {
    label: 'Make-up Day',
    color: '#000000',
    bgColor: '#d9d9d9',
  },
};

// Type normalization mapping (matches Python)
export const TYPE_NORMALIZATION: Record<string, EventType> = {
  no_school: 'no_school',
  half_day: 'half_day',
  first_day: 'first_day',
  last_day: 'last_day',
  early_release: 'early_release',
  ptsa_event: 'ptsa_event',
  closure_possible: 'closure_possible',
  // Aliases
  first_day_1_12: 'first_day',
  first_day_k: 'first_day',
  holiday: 'no_school',
  closure_day: 'closure_possible',
  possible_school_day: 'closure_possible',
  potential_school_day: 'closure_possible',
  // Additional types from CSV (map to closest equivalent)
  kinder_family_conn: 'half_day',
  grades_due: 'no_school', // Skip these - they're informational, not calendar marks
};
