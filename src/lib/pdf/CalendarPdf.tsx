'use client';

import {
  Document,
  Page,
  Text,
  View,
  StyleSheet,
  Svg,
  Rect,
  Circle,
  Line,
} from '@react-pdf/renderer';
import {
  CalendarEvent,
  CalendarCell,
  MonthData,
  SchoolYearConfig,
} from '../calendar/types';
import {
  MONTH_NAMES,
  generateMonthCells,
  getSchoolYearMonths,
  DEFAULT_SCHOOL_YEAR_CONFIG,
  formatDateShort,
  formatDateRange,
  parseDate,
} from '../calendar/utils';

// Color constants - matching WeasyPrint CSS
const PTSA_RED = '#C40A0C';
const GREY_BG = '#ddd';  // Lighter grey for half-day cells
const LIGHT_GREY = '#d9d9d9';  // Was #e5e5e5
const WEEKEND_COLOR = '#999';  // Was #888888
const CELL_BORDER = '#ddd';
const DISTRICT_TEXT = '#555';
const FOOTER_COLOR = '#888';  // Was #666
const DAY_HEADER_COLOR = '#666';

// Create styles - matching WeasyPrint CSS values
const styles = StyleSheet.create({
  page: {
    padding: 18,  // Was 14, matching WeasyPrint 18pt margin
    fontFamily: 'Helvetica',
    fontSize: 7.5,  // Was 7, matching WeasyPrint 7.5pt
  },
  header: {
    paddingTop: 6,
    paddingBottom: 8,
    marginBottom: 8,
  },
  title: {
    fontSize: 12,  // Was 14, matching WeasyPrint 12pt
    fontWeight: 'bold',
  },
  titleAccent: {
    color: PTSA_RED,
  },
  calendarGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  // Month container - 3 columns (33.33%) instead of 4 (25%)
  monthContainer: {
    width: '32.5%',  // Was 25%, matching WeasyPrint 32.5%
    marginBottom: 6,
  },
  monthName: {
    textAlign: 'center',
    fontSize: 7,  // Was 8, matching WeasyPrint 7pt
    fontWeight: 'bold',
    marginBottom: 2,  // Was 3, matching WeasyPrint 2pt
    paddingVertical: 2,
    paddingHorizontal: 4,
  },
  dayNamesRow: {
    flexDirection: 'row',
    borderBottomWidth: 0.5,  // Added underline
    borderBottomColor: CELL_BORDER,
    marginBottom: 1,
  },
  dayName: {
    width: '14.28%',
    textAlign: 'center',
    fontSize: 5.5,  // Was 5, matching WeasyPrint 5.5pt
    fontWeight: 'bold',
    color: DAY_HEADER_COLOR,  // Added grey color
    paddingBottom: 2,
  },
  weekRow: {
    flexDirection: 'row',
  },
  dayCell: {
    width: '14.28%',
    height: 11,  // Back to 11pt to fit on single page
    justifyContent: 'center',
    alignItems: 'center',
    position: 'relative',
    borderWidth: 0.5,  // Was 0.25, matching WeasyPrint 0.5pt
    borderColor: CELL_BORDER,
  },
  dayText: {
    fontSize: 6.5,  // Was 6, matching WeasyPrint 6.5pt
    textAlign: 'center',
    fontWeight: 'light',  // Added to increase contrast with bold
  },
  dayTextBold: {
    fontSize: 6.5,
    textAlign: 'center',
    fontWeight: 'heavy',  // font-weight: 900 in CSS
  },
  dayTextWhite: {
    fontSize: 6.5,
    textAlign: 'center',
    color: '#fff',
    fontWeight: 'light',  // Added for consistency
  },
  dayTextWeekend: {
    fontSize: 6.5,
    textAlign: 'center',
    color: WEEKEND_COLOR,
    fontWeight: 'light',  // Added for consistency
  },
  // Legend - matching WeasyPrint
  legend: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 4,  // Was 8, matching WeasyPrint 4pt
    marginBottom: 4,  // Was 8
    paddingVertical: 6,
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: 10,
  },
  // Legend chip - 6pt box with black border (matching WeasyPrint)
  legendChip: {
    width: 6,  // Was 12
    height: 6,
    borderWidth: 0.5,
    borderColor: '#000',
    marginRight: 3,
  },
  legendText: {
    fontSize: 6.5,  // Was 6, matching WeasyPrint 6.5pt
  },
  // Important dates - 2 columns (matching WeasyPrint)
  importantDates: {
    paddingTop: 4,  // Removed flex: 1 to prevent expansion
  },
  importantDatesColumns: {
    flexDirection: 'row',
  },
  importantDatesColumn: {
    width: '50%',  // Was 25%, matching WeasyPrint 2-column layout
    paddingHorizontal: 8,
  },
  importantDateItem: {
    flexDirection: 'row',
    paddingVertical: 0.5,  // Reduced from 1 for tighter spacing
    paddingHorizontal: 2,
  },
  ptsaBar: {
    width: 1.5,  // Was 2, matching WeasyPrint 1.5pt
    backgroundColor: PTSA_RED,
    marginRight: 3,
  },
  importantDateText: {
    fontSize: 6.5,  // Was 5.5, matching WeasyPrint 6.5pt
    flex: 1,
    color: DISTRICT_TEXT,  // Grey for district events
    lineHeight: 1.2,  // Added to match WeasyPrint
  },
  importantDateTextPtsa: {
    fontSize: 6.5,
    color: PTSA_RED,
    flex: 1,
    lineHeight: 1.2,  // Added to match WeasyPrint
  },
  importantDateWhen: {
    fontWeight: 'bold',
  },
  // Footer - matching WeasyPrint
  footer: {
    position: 'absolute',
    bottom: 18,
    left: 18,
    right: 18,
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    fontSize: 5.5,  // Was 5
    color: FOOTER_COLOR,
    paddingTop: 6,
    marginTop: 6,
  },
});

