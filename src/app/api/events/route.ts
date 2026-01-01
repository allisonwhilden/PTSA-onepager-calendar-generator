import { NextRequest, NextResponse } from 'next/server';
import {
  getEvents,
  addEvent,
  updateEvent,
  deleteEvent,
  clearEvents,
  replaceEvents,
  appendEvents,
} from '@/lib/storage/events';
import { CalendarEvent } from '@/lib/calendar/types';
import { generateId } from '@/lib/calendar/utils';

// GET /api/events - Get all events
export async function GET() {
  try {
    const store = await getEvents();
    return NextResponse.json(store);
  } catch (error) {
    console.error('Error fetching events:', error);
    return NextResponse.json(
      { error: 'Failed to fetch events' },
      { status: 500 }
    );
  }
}

// POST /api/events - Add event(s) or perform bulk operations
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const action = body.action || 'add';

    switch (action) {
      case 'add': {
        // Add a single event
        const now = new Date().toISOString();
        const event: CalendarEvent = {
          id: generateId(),
          ...body.event,
          createdAt: now,
          updatedAt: now,
        };
        const store = await addEvent(event);
        return NextResponse.json({ store, event });
      }

      case 'clear': {
        // Clear all events
        const store = await clearEvents();
        return NextResponse.json({ store });
      }

      case 'replace': {
        // Replace all events (CSV import replace mode)
        const now = new Date().toISOString();
        const events: CalendarEvent[] = (body.events || []).map((e: Partial<CalendarEvent>) => ({
          id: e.id || generateId(),
          ...e,
          createdAt: e.createdAt || now,
          updatedAt: now,
        }));
        const store = await replaceEvents(events, body.schoolYear);
        return NextResponse.json({ store });
      }

      case 'append': {
        // Append events (CSV import append mode)
        const now = new Date().toISOString();
        const events: CalendarEvent[] = (body.events || []).map((e: Partial<CalendarEvent>) => ({
          id: generateId(),
          ...e,
          createdAt: now,
          updatedAt: now,
        }));
        const store = await appendEvents(events);
        return NextResponse.json({ store });
      }

      default:
        return NextResponse.json(
          { error: `Unknown action: ${action}` },
          { status: 400 }
        );
    }
  } catch (error) {
    console.error('Error processing events:', error);
    return NextResponse.json(
      { error: 'Failed to process events' },
      { status: 500 }
    );
  }
}

// PUT /api/events - Update an event
export async function PUT(request: NextRequest) {
  try {
    const body = await request.json();
    const { id, ...updates } = body;

    if (!id) {
      return NextResponse.json(
        { error: 'Event id is required' },
        { status: 400 }
      );
    }

    const store = await updateEvent(id, updates);
    return NextResponse.json({ store });
  } catch (error) {
    console.error('Error updating event:', error);
    if ((error as Error).message.includes('not found')) {
      return NextResponse.json(
        { error: (error as Error).message },
        { status: 404 }
      );
    }
    return NextResponse.json(
      { error: 'Failed to update event' },
      { status: 500 }
    );
  }
}

// DELETE /api/events - Delete an event
export async function DELETE(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const id = searchParams.get('id');

    if (!id) {
      return NextResponse.json(
        { error: 'Event id is required' },
        { status: 400 }
      );
    }

    const store = await deleteEvent(id);
    return NextResponse.json({ store });
  } catch (error) {
    console.error('Error deleting event:', error);
    return NextResponse.json(
      { error: 'Failed to delete event' },
      { status: 500 }
    );
  }
}
