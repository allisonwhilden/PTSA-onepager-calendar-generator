import { NextResponse } from 'next/server';
import { getEvents } from '@/lib/storage/events';
import { eventsToCSV } from '@/lib/csv/parser';

// GET /api/export - Export events as CSV
export async function GET() {
  try {
    const store = await getEvents();
    const csv = eventsToCSV(store.events);

    return new NextResponse(csv, {
      headers: {
        'Content-Type': 'text/csv',
        'Content-Disposition': `attachment; filename="calendar-events-${store.schoolYear}.csv"`,
      },
    });
  } catch (error) {
    console.error('Error exporting events:', error);
    return NextResponse.json(
      { error: 'Failed to export events' },
      { status: 500 }
    );
  }
}
