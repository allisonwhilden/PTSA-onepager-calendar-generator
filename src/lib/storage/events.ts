import { put, head, del } from '@vercel/blob';
import { EventsStore, CalendarEvent } from '../calendar/types';

const BLOB_FILENAME = 'events.json';

// Default empty store
function createEmptyStore(schoolYear: number = 2025): EventsStore {
  return {
    schoolYear,
    events: [],
    lastModified: new Date().toISOString(),
  };
}

// Read events from Vercel Blob
export async function getEvents(): Promise<EventsStore> {
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

// Save events to Vercel Blob
export async function saveEvents(store: EventsStore): Promise<void> {
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
