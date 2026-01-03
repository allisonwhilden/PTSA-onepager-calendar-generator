'use client';

import { useState, useMemo } from 'react';
import { CalendarEvent, EVENT_TYPE_CONFIG, EventType } from '@/lib/calendar/types';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { EventSearch } from './EventSearch';
import { EventFilterChips, FilterValue } from './EventFilterChips';
import { ComingUpView } from './ComingUpView';
import { FullEventList } from './FullEventList';

interface EventListProps {
  events: CalendarEvent[];
  onEdit: (event: CalendarEvent) => void;
  onDelete: (eventId: string) => void;
  selectedDate?: Date | null;
  onClearSelection?: () => void;
  onAddEvent?: () => void;
}

type ViewMode = 'coming-up' | 'all' | 'full-list';

export function EventList({ events, onEdit, onDelete, selectedDate, onClearSelection, onAddEvent }: EventListProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState<FilterValue>('all');
  const [viewMode, setViewMode] = useState<ViewMode>('coming-up');

  // Helper to check if an event falls on a specific date
  const eventMatchesDate = (event: CalendarEvent, date: Date): boolean => {
    const dateStr = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;

    // Single day event
    if (event.date) {
      return event.date === dateStr;
    }

    // Date range event
    if (event.startDate && event.endDate) {
      return dateStr >= event.startDate && dateStr <= event.endDate;
    }

    return false;
  };

  // Calculate event counts for filter chips (from all events, not filtered)
  const eventCounts = useMemo(() => {
    const counts: Record<EventType | 'all', number> = {
      all: events.length,
      no_school: 0,
      half_day: 0,
      ptsa_event: 0,
      first_day: 0,
      last_day: 0,
      early_release: 0,
      closure_possible: 0,
    };

    events.forEach((event) => {
      counts[event.type]++;
    });

    return counts;
  }, [events]);

  // Filter and sort events
  const filteredEvents = useMemo(() => {
    let result = [...events];

    // Apply date filter (if a date is selected)
    if (selectedDate) {
      result = result.filter((event) => eventMatchesDate(event, selectedDate));
    }

    // Apply type filter
    if (typeFilter !== 'all') {
      result = result.filter((event) => event.type === typeFilter);
    }

    // Apply search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      result = result.filter((event) => {
        const labelMatch = event.label.toLowerCase().includes(query);
        const notesMatch = event.notes?.toLowerCase().includes(query);
        const typeMatch = EVENT_TYPE_CONFIG[event.type].label.toLowerCase().includes(query);
        // Also search by formatted date
        const dateStr = event.date || event.startDate || '';
        const dateMatch = formatDisplayDate(dateStr).includes(query);
        return labelMatch || notesMatch || typeMatch || dateMatch;
      });
    }

    // Sort by date
    result.sort((a, b) => {
      const dateA = a.date || a.startDate || '';
      const dateB = b.date || b.startDate || '';
      return dateA.localeCompare(dateB);
    });

    return result;
  }, [events, searchQuery, typeFilter, selectedDate]);

  const hasActiveFilters = searchQuery.length > 0 || typeFilter !== 'all';

  // Format selected date for display
  const formatSelectedDate = (date: Date): string => {
    return date.toLocaleDateString('en-US', {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric'
    });
  };

  // Determine what to show
  const showComingUp = !selectedDate && viewMode === 'coming-up' && !searchQuery && typeFilter === 'all';
  const showFullList = viewMode === 'full-list' && !selectedDate;

  // Full list view (collapsible months)
  if (showFullList) {
    return (
      <FullEventList
        events={events}
        onEventClick={onEdit}
        onBack={() => setViewMode('coming-up')}
      />
    );
  }

  return (
    <div className="space-y-3">
      {/* Selected date header */}
      {selectedDate && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-blue-600">Viewing events for</p>
              <p className="font-semibold text-blue-900">{formatSelectedDate(selectedDate)}</p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 text-xs text-blue-600 hover:text-blue-800"
              onClick={onClearSelection}
            >
              View all
            </Button>
          </div>
          {filteredEvents.length === 0 && (
            <div className="mt-3 pt-3 border-t border-blue-200">
              <p className="text-sm text-blue-700 mb-2">No events on this day.</p>
              {onAddEvent && (
                <Button
                  size="sm"
                  className="h-8 text-xs"
                  onClick={onAddEvent}
                >
                  + Add Event
                </Button>
              )}
            </div>
          )}
        </div>
      )}

      {/* Coming Up View (default when no date selected and no search/filters) */}
      {showComingUp ? (
        <ComingUpView
          events={events}
          onEventClick={onEdit}
          onViewAll={() => setViewMode('full-list')}
        />
      ) : (
        <>
          {/* Search */}
          <EventSearch
            value={searchQuery}
            onChange={(val) => {
              setSearchQuery(val);
              if (val) setViewMode('all'); // Switch to all view when searching
            }}
            resultCount={filteredEvents.length}
            totalCount={selectedDate ? filteredEvents.length : events.length}
          />

          {/* Filter chips - hide when viewing a specific date */}
          {!selectedDate && (
            <EventFilterChips
              value={typeFilter}
              onChange={(val) => {
                setTypeFilter(val);
                if (val !== 'all') setViewMode('all'); // Switch to all view when filtering
              }}
              eventCounts={eventCounts}
            />
          )}

          {/* Back to Coming Up button (when in all view) */}
          {!selectedDate && viewMode === 'all' && !searchQuery && typeFilter === 'all' && (
            <div className="flex gap-2">
              <Button
                variant="ghost"
                size="sm"
                className="h-8 text-xs"
                onClick={() => setViewMode('coming-up')}
              >
                ← Coming Up
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-8 text-xs"
                onClick={() => setViewMode('full-list')}
              >
                Browse by Month
              </Button>
            </div>
          )}

          {/* Clear filters button */}
          {hasActiveFilters && filteredEvents.length !== events.length && !selectedDate && (
            <Button
              variant="ghost"
              size="sm"
              className="h-8 text-xs"
              onClick={() => {
                setSearchQuery('');
                setTypeFilter('all');
              }}
            >
              Clear filters
            </Button>
          )}

          {/* Event list */}
          {events.length === 0 ? (
            <div className="rounded-lg border bg-white p-4 text-center text-gray-500">
              No events yet. Click on a day to add one.
            </div>
          ) : filteredEvents.length === 0 && !selectedDate ? (
            <div className="rounded-lg border bg-white p-4 text-center text-gray-500">
              No events match your search.
              <button
                className="ml-1 text-blue-600 underline"
                onClick={() => {
                  setSearchQuery('');
                  setTypeFilter('all');
                }}
              >
                Clear filters
              </button>
            </div>
          ) : filteredEvents.length > 0 ? (
            <>
              <div className="space-y-2">
                {filteredEvents.map((event) => (
                  <EventCard
                    key={event.id}
                    event={event}
                    onEdit={() => onEdit(event)}
                    onDelete={() => onDelete(event.id)}
                    searchQuery={searchQuery}
                  />
                ))}
              </div>
              {/* View all by month link at bottom */}
              {!selectedDate && events.length > 5 && (
                <div className="pt-2 text-center">
                  <button
                    className="text-sm text-gray-500 hover:text-gray-700 underline"
                    onClick={() => setViewMode('full-list')}
                  >
                    Browse all {events.length} events by month →
                  </button>
                </div>
              )}
            </>
          ) : null}
        </>
      )}
    </div>
  );
}

