'use client';

import { CalendarCell, EventType } from '@/lib/calendar/types';
import { cn } from '@/lib/utils';

interface DayCellProps {
  cell: CalendarCell | null;
  onClick?: (cell: CalendarCell) => void;
  isSelected?: boolean;
}

// Map event types to visual styles
const markStyles: Record<EventType, string> = {
  no_school: 'bg-black text-white',
  half_day: 'bg-gray-300',
  early_release: 'font-black',
  ptsa_event: '', // Handled with circle
  first_day: '', // Handled with box
  last_day: '', // Handled with box
  closure_possible: 'stripe-pattern', // Diagonal stripes
};

export function DayCell({ cell, onClick, isSelected }: DayCellProps) {
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
    ? 'stripe-pattern'
    : '';

  // Determine if early release (bold)
  const isEarlyRelease = marks.includes('early_release');
  const isPtsaEvent = marks.includes('ptsa_event');

  // Bold only for early release days (unless it's a PTSA day - then also bold)
  const isBold = isEarlyRelease || (isPtsaEvent && isEarlyRelease);

  // Render day content with optional indicator wrapper
  const renderDayContent = () => {
    const asterisk = showAsterisk ? '*' : '';

    // Rectangle box for first/last day (not diamond)
    if (hasDiamond && !hasCircle) {
      return (
        <span className="inline-flex items-center justify-center border border-black px-1 font-bold text-xs leading-tight">
          {day}{asterisk}
        </span>
      );
    }

    // Red circle for PTSA events
    if (hasCircle) {
      return (
        <span className="relative z-10 inline-flex h-5 w-5 items-center justify-center rounded-full border border-red-600">
          {day}{asterisk}
        </span>
      );
    }

    // Default: just the number with inline asterisk
    return <span className="relative z-10">{day}{asterisk}</span>;
  };

  return (
    <div
      onClick={() => cell && onClick?.(cell)}
      className={cn(
        'relative flex h-8 w-8 cursor-pointer items-center justify-center text-sm transition-colors hover:bg-blue-100',
        bgClass,
        isWeekend && !bgClass && 'text-gray-400',
        isBold && 'font-black',
        isSelected && 'ring-2 ring-blue-500 ring-offset-1 rounded-sm'
      )}
    >
      {renderDayContent()}
    </div>
  );
}
