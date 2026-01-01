'use client';

import { useState } from 'react';
import { pdf } from '@react-pdf/renderer';
import { Button } from '@/components/ui/button';
import { CalendarEvent, SchoolYearConfig } from '@/lib/calendar/types';
import { CalendarPdf } from '@/lib/pdf/CalendarPdf';
import { DEFAULT_SCHOOL_YEAR_CONFIG } from '@/lib/calendar/utils';

interface PdfDownloadProps {
  events: CalendarEvent[];
  schoolYear?: number;
  config?: SchoolYearConfig;
}

export function PdfDownload({
  events,
  schoolYear = 2025,
  config = DEFAULT_SCHOOL_YEAR_CONFIG,
}: PdfDownloadProps) {
  const [isGenerating, setIsGenerating] = useState(false);

  const handleDownload = async () => {
    setIsGenerating(true);

    try {
      const doc = (
        <CalendarPdf events={events} schoolYear={schoolYear} config={config} />
      );
      const blob = await pdf(doc).toBlob();
      const url = URL.createObjectURL(blob);

      const link = document.createElement('a');
      link.href = url;
      link.download = `HoraceMann-PTSA-${schoolYear}-${(schoolYear + 1) % 100}-Calendar.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error generating PDF:', error);
      alert('Failed to generate PDF. Please try again.');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <Button onClick={handleDownload} disabled={isGenerating}>
      {isGenerating ? 'Generating...' : 'Download PDF'}
    </Button>
  );
}
