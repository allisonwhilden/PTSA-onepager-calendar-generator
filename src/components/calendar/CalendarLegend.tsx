'use client';

import { EVENT_TYPE_CONFIG, EventType } from '@/lib/calendar/types';

const legendItems: { type: EventType; display: string }[] = [
  { type: 'no_school', display: 'No School' },
  { type: 'half_day', display: 'Half Day' },
  { type: 'early_release', display: 'Early Release Wed' },
  { type: 'ptsa_event', display: 'PTSA Event' },
  { type: 'first_day', display: 'First/Last Day' },
  { type: 'closure_possible', display: 'Make-up Day' },
];

export function CalendarLegend() {
  return (
    <div className="flex flex-wrap items-center gap-4 text-sm">
      {legendItems.map(({ type, display }) => {
        const config = EVENT_TYPE_CONFIG[type];
        return (
          <div key={type} className="flex items-center gap-2">
            <LegendIcon type={type} />
            <span>{display}</span>
          </div>
        );
      })}
    </div>
  );
}

function LegendIcon({ type }: { type: EventType }) {
  switch (type) {
    case 'no_school':
      return (
        <span className="flex h-5 w-5 items-center justify-center bg-black text-[10px] text-white">
          1
        </span>
      );
    case 'half_day':
      return (
        <span className="flex h-5 w-5 items-center justify-center bg-gray-300 text-[10px]">
          1
        </span>
      );
    case 'early_release':
      return (
        <span className="flex h-5 w-5 items-center justify-center text-[10px] font-black">
          1
        </span>
      );
    case 'ptsa_event':
      return (
        <span className="flex h-5 w-5 items-center justify-center">
          <span className="flex h-4 w-4 items-center justify-center rounded-full border border-red-600 text-[8px]">
            1
          </span>
        </span>
      );
    case 'first_day':
    case 'last_day':
      return (
        <span className="flex h-5 w-5 items-center justify-center">
          <span className="flex h-4 w-4 rotate-45 items-center justify-center border border-black">
            <span className="-rotate-45 text-[8px]">1</span>
          </span>
        </span>
      );
    case 'closure_possible':
      return (
        <span className="flex h-5 w-5 items-center justify-center bg-gray-200 text-[10px]">
          1
        </span>
      );
    default:
      return null;
  }
}
