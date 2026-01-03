'use client';

import { useState, useEffect } from 'react';
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from '@/components/ui/drawer';
import { Button } from '@/components/ui/button';
import { CalendarEvent } from '@/lib/calendar/types';
import { EventList } from './EventList';
import { ChevronUp, Calendar } from 'lucide-react';

interface MobileEventDrawerProps {
  events: CalendarEvent[];
  onEdit: (event: CalendarEvent) => void;
  onDelete: (eventId: string) => void;
  selectedDate?: Date | null;
  onClearSelection?: () => void;
  onAddEvent?: () => void;
}

// Hook to check if we're on mobile (below lg breakpoint)
function useIsMobile() {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 1024); // lg breakpoint
    };

    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  return isMobile;
}

export function MobileEventDrawer({
  events,
  onEdit,
  onDelete,
  selectedDate,
  onClearSelection,
  onAddEvent,
}: MobileEventDrawerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const isMobile = useIsMobile();

  // Open drawer when a date is selected (mobile only)
  useEffect(() => {
    if (selectedDate && isMobile) {
      setIsOpen(true);
    }
  }, [selectedDate, isMobile]);

  // Don't render anything on desktop
  if (!isMobile) {
    return null;
  }

  // Format selected date for peek view
  const formatPeekDate = (date: Date): string => {
    return date.toLocaleDateString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
    });
  };

  // Count upcoming events (next 7 days)
  const upcomingCount = (() => {
    const now = new Date();
    const weekFromNow = new Date();
    weekFromNow.setDate(weekFromNow.getDate() + 7);

    return events.filter((event) => {
      const dateStr = event.date || event.startDate || '';
      if (!dateStr) return false;
      return dateStr >= now.toISOString().split('T')[0] && dateStr <= weekFromNow.toISOString().split('T')[0];
    }).length;
  })();

  return (
    <Drawer open={isOpen} onOpenChange={setIsOpen}>
      {/* Peek bar trigger at bottom of screen */}
      <DrawerTrigger asChild>
        <div className="fixed bottom-0 left-0 right-0 z-50 lg:hidden">
          <Button
            variant="outline"
            className="w-full h-14 rounded-none rounded-t-xl border-b-0 bg-white shadow-lg flex items-center justify-between px-4"
          >
            <div className="flex items-center gap-2">
              <Calendar className="h-5 w-5 text-gray-500" />
              {selectedDate ? (
                <span className="font-medium">{formatPeekDate(selectedDate)}</span>
              ) : (
                <span className="text-gray-600">
                  {upcomingCount > 0 ? `${upcomingCount} events this week` : 'View events'}
                </span>
              )}
            </div>
            <ChevronUp className="h-5 w-5 text-gray-400" />
          </Button>
        </div>
      </DrawerTrigger>

      <DrawerContent className="max-h-[85vh]">
        <DrawerHeader className="px-4 py-2 border-b">
          <div className="flex items-center justify-between">
            <DrawerTitle className="text-base">
              {selectedDate ? formatPeekDate(selectedDate) : 'Events'}
            </DrawerTitle>
            {selectedDate && (
              <Button
                variant="ghost"
                size="sm"
                className="h-8 text-xs"
                onClick={() => {
                  onClearSelection?.();
                  // Keep drawer open but show all events
                }}
              >
                Show all
              </Button>
            )}
          </div>
        </DrawerHeader>

        {/* Scrollable content area */}
        <div className="overflow-y-auto px-4 pb-8 pt-2" style={{ maxHeight: 'calc(85vh - 60px)' }}>
          <EventList
            events={events}
            onEdit={(event) => {
              onEdit(event);
              setIsOpen(false);
            }}
            onDelete={onDelete}
            selectedDate={selectedDate}
            onClearSelection={onClearSelection}
            onAddEvent={onAddEvent}
          />
        </div>
      </DrawerContent>
    </Drawer>
  );
}
