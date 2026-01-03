'use client';

import { useState, useMemo } from 'react';
import { CalendarEvent, EVENT_TYPE_CONFIG } from '@/lib/calendar/types';
import { groupEventsByMonth, MonthEventsGroup } from '@/lib/calendar/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ChevronDown, ChevronRight, ArrowLeft } from 'lucide-react';

interface FullEventListProps {
  events: CalendarEvent[];
  onEventClick?: (event: CalendarEvent) => void;
  onBack?: () => void;
}

export function FullEventList({ events, onEventClick, onBack }: FullEventListProps) {
  const [expandedMonths, setExpandedMonths] = useState<Set<string>>(new Set());

  const monthGroups = useMemo(() => {
    return groupEventsByMonth(events);
  }, [events]);

  // Start with first 3 months expanded
  useMemo(() => {
    if (expandedMonths.size === 0 && monthGroups.length > 0) {
      const initial = new Set<string>();
      monthGroups.slice(0, 3).forEach((g) => initial.add(g.label));
      setExpandedMonths(initial);
    }
  }, [monthGroups]);

  const toggleMonth = (label: string) => {
    setExpandedMonths((prev) => {
      const next = new Set(prev);
      if (next.has(label)) {
        next.delete(label);
      } else {
        next.add(label);
      }
      return next;
    });
  };

  const expandAll = () => {
    setExpandedMonths(new Set(monthGroups.map((g) => g.label)));
  };

  const collapseAll = () => {
    setExpandedMonths(new Set());
  };

  if (events.length === 0) {
    return (
      <div className="rounded-lg border bg-white p-4 text-center text-gray-500">
        No events yet. Click on a day to add one.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {onBack && (
            <Button
              variant="ghost"
              size="sm"
              className="h-8 px-2"
              onClick={onBack}
            >
              <ArrowLeft className="h-4 w-4" />
            </Button>
          )}
          <div>
            <h3 className="font-semibold text-gray-900">All Events</h3>
            <p className="text-xs text-gray-500">{events.length} events</p>
          </div>
        </div>
        <div className="flex gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs text-gray-500"
            onClick={expandAll}
          >
            Expand all
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs text-gray-500"
            onClick={collapseAll}
          >
            Collapse
          </Button>
        </div>
      </div>

      {/* Month groups */}
      <div className="space-y-2">
        {monthGroups.map((group) => (
          <MonthSection
            key={group.label}
            group={group}
            isExpanded={expandedMonths.has(group.label)}
            onToggle={() => toggleMonth(group.label)}
            onEventClick={onEventClick}
          />
        ))}
      </div>
    </div>
  );
}

interface MonthSectionProps {
  group: MonthEventsGroup;
  isExpanded: boolean;
  onToggle: () => void;
  onEventClick?: (event: CalendarEvent) => void;
}

function MonthSection({ group, isExpanded, onToggle, onEventClick }: MonthSectionProps) {
  return (
    <div className="rounded-lg border bg-white overflow-hidden">
      {/* Month header - sticky */}
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-2 bg-gray-50 hover:bg-gray-100 transition-colors sticky top-0 z-10"
      >
        <div className="flex items-center gap-2">
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 text-gray-500" />
          ) : (
            <ChevronRight className="h-4 w-4 text-gray-500" />
          )}
          <span className="font-medium text-sm">{group.label}</span>
        </div>
        <Badge variant="secondary" className="text-xs">
          {group.events.length}
        </Badge>
      </button>

      {/* Events */}
      {isExpanded && (
        <div className="divide-y divide-gray-100">
          {group.events.map((event) => (
            <CompactEventRow
              key={event.id}
              event={event}
              onClick={() => onEventClick?.(event)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

interface CompactEventRowProps {
  event: CalendarEvent;
  onClick?: () => void;
}

function CompactEventRow({ event, onClick }: CompactEventRowProps) {
  const typeConfig = EVENT_TYPE_CONFIG[event.type];
  const dateDisplay = event.date
    ? formatDisplayDate(event.date)
    : `${formatDisplayDate(event.startDate!)} - ${formatDisplayDate(event.endDate!)}`;

  return (
    <div
      onClick={onClick}
      className="flex items-center gap-2 p-2 cursor-pointer hover:bg-gray-50 transition-colors"
    >
      {/* Type indicator dot */}
      <div
        className="h-2 w-2 rounded-full shrink-0"
        style={{
          backgroundColor:
            typeConfig.bgColor === 'transparent'
              ? typeConfig.color
              : typeConfig.bgColor,
        }}
      />

      {/* Date */}
      <span className="text-xs text-gray-500 w-16 shrink-0">{dateDisplay}</span>

      {/* Label */}
      <span className="text-sm truncate flex-1">{event.label}</span>

      {/* Type badge (subtle) */}
      <Badge
        variant="secondary"
        className="text-[10px] px-1.5 py-0 h-4 shrink-0"
        style={{
          backgroundColor:
            typeConfig.bgColor === 'transparent'
              ? '#f3f4f6'
              : `${typeConfig.bgColor}40`,
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
