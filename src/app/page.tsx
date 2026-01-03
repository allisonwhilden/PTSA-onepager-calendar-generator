'use client';

import { useEffect, useState, useCallback } from 'react';
import { CalendarGrid, CalendarLegend } from '@/components/calendar';
import { EventList, MobileEventDrawer } from '@/components/events';
import { CsvUpload } from '@/components/upload';
import { PdfDownload } from '@/components/pdf';
import { CalendarEvent, CalendarCell, MonthData, EventsStore } from '@/lib/calendar/types';
import { formatDate } from '@/lib/calendar/utils';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { EVENT_TYPE_CONFIG, EventType } from '@/lib/calendar/types';

const EVENT_TYPES: EventType[] = [
  'no_school',
  'half_day',
  'ptsa_event',
  'first_day',
  'last_day',
  'early_release',
  'closure_possible',
];

type FormMode = 'add' | 'edit';

export default function Home() {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Dialog state
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [formMode, setFormMode] = useState<FormMode>('add');
  const [editingEvent, setEditingEvent] = useState<CalendarEvent | null>(null);
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const [formData, setFormData] = useState({
    type: 'no_school' as EventType,
    label: '',
    notes: '',
    isRange: false,
    endDate: '',
  });

  // Sidebar state - which date is being viewed (separate from dialog)
  const [viewingDate, setViewingDate] = useState<Date | null>(null);

  // Fetch events on mount
  const fetchEvents = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/events');
      if (!response.ok) throw new Error('Failed to fetch events');
      const data: EventsStore = await response.json();
      setEvents(data.events);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  // Handle day click - show events for that day in sidebar
  const handleDayClick = (cell: CalendarCell) => {
    setViewingDate(cell.date);
  };

  // Handle add event for the currently viewed date
  const handleAddEventForDate = () => {
    if (!viewingDate) return;
    setFormMode('add');
    setEditingEvent(null);
    setSelectedDate(viewingDate);
    setFormData({
      type: 'no_school',
      label: '',
      notes: '',
      isRange: false,
      endDate: '',
    });
    setIsDialogOpen(true);
  };

  // Clear the viewing date selection
  const handleClearSelection = () => {
    setViewingDate(null);
  };

  // Handle edit click
  const handleEdit = (event: CalendarEvent) => {
    setFormMode('edit');
    setEditingEvent(event);
    setSelectedDate(event.date ? new Date(event.date + 'T00:00:00') : null);
    setFormData({
      type: event.type,
      label: event.label,
      notes: event.notes || '',
      isRange: !!event.startDate,
      endDate: event.endDate || '',
    });
    setIsDialogOpen(true);
  };

  // Handle delete
  const handleDelete = async (eventId: string) => {
    try {
      const response = await fetch(`/api/events?id=${eventId}`, {
        method: 'DELETE',
      });
      if (!response.ok) throw new Error('Failed to delete event');
      const data = await response.json();
      setEvents(data.store.events);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  // Handle clear all
  const handleClearAll = async () => {
    try {
      const response = await fetch('/api/events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'clear' }),
      });
      if (!response.ok) throw new Error('Failed to clear events');
      const data = await response.json();
      setEvents(data.store.events);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  // Handle CSV import
  const handleCsvImport = async (newEvents: CalendarEvent[], mode: 'replace' | 'append') => {
    try {
      const response = await fetch('/api/events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: mode,
          events: newEvents,
        }),
      });
      if (!response.ok) throw new Error('Failed to import events');
      const data = await response.json();
      setEvents(data.store.events);
    } catch (err) {
      setError((err as Error).message);
      throw err;
    }
  };

  // Handle CSV export
  const handleExport = () => {
    window.location.href = '/api/export';
  };

  // Handle form submit
  const handleSubmit = async () => {
    if (!formData.label) return;

    try {
      if (formMode === 'add') {
        const eventData: Partial<CalendarEvent> = {
          type: formData.type,
          label: formData.label,
          notes: formData.notes || undefined,
        };

        if (formData.isRange && formData.endDate && selectedDate) {
          eventData.startDate = formatDate(selectedDate);
          eventData.endDate = formData.endDate;
        } else if (selectedDate) {
          eventData.date = formatDate(selectedDate);
        }

        const response = await fetch('/api/events', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'add', event: eventData }),
        });

        if (!response.ok) throw new Error('Failed to add event');
        const data = await response.json();
        setEvents(data.store.events);
      } else if (formMode === 'edit' && editingEvent) {
        const updates: Partial<CalendarEvent> = {
          type: formData.type,
          label: formData.label,
          notes: formData.notes || undefined,
        };

        if (formData.isRange && formData.endDate) {
          updates.startDate = editingEvent.startDate || editingEvent.date;
          updates.endDate = formData.endDate;
          updates.date = undefined;
        } else {
          updates.date = editingEvent.date || editingEvent.startDate;
          updates.startDate = undefined;
          updates.endDate = undefined;
        }

        const response = await fetch('/api/events', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: editingEvent.id, ...updates }),
        });

        if (!response.ok) throw new Error('Failed to update event');
        const data = await response.json();
        setEvents(data.store.events);
      }

      setIsDialogOpen(false);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-lg">Loading calendar...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-3 sm:p-4 lg:p-6">
      {/* Error banner */}
      {error && (
        <div className="mb-4 rounded-lg bg-red-100 p-4 text-red-700">
          {error}
          <button className="ml-4 underline" onClick={() => setError(null)}>
            Dismiss
          </button>
        </div>
      )}

      {/* Header */}
      <header className="mb-4 lg:mb-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-lg sm:text-xl lg:text-2xl font-bold">
              Horace Mann <span className="text-red-600">PTSA</span> Calendar
            </h1>
            <p className="text-sm text-gray-600 hidden sm:block">Click on any day to add an event</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <PdfDownload events={events} />
            <CsvUpload onImport={handleCsvImport} />
            <Button variant="outline" size="sm" onClick={handleExport} disabled={events.length === 0} className="text-xs sm:text-sm">
              Export
            </Button>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="destructive" size="sm" disabled={events.length === 0} className="text-xs sm:text-sm">
                  Clear
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Clear all events?</AlertDialogTitle>
                  <AlertDialogDescription>
                    This will permanently delete all {events.length} events. This action cannot be undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={handleClearAll}>
                    Yes, clear all
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </div>
      </header>

      {/* Main layout */}
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        {/* Left column - Calendar */}
        <div className="pb-16 lg:pb-0">
          {/* Legend */}
          <div className="mb-4">
            <CalendarLegend />
          </div>

          {/* Calendar Grid */}
          <CalendarGrid events={events} onDayClick={handleDayClick} selectedDate={viewingDate} />
        </div>

        {/* Right column - Event List (desktop only) */}
        <div className="hidden lg:block">
          <h2 className="mb-3 text-lg font-semibold">
            Events ({events.length})
          </h2>
          <EventList
            events={events}
            onEdit={handleEdit}
            onDelete={handleDelete}
            selectedDate={viewingDate}
            onClearSelection={handleClearSelection}
            onAddEvent={handleAddEventForDate}
          />
        </div>
      </div>

      {/* Mobile Event Drawer (mobile only) */}
      <MobileEventDrawer
        events={events}
        onEdit={handleEdit}
        onDelete={handleDelete}
        selectedDate={viewingDate}
        onClearSelection={handleClearSelection}
        onAddEvent={handleAddEventForDate}
      />

      {/* Add/Edit Event Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {formMode === 'add' ? 'Add Event' : 'Edit Event'}
            </DialogTitle>
            <DialogDescription>
              {formMode === 'add' && selectedDate
                ? `Adding event for ${selectedDate.toLocaleDateString()}`
                : formMode === 'edit' && editingEvent
                ? `Editing: ${editingEvent.label}`
                : ''}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div>
              <Label htmlFor="type">Event Type</Label>
              <Select
                value={formData.type}
                onValueChange={(value) =>
                  setFormData({ ...formData, type: value as EventType })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {EVENT_TYPES.map((type) => (
                    <SelectItem key={type} value={type}>
                      {EVENT_TYPE_CONFIG[type].label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label htmlFor="label">Label</Label>
              <Input
                id="label"
                value={formData.label}
                onChange={(e) =>
                  setFormData({ ...formData, label: e.target.value })
                }
                placeholder="e.g., Winter Break"
              />
            </div>

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="isRange"
                checked={formData.isRange}
                onChange={(e) =>
                  setFormData({ ...formData, isRange: e.target.checked })
                }
              />
              <Label htmlFor="isRange">Date range</Label>
            </div>

            {formData.isRange && (
              <div>
                <Label htmlFor="endDate">End Date</Label>
                <Input
                  id="endDate"
                  type="date"
                  value={formData.endDate}
                  onChange={(e) =>
                    setFormData({ ...formData, endDate: e.target.value })
                  }
                />
              </div>
            )}

            <div>
              <Label htmlFor="notes">Notes (optional)</Label>
              <Textarea
                id="notes"
                value={formData.notes}
                onChange={(e) =>
                  setFormData({ ...formData, notes: e.target.value })
                }
                placeholder="Additional details..."
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={!formData.label}>
              {formMode === 'add' ? 'Add Event' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
