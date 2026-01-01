import { promises as fs } from 'fs';
import path from 'path';
import { EventsStore, CalendarEvent } from '../calendar/types';

// Path to events JSON file (in data directory)
const DATA_DIR = path.join(process.cwd(), 'data');
const EVENTS_FILE = path.join(DATA_DIR, 'events.json');

// Default empty store
function createEmptyStore(schoolYear: number = 2025): EventsStore {
  return {
    schoolYear,
    events: [],
    lastModified: new Date().toISOString(),
  };
}

// Ensure data directory exists
async function ensureDataDir(): Promise<void> {
  try {
    await fs.access(DATA_DIR);
  } catch {
    await fs.mkdir(DATA_DIR, { recursive: true });
  }
}

// Read events from JSON file
export async function getEvents(): Promise<EventsStore> {
  try {
    await ensureDataDir();
    const data = await fs.readFile(EVENTS_FILE, 'utf-8');
    return JSON.parse(data) as EventsStore;
  } catch (error) {
    // File doesn't exist, return empty store
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      return createEmptyStore();
    }
    throw error;
  }
}

// Save events to JSON file
export async function saveEvents(store: EventsStore): Promise<void> {
  await ensureDataDir();
  store.lastModified = new Date().toISOString();
  await fs.writeFile(EVENTS_FILE, JSON.stringify(store, null, 2), 'utf-8');
}

// Add a single event
export async function addEvent(event: CalendarEvent): Promise<EventsStore> {
  const store = await getEvents();
  store.events.push(event);
  await saveEvents(store);
  return store;
}

// Update an event by ID
export async function updateEvent(id: string, updates: Partial<CalendarEvent>): Promise<EventsStore> {
  const store = await getEvents();
  const index = store.events.findIndex(e => e.id === id);

  if (index === -1) {
    throw new Error(`Event with id ${id} not found`);
  }

  store.events[index] = {
    ...store.events[index],
    ...updates,
    updatedAt: new Date().toISOString(),
  };

  await saveEvents(store);
  return store;
}

// Delete an event by ID
export async function deleteEvent(id: string): Promise<EventsStore> {
  const store = await getEvents();
  store.events = store.events.filter(e => e.id !== id);
  await saveEvents(store);
  return store;
}

// Clear all events
export async function clearEvents(): Promise<EventsStore> {
  const store = createEmptyStore();
  await saveEvents(store);
  return store;
}

// Replace all events (for CSV import)
export async function replaceEvents(events: CalendarEvent[], schoolYear?: number): Promise<EventsStore> {
  const store: EventsStore = {
    schoolYear: schoolYear ?? 2025,
    events,
    lastModified: new Date().toISOString(),
  };
  await saveEvents(store);
  return store;
}

// Append events (for CSV append import)
export async function appendEvents(newEvents: CalendarEvent[]): Promise<EventsStore> {
  const store = await getEvents();
  store.events.push(...newEvents);
  await saveEvents(store);
  return store;
}