// Day names - title case (Su, Mo, Tu...) matching WeasyPrint
const DAY_NAMES = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

interface CalendarPdfProps {
  events: CalendarEvent[];
  schoolYear?: number;
  config?: SchoolYearConfig;
}

export function CalendarPdf({
  events,
  schoolYear = 2025,
  config = DEFAULT_SCHOOL_YEAR_CONFIG,
}: CalendarPdfProps) {
  const monthRefs = getSchoolYearMonths(schoolYear);
  const months: MonthData[] = monthRefs.map(({ year, month }) => ({
    name: MONTH_NAMES[month],
    year,
    month,
    cells: generateMonthCells(year, month, events, config),
  }));

  const importantDates = generateImportantDates(events);

  // Split important dates into 2 columns (matching WeasyPrint)
  const half = Math.ceil((importantDates.length + 1) / 2);
  const columns = [
    importantDates.slice(0, half),
    importantDates.slice(half),
  ];

  // Format date for footer
  const now = new Date();
  const footerDate = `${now.toLocaleString('en-US', { month: 'short' })} ${String(now.getDate()).padStart(2, '0')}, ${now.getFullYear()}`;

  return (
    <Document>
      <Page size="LETTER" style={styles.page}>
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>
            Horace Mann <Text style={styles.titleAccent}>PTSA</Text> | {schoolYear}-{String((schoolYear + 1) % 100).padStart(2, '0')} Calendar
          </Text>
        </View>

        {/* Calendar Grid - 3 columns x 4 rows (matching WeasyPrint) */}
        <View style={styles.calendarGrid}>
          {months.map((month) => (
            <MonthView key={`${month.year}-${month.month}`} month={month} />
          ))}
        </View>

        {/* Legend - matching WeasyPrint structure */}
        <View style={styles.legend}>
          {/* No School - black chip */}
          <View style={styles.legendItem}>
            <View style={[styles.legendChip, { backgroundColor: '#000' }]} />
            <Text style={styles.legendText}>No School</Text>
          </View>
          {/* Half Day - grey chip */}
          <View style={styles.legendItem}>
            <View style={[styles.legendChip, { backgroundColor: GREY_BG }]} />
            <Text style={styles.legendText}>Half Day</Text>
          </View>
          {/* Make-up - striped chip */}
          <View style={styles.legendItem}>
            <StripedChip />
            <Text style={styles.legendText}>Make-up</Text>
          </View>
          {/* First/Last - diamond box with "1" */}
          <View style={styles.legendItem}>
            <View style={{ borderWidth: 0.75, borderColor: '#000', paddingHorizontal: 1, marginRight: 3 }}>
              <Text style={{ fontSize: 5, fontWeight: 'bold' }}>1</Text>
            </View>
            <Text style={styles.legendText}>First/Last</Text>
          </View>
          {/* PTSA - circle with "1" inside */}
          <View style={styles.legendItem}>
            <View style={{ width: 12, height: 12, marginRight: 3, position: 'relative' }}>
              <Svg width={12} height={12} viewBox="0 0 12 12" style={{ position: 'absolute' }}>
                <Circle cx="6" cy="6" r="5" stroke={PTSA_RED} strokeWidth="1" fill="none" />
              </Svg>
              <Text style={{ position: 'absolute', width: 12, height: 12, textAlign: 'center', fontSize: 5, lineHeight: 12 }}>1</Text>
            </View>
            <Text style={styles.legendText}>PTSA</Text>
          </View>
          {/* Early Release - Bold text */}
          <View style={styles.legendItem}>
            <Text style={{ fontWeight: 'heavy', fontSize: 6.5, marginRight: 3 }}>Bold</Text>
            <Text style={styles.legendText}>=Early Release</Text>
          </View>
          {/* Asterisk */}
          <View style={styles.legendItem}>
            <Text style={{ fontWeight: 'bold', fontSize: 7, marginRight: 3 }}>*</Text>
            <Text style={styles.legendText}>=See Dates</Text>
          </View>
        </View>

        {/* Important Dates - 2 columns (matching WeasyPrint) */}
        <View style={styles.importantDates}>
          <View style={styles.importantDatesColumns}>
            {columns.map((column, colIndex) => (
              <View key={colIndex} style={styles.importantDatesColumn}>
                {column.map((date, i) => (
                  <View key={i} style={[
                    styles.importantDateItem,
                    date.isPtsa ? { borderLeftWidth: 1.5, borderLeftColor: PTSA_RED, paddingLeft: 3 } : {}
                  ]}>
                    <Text style={date.isPtsa ? styles.importantDateTextPtsa : styles.importantDateText}>
                      <Text style={styles.importantDateWhen}>{date.when}</Text> {date.label}
                    </Text>
                  </View>
                ))}
              </View>
            ))}
          </View>
        </View>

        {/* Footer - matching WeasyPrint content */}
        <View style={styles.footer}>
          <Text>Updated {footerDate}</Text>
          <Text style={{ color: '#aaa', marginHorizontal: 4 }}>|</Text>
          <Text>Calendar subject to change</Text>
          <Text style={{ color: '#aaa', marginHorizontal: 4 }}>|</Text>
          <Text>School year may extend due to weather closures</Text>
        </View>
      </Page>
    </Document>
  );
}

