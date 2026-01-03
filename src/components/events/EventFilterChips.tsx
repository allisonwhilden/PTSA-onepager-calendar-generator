'use client';

import { EventType, EVENT_TYPE_CONFIG } from '@/lib/calendar/types';
import { cn } from '@/lib/utils';

export type FilterValue = EventType | 'all';

interface EventFilterChipsProps {
  value: FilterValue;
  onChange: (value: FilterValue) => void;
  eventCounts: Record<EventType | 'all', number>;
}

const FILTER_OPTIONS: { value: FilterValue; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'no_school', label: 'No School' },
  { value: 'ptsa_event', label: 'PTSA' },
  { value: 'half_day', label: 'Half Day' },
  { value: 'early_release', label: 'Early Release' },
  { value: 'closure_possible', label: 'Make-up' },
];

export function EventFilterChips({ value, onChange, eventCounts }: EventFilterChipsProps) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {FILTER_OPTIONS.map((option) => {
        const isSelected = value === option.value;
        const count = eventCounts[option.value];
        const typeConfig = option.value !== 'all' ? EVENT_TYPE_CONFIG[option.value] : null;

        // Skip filters with no events (except 'all')
        if (option.value !== 'all' && count === 0) return null;

        return (
          <button
            key={option.value}
            onClick={() => onChange(option.value)}
            className={cn(
              'inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium transition-colors',
              'min-h-[32px] touch-manipulation', // 44px touch target via padding
              isSelected
                ? option.value === 'all'
                  ? 'bg-gray-900 text-white'
                  : 'ring-2 ring-offset-1'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            )}
            style={
              isSelected && typeConfig
                ? {
                    backgroundColor: typeConfig.bgColor === 'transparent' ? '#f3f4f6' : typeConfig.bgColor,
                    color: typeConfig.color,
                    outlineColor: typeConfig.color,
                  }
                : undefined
            }
          >
            {option.label}
            <span
              className={cn(
                'rounded-full px-1.5 py-0.5 text-[10px]',
                isSelected ? 'bg-white/20' : 'bg-gray-200'
              )}
            >
              {count}
            </span>
          </button>
        );
      })}
    </div>
  );
}
