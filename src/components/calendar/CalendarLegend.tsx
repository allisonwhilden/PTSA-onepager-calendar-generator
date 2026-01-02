'use client';

import { EVENT_TYPE_CONFIG, EventType } from '@/lib/calendar/types';

type LegendItemType = EventType | 'asterisk';

const legendItems: { type: LegendItemType; display: string }[] = [
  { type: 'no_school', display: 'No School' },
  { type: 'half_day', display: 'Half Day' },
  { type: 'early_release', display: '=Early Release' },
  { type: 'ptsa_event', display: 'PTSA Event' },
  { type: 'first_day', display: 'First/Last Day' },
  { type: 'closure_possible', display: 'Make-up Day' },
  { type: 'asterisk', display: '=See Dates' },
];

export function CalendarLegend() {
  return (
    <div className="flex flex-wrap items-center gap-4 text-sm">
      {legendItems.map(({ type, display }) => {
        return (
          <div key={type} className="flex items-center gap-1.5">
            <LegendIcon type={type} />
            <span>{display}</span>
          </div>
        );
      })}
    </div>
  );
}

function LegendIcon({ type }: { type: LegendItemType }) {
  switch (type) {
    case 'no_school':
      return (
        <span className="flex h-4 w-4 items-center justify-center border border-black bg-black text-[9px] text-white">
          1
        </span>
      );
    case 'half_day':
      return (
        <span className="flex h-4 w-4 items-center justify-center border border-black bg-gray-300 text-[9px]">
          1
        </span>
      );
    case 'early_release':
      // Show "Bold" text to indicate bold formatting
      return (
        <span className="text-[10px] font-black">Bold</span>
      );
    case 'ptsa_event':
      return (
        <span className="flex h-4 w-4 items-center justify-center rounded-full border border-red-600 text-[8px]">
          1
        </span>
      );
    case 'first_day':
    case 'last_day':
      // Rectangle box (not rotated diamond)
      return (
        <span className="inline-flex items-center justify-center border border-black px-1 text-[9px] font-bold leading-tight">
          1
        </span>
      );
    case 'closure_possible':
      // Striped pattern chip
      return (
        <span className="h-4 w-4 border border-black stripe-pattern" />
      );
    case 'asterisk':
      return (
        <span className="text-sm font-bold">*</span>
      );
    default:
      return null;
  }
}
