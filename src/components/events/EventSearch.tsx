'use client';

import { Input } from '@/components/ui/input';
import { Search, X } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface EventSearchProps {
  value: string;
  onChange: (value: string) => void;
  resultCount: number;
  totalCount: number;
}

export function EventSearch({ value, onChange, resultCount, totalCount }: EventSearchProps) {
  const hasFilter = value.length > 0;
  const showingFiltered = hasFilter && resultCount !== totalCount;

  return (
    <div className="space-y-1">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <Input
          type="text"
          placeholder="Search events..."
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="h-10 pl-9 pr-9"
        />
        {hasFilter && (
          <Button
            variant="ghost"
            size="sm"
            className="absolute right-1 top-1/2 h-7 w-7 -translate-y-1/2 p-0"
            onClick={() => onChange('')}
          >
            <X className="h-4 w-4" />
            <span className="sr-only">Clear search</span>
          </Button>
        )}
      </div>
      {showingFiltered && (
        <p className="text-xs text-gray-500">
          Showing {resultCount} of {totalCount} events
        </p>
      )}
    </div>
  );
}
