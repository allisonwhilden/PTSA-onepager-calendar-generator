'use client';

import { CalendarEvent, EVENT_TYPE_CONFIG } from '@/lib/calendar/types';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

interface EventListProps {
  events: CalendarEvent[];
  onEdit: (event: CalendarEvent) => void;
  onDelete: (eventId: string) => void;
}

export function EventList({ events, onEdit, onDelete }: EventListProps) {
  // Sort events by date
  const sortedEvents = [...events].sort((a, b) => {
    const dateA = a.date || a.startDate || '';
    const dateB = b.date || b.startDate || '';
    return dateA.localeCompare(dateB);
  });

  if (events.length === 0) {
    return (
      <div className="rounded-lg border bg-white p-4 text-center text-gray-500">
        No events yet. Click on a day to add one.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {sortedEvents.map((event) => (
        <EventCard
          key={event.id}
          event={event}
          onEdit={() => onEdit(event)}
          onDelete={() => onDelete(event.id)}
        />
      ))}
    </div>
  );
}

interface EventCardProps {
  event: CalendarEvent;
  onEdit: () => void;
  onDelete: () => void;
}

function EventCard({ event, onEdit, onDelete }: EventCardProps) {
  const typeConfig = EVENT_TYPE_CONFIG[event.type];
  const dateDisplay = event.date
    ? formatDisplayDate(event.date)
    : `${formatDisplayDate(event.startDate!)} - ${formatDisplayDate(event.endDate!)}`;

  return (
    <div className="flex items-center justify-between rounded-lg border bg-white p-3">
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <Badge
            style={{
              backgroundColor: typeConfig.bgColor === 'transparent' ? '#f3f4f6' : typeConfig.bgColor,
              color: typeConfig.color,
            }}
          >
            {typeConfig.label}
          </Badge>
          <span className="text-sm text-gray-500">{dateDisplay}</span>
        </div>
        <p className="mt-1 font-medium">{event.label}</p>
        {event.notes && (
          <p className="mt-0.5 text-sm text-gray-600">{event.notes}</p>
        )}
      </div>
      <div className="flex gap-1">
        <Button variant="outline" size="sm" onClick={onEdit}>
          Edit
        </Button>
        <Button variant="destructive" size="sm" onClick={onDelete}>
          Delete
        </Button>
      </div>
    </div>
  );
}

function formatDisplayDate(dateStr: string): string {
  const [year, month, day] = dateStr.split('-');
  return `${parseInt(month)}/${parseInt(day)}`;
}
