import { put, head, del } from '@vercel/blob';
import { EventsStore, CalendarEvent } from '../calendar/types';
import { promises as fs } from 'fs';
import path from 'path';

const BLOB_FILENAME = 'events.json';
const LOCAL_STORAGE_PATH = path.join(process.cwd(), '.local-events.json');

// Check if we should use local storage (no Vercel Blob token)
const USE_LOCAL_STORAGE = !process.env.BLOB_READ_WRITE_TOKEN;

// Default empty store
function createEmptyStore(schoolYear: number = 2025): EventsStore {
  return {
    schoolYear,
    events: [],
    lastModified: new Date().toISOString(),
  };
}

// Local storage functions for development
async function getLocalEvents(): Promise<EventsStore> {
  try {
    const data = await fs.readFile(LOCAL_STORAGE_PATH, 'utf-8');
    return JSON.parse(data) as EventsStore;
  } catch {
    return createEmptyStore();
  }
}

async function saveLocalEvents(store: EventsStore): Promise<void> {
  store.lastModified = new Date().toISOString();
  await fs.writeFile(LOCAL_STORAGE_PATH, JSON.stringify(store, null, 2));
}

// Read events from Vercel Blob or local storage
export async function getEvents(): Promise<EventsStore> {
  if (USE_LOCAL_STORAGE) {
    return getLocalEvents();
  }

  try {
    // Check if blob exists
    const blobInfo = await head(BLOB_FILENAME).catch(() => null);

    if (!blobInfo) {
      return createEmptyStore();
    }

    // Fetch the blob content
    const response = await fetch(blobInfo.url);
    if (!response.ok) {
      return createEmptyStore();
    }

    const data = await response.json();
    return data as EventsStore;
  } catch (error) {
    console.error('Error reading events from blob:', error);
    return createEmptyStore();
  }
}

// Save events to Vercel Blob or local storage
export async function saveEvents(store: EventsStore): Promise<void> {
  if (USE_LOCAL_STORAGE) {
    return saveLocalEvents(store);
  }

  store.lastModified = new Date().toISOString();

  // Delete old blob if exists (Vercel Blob doesn't support overwrite)
  try {
    const blobInfo = await head(BLOB_FILENAME).catch(() => null);
    if (blobInfo) {
      await del(blobInfo.url);
    }
  } catch {
    // Ignore delete errors
  }

  // Upload new blob
  await put(BLOB_FILENAME, JSON.stringify(store, null, 2), {
    access: 'public',
    addRandomSuffix: false,
  });
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