// Striped chip for legend (6pt box with diagonal stripes)
function StripedChip() {
  return (
    <Svg width={6} height={6} viewBox="0 0 6 6" style={{ marginRight: 3, borderWidth: 0.5, borderColor: '#000' }}>
      <Rect x="0" y="0" width="6" height="6" fill={LIGHT_GREY} />
      {/* Diagonal stripes going \ (top-left to bottom-right) */}
      <Line x1="-1" y1="-1" x2="2" y2="2" stroke="#fff" strokeWidth="0.75" />
      <Line x1="1" y1="-1" x2="4" y2="2" stroke="#fff" strokeWidth="0.75" />
      <Line x1="3" y1="-1" x2="6" y2="2" stroke="#fff" strokeWidth="0.75" />
      <Line x1="5" y1="-1" x2="8" y2="2" stroke="#fff" strokeWidth="0.75" />
      <Line x1="-1" y1="1" x2="2" y2="4" stroke="#fff" strokeWidth="0.75" />
      <Line x1="-1" y1="3" x2="2" y2="6" stroke="#fff" strokeWidth="0.75" />
      <Line x1="-1" y1="5" x2="2" y2="8" stroke="#fff" strokeWidth="0.75" />
    </Svg>
  );
}

// Month view component
function MonthView({ month }: { month: MonthData }) {
  const weeks: (CalendarCell | null)[][] = [];
  for (let i = 0; i < month.cells.length; i += 7) {
    weeks.push(month.cells.slice(i, i + 7));
  }

  return (
    <View style={styles.monthContainer}>
      <Text style={styles.monthName}>{month.name} {month.year}</Text>

      {/* Day names */}
      <View style={styles.dayNamesRow}>
        {DAY_NAMES.map((day) => (
          <Text key={day} style={styles.dayName}>
            {day}
          </Text>
        ))}
      </View>

      {/* Weeks */}
      {weeks.map((week, weekIndex) => (
        <View key={weekIndex} style={styles.weekRow}>
          {week.map((cell, dayIndex) => (
            <DayCell key={dayIndex} cell={cell} />
          ))}
        </View>
      ))}
    </View>
  );
}

