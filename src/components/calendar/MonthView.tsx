'use client';

import { CalendarCell, MonthData } from '@/lib/calendar/types';
import { DayCell } from './DayCell';

const DAY_NAMES = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

interface MonthViewProps {
  month: MonthData;
  onDayClick?: (cell: CalendarCell) => void;
}

export function MonthView({ month, onDayClick }: MonthViewProps) {
  // Split cells into weeks (7 days each)
  const weeks: (CalendarCell | null)[][] = [];
  for (let i = 0; i < month.cells.length; i += 7) {
    weeks.push(month.cells.slice(i, i + 7));
  }

  return (
    <div className="rounded-lg border bg-white p-2">
      {/* Month name */}
      <h3 className="mb-2 text-center text-sm font-semibold">{month.name}</h3>

      {/* Day names header */}
      <div className="mb-1 grid grid-cols-7 gap-0.5">
        {DAY_NAMES.map((day) => (
          <div
            key={day}
            className="text-center text-[10px] font-medium text-gray-500"
          >
            {day}
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="grid grid-cols-7 gap-0.5">
        {month.cells.map((cell, index) => (
          <DayCell key={index} cell={cell} onClick={onDayClick} />
        ))}
      </div>
    </div>
  );
}