interface EventCardProps {
  event: CalendarEvent;
  onEdit: () => void;
  onDelete: () => void;
  searchQuery?: string;
}

function EventCard({ event, onEdit, onDelete, searchQuery }: EventCardProps) {
  const typeConfig = EVENT_TYPE_CONFIG[event.type];
  const dateDisplay = event.date
    ? formatDisplayDate(event.date)
    : `${formatDisplayDate(event.startDate!)} - ${formatDisplayDate(event.endDate!)}`;

  // Highlight matching text if search is active
  const highlightText = (text: string) => {
    if (!searchQuery?.trim()) return text;
    const regex = new RegExp(`(${escapeRegex(searchQuery)})`, 'gi');
    const parts = text.split(regex);
    return parts.map((part, i) =>
      regex.test(part) ? (
        <mark key={i} className="bg-yellow-200 px-0.5 rounded">
          {part}
        </mark>
      ) : (
        part
      )
    );
  };

  return (
    <div className="flex items-start justify-between gap-2 rounded-lg border bg-white p-3">
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <Badge
            style={{
              backgroundColor: typeConfig.bgColor === 'transparent' ? '#f3f4f6' : typeConfig.bgColor,
              color: typeConfig.color,
            }}
            className="shrink-0"
          >
            {typeConfig.label}
          </Badge>
          <span className="text-sm text-gray-500">{dateDisplay}</span>
        </div>
        <p className="mt-1 font-medium break-words">{highlightText(event.label)}</p>
        {event.notes && (
          <p className="mt-0.5 text-sm text-gray-600 break-words">{highlightText(event.notes)}</p>
        )}
      </div>
      <div className="flex shrink-0 gap-1">
        <Button variant="outline" size="sm" onClick={onEdit} className="h-8 px-2 text-xs">
          Edit
        </Button>
        <Button variant="destructive" size="sm" onClick={onDelete} className="h-8 px-2 text-xs">
          Delete
        </Button>
      </div>
    </div>
  );
}

function formatDisplayDate(dateStr: string): string {
  if (!dateStr) return '';
  const [year, month, day] = dateStr.split('-');
  return `${parseInt(month)}/${parseInt(day)}`;
}

function escapeRegex(string: string): string {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
