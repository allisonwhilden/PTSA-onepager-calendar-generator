'use client';

import { useEffect, useState, useCallback } from 'react';
import { CalendarGrid, CalendarLegend } from '@/components/calendar';
import { EventList } from '@/components/events';
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

  // Handle day click - open add dialog
  const handleDayClick = (cell: CalendarCell) => {
    setFormMode('add');
    setEditingEvent(null);
    setSelectedDate(cell.date);
    setFormData({
      type: 'no_school',
      label: '',
      notes: '',
      isRange: false,
      endDate: '',
    });
    setIsDialogOpen(true);
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
    <div className="min-h-screen bg-gray-50 p-6">
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
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">
            Horace Mann <span className="text-red-600">PTSA</span> Calendar Editor
          </h1>
          <p className="text-gray-600">Click on any day to add an event</p>
        </div>
        <div className="flex gap-2">
          <PdfDownload events={events} />
          <CsvUpload onImport={handleCsvImport} />
          <Button variant="outline" onClick={handleExport} disabled={events.length === 0}>
            Export CSV
          </Button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="destructive" disabled={events.length === 0}>
                Clear All
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
      </header>

      {/* Main layout */}
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        {/* Left column - Calendar */}
        <div>
          {/* Legend */}
          <div className="mb-4">
            <CalendarLegend />
          </div>

          {/* Calendar Grid */}
          <CalendarGrid events={events} onDayClick={handleDayClick} />
        </div>

        {/* Right column - Event List */}
        <div>
          <h2 className="mb-3 text-lg font-semibold">
            Events ({events.length})
          </h2>
          <EventList
            events={events}
            onEdit={handleEdit}
            onDelete={handleDelete}
          />
        </div>
      </div>

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
