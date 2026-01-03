'use client';

import { useMemo } from 'react';
import { CalendarEvent, EVENT_TYPE_CONFIG } from '@/lib/calendar/types';
import { getUpcomingEvents, UpcomingEventsGroup } from '@/lib/calendar/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ChevronRight } from 'lucide-react';

interface ComingUpViewProps {
  events: CalendarEvent[];
  onEventClick?: (event: CalendarEvent) => void;
  onViewAll?: () => void;
}

export function ComingUpView({ events, onEventClick, onViewAll }: ComingUpViewProps) {
  const upcomingGroups = useMemo(() => {
    return getUpcomingEvents(events);
  }, [events]);

  const totalUpcoming = upcomingGroups.reduce((sum, g) => sum + g.events.length, 0);

  if (totalUpcoming === 0) {
    return (
      <div className="rounded-lg border bg-white p-4 text-center">
        <p className="text-gray-500 mb-2">No upcoming events</p>
        {onViewAll && (
          <Button variant="outline" size="sm" onClick={onViewAll}>
            View all events
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-gray-900">Coming Up</h3>
          <p className="text-xs text-gray-500">{totalUpcoming} events</p>
        </div>
        {onViewAll && (
          <Button
            variant="ghost"
            size="sm"
            className="h-8 text-xs text-gray-600"
            onClick={onViewAll}
          >
            View all
            <ChevronRight className="ml-1 h-3 w-3" />
          </Button>
        )}
      </div>

      {/* Event groups */}
      {upcomingGroups.map((group) => (
        <EventGroup
          key={group.label}
          group={group}
          onEventClick={onEventClick}
        />
      ))}
    </div>
  );
}

interface EventGroupProps {
  group: UpcomingEventsGroup;
  onEventClick?: (event: CalendarEvent) => void;
}

function EventGroup({ group, onEventClick }: EventGroupProps) {
  return (
    <div className="space-y-2">
      {/* Group header */}
      <div className="flex items-center gap-2">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
          {group.label}
        </h4>
        <div className="flex-1 border-t border-gray-200" />
        <span className="text-xs text-gray-400">{group.events.length}</span>
      </div>

      {/* Events */}
      <div className="space-y-1.5">
        {group.events.map((event) => (
          <CompactEventCard
            key={event.id}
            event={event}
            onClick={() => onEventClick?.(event)}
          />
        ))}
      </div>
    </div>
  );
}

interface CompactEventCardProps {
  event: CalendarEvent;
  onClick?: () => void;
}

function CompactEventCard({ event, onClick }: CompactEventCardProps) {
  const typeConfig = EVENT_TYPE_CONFIG[event.type];
  const dateDisplay = event.date
    ? formatDisplayDate(event.date)
    : `${formatDisplayDate(event.startDate!)} - ${formatDisplayDate(event.endDate!)}`;

  return (
    <div
      onClick={onClick}
      className="flex items-center gap-2 rounded-md border bg-white p-2 cursor-pointer hover:bg-gray-50 transition-colors"
    >
      {/* Type indicator dot */}
      <div
        className="h-2 w-2 rounded-full shrink-0"
        style={{
          backgroundColor: typeConfig.bgColor === 'transparent'
            ? typeConfig.color
            : typeConfig.bgColor,
        }}
      />

      {/* Date */}
      <span className="text-xs text-gray-500 w-12 shrink-0">{dateDisplay}</span>

      {/* Label */}
      <span className="text-sm font-medium truncate flex-1">{event.label}</span>

      {/* Type badge (subtle) */}
      <Badge
        variant="secondary"
        className="text-[10px] px-1.5 py-0 h-4 shrink-0"
        style={{
          backgroundColor: typeConfig.bgColor === 'transparent' ? '#f3f4f6' : `${typeConfig.bgColor}40`,
          color: typeConfig.color === '#ffffff' ? '#374151' : typeConfig.color,
        }}
      >
        {typeConfig.label.split(' ')[0]}
      </Badge>
    </div>
  );
}

function formatDisplayDate(dateStr: string): string {
  if (!dateStr) return '';
  const [year, month, day] = dateStr.split('-');
  return `${parseInt(month)}/${parseInt(day)}`;
}
