'use client';

import { CalendarCell, CalendarEvent, MonthData, SchoolYearConfig } from '@/lib/calendar/types';
import {
  MONTH_NAMES,
  generateMonthCells,
  getSchoolYearMonths,
  DEFAULT_SCHOOL_YEAR_CONFIG,
} from '@/lib/calendar/utils';
import { MonthView } from './MonthView';

interface CalendarGridProps {
  events: CalendarEvent[];
  schoolYear?: number;
  config?: SchoolYearConfig;
  onDayClick?: (cell: CalendarCell, monthData: MonthData) => void;
}

export function CalendarGrid({
  events,
  schoolYear = 2025,
  config = DEFAULT_SCHOOL_YEAR_CONFIG,
  onDayClick,
}: CalendarGridProps) {
  // Generate month data for the school year
  const monthRefs = getSchoolYearMonths(schoolYear);

  const months: MonthData[] = monthRefs.map(({ year, month }) => ({
    name: MONTH_NAMES[month],
    year,
    month,
    cells: generateMonthCells(year, month, events, config),
  }));

  const handleDayClick = (cell: CalendarCell, monthData: MonthData) => {
    onDayClick?.(cell, monthData);
  };

  return (
    <div className="grid grid-cols-3 gap-3 md:grid-cols-4 lg:grid-cols-4">
      {months.map((month) => (
        <MonthView
          key={`${month.year}-${month.month}`}
          month={month}
          onDayClick={(cell) => handleDayClick(cell, month)}
        />
      ))}
    </div>
  );
}
