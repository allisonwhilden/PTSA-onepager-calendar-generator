'use client';

import { useState, useRef } from 'react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { CalendarEvent } from '@/lib/calendar/types';
import { parseCSV } from '@/lib/csv/parser';

type UploadMode = 'replace' | 'append';

interface CsvUploadProps {
  onImport: (events: CalendarEvent[], mode: UploadMode) => Promise<void>;
}

export function CsvUpload({ onImport }: CsvUploadProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [mode, setMode] = useState<UploadMode>('replace');
  const [parsedEvents, setParsedEvents] = useState<CalendarEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setError(null);

    try {
      const text = await file.text();
      const events = parseCSV(text);
      setParsedEvents(events);
    } catch (err) {
      setError((err as Error).message);
      setParsedEvents([]);
    }
  };

  const handleImport = async () => {
    if (parsedEvents.length === 0) return;

    setIsLoading(true);
    try {
      await onImport(parsedEvents, mode);
      setIsOpen(false);
      setParsedEvents([]);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    setIsOpen(false);
    setParsedEvents([]);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <>
      <Button variant="outline" size="sm" className="text-xs sm:text-sm" onClick={() => setIsOpen(true)}>
        Import
      </Button>

      <Dialog open={isOpen} onOpenChange={handleClose}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Import Events from CSV</DialogTitle>
            <DialogDescription>
              Upload a CSV file with event data. Choose to replace all events or append to existing ones.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {/* Mode selection */}
            <div className="flex gap-4">
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  name="mode"
                  value="replace"
                  checked={mode === 'replace'}
                  onChange={() => setMode('replace')}
                />
                <span className="text-sm">Replace all events</span>
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  name="mode"
                  value="append"
                  checked={mode === 'append'}
                  onChange={() => setMode('append')}
                />
                <span className="text-sm">Append to existing</span>
              </label>
            </div>

            {/* File input */}
            <div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                onChange={handleFileSelect}
                className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-gray-100 file:text-gray-700 hover:file:bg-gray-200"
              />
            </div>

            {/* Error message */}
            {error && (
              <div className="rounded-lg bg-red-100 p-3 text-sm text-red-700">
                {error}
              </div>
            )}

            {/* Preview */}
            {parsedEvents.length > 0 && (
              <div className="rounded-lg border bg-gray-50 p-3">
                <p className="text-sm font-medium">
                  Ready to import {parsedEvents.length} events
                </p>
                <ul className="mt-2 max-h-40 overflow-y-auto text-sm text-gray-600">
                  {parsedEvents.slice(0, 5).map((event, i) => (
                    <li key={i}>
                      {event.date || `${event.startDate} - ${event.endDate}`}: {event.label}
                    </li>
                  ))}
                  {parsedEvents.length > 5 && (
                    <li className="text-gray-400">
                      ...and {parsedEvents.length - 5} more
                    </li>
                  )}
                </ul>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={handleClose}>
              Cancel
            </Button>
            <Button
              onClick={handleImport}
              disabled={parsedEvents.length === 0 || isLoading}
            >
              {isLoading ? 'Importing...' : `Import ${parsedEvents.length} Events`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
