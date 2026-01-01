'use client';

import { CalendarCell, EventType } from '@/lib/calendar/types';
import { cn } from '@/lib/utils';

interface DayCellProps {
  cell: CalendarCell | null;
  onClick?: (cell: CalendarCell) => void;
}

// Map event types to visual styles
const markStyles: Record<EventType, string> = {
  no_school: 'bg-black text-white',
  half_day: 'bg-gray-300',
  early_release: 'font-black',
  ptsa_event: '', // Handled with circle
  first_day: '', // Handled with diamond
  last_day: '', // Handled with diamond
  closure_possible: 'bg-gray-200',
};

export function DayCell({ cell, onClick }: DayCellProps) {
  if (!cell) {
    return <div className="h-8 w-8" />;
  }

  const { day, marks, isWeekend, hasDiamond, hasCircle, showAsterisk } = cell;

  // Determine background class
  const bgClass = marks.includes('no_school')
    ? 'bg-black text-white'
    : marks.includes('half_day')
    ? 'bg-gray-300'
    : marks.includes('closure_possible')
    ? 'bg-gray-200'
    : '';

  // Determine if early release (bold)
  const isEarlyRelease = marks.includes('early_release');
  const isPtsaEvent = marks.includes('ptsa_event');

  // Bold only for early release days (unless it's a PTSA day - then also bold)
  const isBold = isEarlyRelease || (isPtsaEvent && isEarlyRelease);

  return (
    <div
      onClick={() => cell && onClick?.(cell)}
      className={cn(
        'relative flex h-8 w-8 cursor-pointer items-center justify-center text-sm transition-colors hover:bg-blue-100',
        bgClass,
        isWeekend && !bgClass && 'text-gray-400',
        isBold && 'font-black'
      )}
    >
      {/* Diamond indicator for first/last day */}
      {hasDiamond && (
        <span className="absolute inset-0 flex items-center justify-center">
          <span className="h-5 w-5 rotate-45 border border-black" />
        </span>
      )}

      {/* Circle indicator for PTSA event */}
      {hasCircle && (
        <span className="absolute inset-0 flex items-center justify-center">
          <span className="h-5 w-5 rounded-full border border-red-600" />
        </span>
      )}

      {/* Day number */}
      <span className="relative z-10">{day}</span>

      {/* Asterisk for additional info */}
      {showAsterisk && (
        <span className="absolute -right-0.5 top-0 text-[10px] leading-none">
          *
        </span>
      )}
    </div>
  );
}