// Day cell component with proper indicators
function DayCell({ cell }: { cell: CalendarCell | null }) {
  if (!cell) {
    return <View style={styles.dayCell} />;
  }

  const { day, marks, isWeekend, hasDiamond, hasCircle, showAsterisk } = cell;

  const isNoSchool = marks.includes('no_school');
  const isHalfDay = marks.includes('half_day');
  const isClosure = marks.includes('closure_possible');
  const isEarlyRelease = marks.includes('early_release');
  const isPtsa = marks.includes('ptsa_event');

  // Background color
  let bgColor = 'transparent';
  if (isNoSchool) bgColor = '#000';
  else if (isHalfDay) bgColor = GREY_BG;

  // Text style
  let textStyle = styles.dayText;
  if (isNoSchool) textStyle = styles.dayTextWhite;
  else if (isWeekend) textStyle = styles.dayTextWeekend;
  else if (isEarlyRelease && !isPtsa) textStyle = styles.dayTextBold;

  // For half-day, show solid grey background using SVG for edge-to-edge fill
  if (isHalfDay && !isNoSchool && !isClosure) {
    return (
      <View style={styles.dayCell}>
        <Svg width="100%" height="100%" viewBox="0 0 20 11" style={{ position: 'absolute' }} preserveAspectRatio="none">
          <Rect x="0" y="0" width="20" height="11" fill={GREY_BG} />
        </Svg>
        {hasDiamond && (
          <Svg width="100%" height="100%" viewBox="0 0 20 11" style={{ position: 'absolute' }} preserveAspectRatio="none">
            <Rect x="4" y="1" width="12" height="9" stroke="#000" strokeWidth="0.75" fill="none" />
          </Svg>
        )}
        {hasCircle && (
          <Svg width="100%" height="100%" viewBox="0 0 20 11" style={{ position: 'absolute' }} preserveAspectRatio="none">
            <Circle cx="10" cy="5.5" r="5" stroke={PTSA_RED} strokeWidth="1" fill="none" />
          </Svg>
        )}
        <Text style={hasDiamond ? { ...textStyle, fontWeight: 'bold' } : (isEarlyRelease ? styles.dayTextBold : textStyle)}>{day}{showAsterisk ? '*' : ''}</Text>
      </View>
    );
  }

  // For closure/make-up days, show striped pattern with extended lines
  if (isClosure && !isNoSchool && !isHalfDay) {
    return (
      <View style={styles.dayCell}>
        <Svg width="100%" height="100%" viewBox="0 0 20 11" style={{ position: 'absolute' }} preserveAspectRatio="none">
          <Rect x="0" y="0" width="20" height="11" fill={LIGHT_GREY} />
          {/* Diagonal stripes going \ (top-left to bottom-right) every 3 units */}
          <Line x1="-10" y1="-10" x2="3" y2="3" stroke="#fff" strokeWidth="1.5" />
          <Line x1="-7" y1="-10" x2="6" y2="3" stroke="#fff" strokeWidth="1.5" />
          <Line x1="-4" y1="-10" x2="9" y2="3" stroke="#fff" strokeWidth="1.5" />
          <Line x1="-1" y1="-10" x2="12" y2="3" stroke="#fff" strokeWidth="1.5" />
          <Line x1="2" y1="-10" x2="15" y2="3" stroke="#fff" strokeWidth="1.5" />
          <Line x1="5" y1="-10" x2="18" y2="3" stroke="#fff" strokeWidth="1.5" />
          <Line x1="8" y1="-10" x2="21" y2="3" stroke="#fff" strokeWidth="1.5" />
          <Line x1="11" y1="-10" x2="24" y2="3" stroke="#fff" strokeWidth="1.5" />
          <Line x1="14" y1="-10" x2="27" y2="3" stroke="#fff" strokeWidth="1.5" />
          <Line x1="17" y1="-10" x2="30" y2="3" stroke="#fff" strokeWidth="1.5" />
          <Line x1="-10" y1="-7" x2="3" y2="6" stroke="#fff" strokeWidth="1.5" />
          <Line x1="-10" y1="-4" x2="3" y2="9" stroke="#fff" strokeWidth="1.5" />
          <Line x1="-10" y1="-1" x2="3" y2="12" stroke="#fff" strokeWidth="1.5" />
          <Line x1="-10" y1="2" x2="3" y2="15" stroke="#fff" strokeWidth="1.5" />
          <Line x1="-10" y1="5" x2="3" y2="18" stroke="#fff" strokeWidth="1.5" />
          <Line x1="-10" y1="8" x2="3" y2="21" stroke="#fff" strokeWidth="1.5" />
        </Svg>
        <Text style={textStyle}>{day}{showAsterisk ? '*' : ''}</Text>
      </View>
    );
  }

  // For PTSA events, show circle (12pt diameter)
  if (hasCircle && !isNoSchool) {
    return (
      <View style={[styles.dayCell, { backgroundColor: bgColor }]}>
        <Svg width="100%" height="100%" viewBox="0 0 20 11" style={{ position: 'absolute' }}>
          <Circle cx="10" cy="5.5" r="5" stroke={PTSA_RED} strokeWidth="1" fill="none" />
        </Svg>
        <Text style={isEarlyRelease ? styles.dayTextBold : styles.dayText}>{day}</Text>
      </View>
    );
  }

  // For first/last days, show square box around number
  if (hasDiamond && !isNoSchool) {
    return (
      <View style={[styles.dayCell, { backgroundColor: bgColor }]}>
        <Svg width="100%" height="100%" viewBox="0 0 20 11" style={{ position: 'absolute' }}>
          <Rect x="4" y="1" width="12" height="9" stroke="#000" strokeWidth="0.75" fill="none" />
        </Svg>
        <Text style={{ ...textStyle, fontWeight: 'bold' }}>{day}{showAsterisk ? '*' : ''}</Text>
      </View>
    );
  }

  return (
    <View style={[styles.dayCell, { backgroundColor: bgColor }]}>
      <Text style={textStyle}>{day}{showAsterisk ? '*' : ''}</Text>
    </View>
  );
}

// Generate important dates from events
interface ImportantDate {
  when: string;
  label: string;
  isPtsa: boolean;
  sortDate: Date;
}

function generateImportantDates(events: CalendarEvent[]): ImportantDate[] {
  const dates: ImportantDate[] = [];

  for (const event of events) {
    if (event.type === 'early_release') continue;

    const isPtsa = event.type === 'ptsa_event';
    let when: string;
    let sortDate: Date;

    if (event.date) {
      sortDate = parseDate(event.date);
      when = formatDateShort(sortDate);
    } else if (event.startDate && event.endDate) {
      sortDate = parseDate(event.startDate);
      when = formatDateRange(parseDate(event.startDate), parseDate(event.endDate));
    } else {
      continue;
    }

    dates.push({
      when,
      label: isPtsa ? `PTSA: ${event.label}` : event.label,
      isPtsa,
      sortDate,
    });
  }

  dates.sort((a, b) => a.sortDate.getTime() - b.sortDate.getTime());
  return dates;
}
