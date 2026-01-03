'use client';

import { CalendarCell, MonthData } from '@/lib/calendar/types';
import { DayCell } from './DayCell';

const DAY_NAMES = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

interface MonthViewProps {
  month: MonthData;
  onDayClick?: (cell: CalendarCell) => void;
  selectedDate?: Date | null;
}

export function MonthView({ month, onDayClick, selectedDate }: MonthViewProps) {
  // Check if a cell matches the selected date
  const isCellSelected = (cell: CalendarCell | null): boolean => {
    if (!cell || !selectedDate) return false;
    return (
      cell.date.getFullYear() === selectedDate.getFullYear() &&
      cell.date.getMonth() === selectedDate.getMonth() &&
      cell.date.getDate() === selectedDate.getDate()
    );
  };

  return (
    <div className="rounded-lg border bg-white p-1.5 sm:p-2">
      {/* Month name */}
      <h3 className="mb-1 sm:mb-2 text-center text-xs sm:text-sm font-semibold">{month.name}</h3>

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
          <DayCell
            key={index}
            cell={cell}
            onClick={onDayClick}
            isSelected={isCellSelected(cell)}
          />
        ))}
      </div>
    </div>
  );
}
