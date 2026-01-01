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
  G,
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

// Color constants
const PTSA_RED = '#C40A0C';
const BORDER_COLOR = '#000';
const GREY_BG = '#cccccc';
const LIGHT_GREY = '#d9d9d9';
const WEEKEND_COLOR = '#888888';

// Create styles
const styles = StyleSheet.create({
  page: {
    padding: 12,
    fontFamily: 'Helvetica',
    fontSize: 7,
  },
  header: {
    marginBottom: 6,
  },
  title: {
    fontSize: 14,
    fontWeight: 'bold',
  },
  titleAccent: {
    color: PTSA_RED,
  },
  calendarGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  monthContainer: {
    width: '25%',
    padding: 2,
  },
  monthInner: {
    border: `0.5pt solid ${BORDER_COLOR}`,
    padding: 2,
  },
  monthName: {
    textAlign: 'center',
    fontSize: 8,
    fontWeight: 'bold',
    marginBottom: 2,
    backgroundColor: '#f0f0f0',
    padding: 1,
  },
  dayNamesRow: {
    flexDirection: 'row',
    borderBottom: `0.5pt solid ${BORDER_COLOR}`,
    marginBottom: 1,
  },
  dayName: {
    width: '14.28%',
    textAlign: 'center',
    fontSize: 5,
    fontWeight: 'bold',
    paddingBottom: 1,
  },
  weekRow: {
    flexDirection: 'row',
  },
  dayCell: {
    width: '14.28%',
    height: 11,
    justifyContent: 'center',
    alignItems: 'center',
    position: 'relative',
  },
  dayText: {
    fontSize: 6,
    textAlign: 'center',
  },
  dayTextBold: {
    fontSize: 6,
    textAlign: 'center',
    fontWeight: 'bold',
  },
  dayTextWhite: {
    fontSize: 6,
    textAlign: 'center',
    color: '#fff',
  },
  dayTextWeekend: {
    fontSize: 6,
    textAlign: 'center',
    color: WEEKEND_COLOR,
  },
  dayTextRed: {
    fontSize: 6,
    textAlign: 'center',
    color: PTSA_RED,
  },
  // Legend
  legend: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 4,
    marginBottom: 4,
    paddingTop: 4,
    borderTop: `0.5pt solid ${BORDER_COLOR}`,
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: 6,
  },
  legendBox: {
    width: 10,
    height: 10,
    marginRight: 2,
    justifyContent: 'center',
    alignItems: 'center',
  },
  legendText: {
    fontSize: 5,
  },
  // Important dates
  importantDates: {
    marginTop: 2,
  },
  importantDatesColumns: {
    flexDirection: 'row',
  },
  importantDatesColumn: {
    width: '25%',
    paddingHorizontal: 2,
  },
  importantDateItem: {
    marginBottom: 1,
  },
  importantDateText: {
    fontSize: 5,
  },
  importantDateTextPtsa: {
    fontSize: 5,
    color: PTSA_RED,
  },
  // Footer
  footer: {
    position: 'absolute',
    bottom: 8,
    left: 12,
    right: 12,
    flexDirection: 'row',
    justifyContent: 'space-between',
    fontSize: 5,
    color: '#666',
    borderTop: `0.5pt solid #ccc`,
    paddingTop: 4,
  },
});

const DAY_NAMES = ['SU', 'MO', 'TU', 'WE', 'TH', 'FR', 'SA'];

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

  // Split important dates into 4 columns
  const columnSize = Math.ceil(importantDates.length / 4);
  const columns = [
    importantDates.slice(0, columnSize),
    importantDates.slice(columnSize, columnSize * 2),
    importantDates.slice(columnSize * 2, columnSize * 3),
    importantDates.slice(columnSize * 3),
  ];

  return (
    <Document>
      <Page size="LETTER" style={styles.page}>
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>
            Horace Mann <Text style={styles.titleAccent}>PTSA</Text> | {schoolYear}-{(schoolYear + 1) % 100} Calendar
          </Text>
        </View>

        {/* Calendar Grid - 4 columns x 3 rows */}
        <View style={styles.calendarGrid}>
          {months.map((month) => (
            <MonthView key={`${month.year}-${month.month}`} month={month} />
          ))}
        </View>

        {/* Legend */}
        <View style={styles.legend}>
          <View style={styles.legendItem}>
            <View style={[styles.legendBox, { backgroundColor: '#000' }]}>
              <Text style={{ color: '#fff', fontSize: 5 }}>1</Text>
            </View>
            <Text style={styles.legendText}>No School</Text>
          </View>
          <View style={styles.legendItem}>
            <View style={[styles.legendBox, { backgroundColor: GREY_BG }]}>
              <Text style={{ fontSize: 5 }}>1</Text>
            </View>
            <Text style={styles.legendText}>Half Day</Text>
          </View>
          <View style={styles.legendItem}>
            <View style={styles.legendBox}>
              <Text style={{ fontSize: 5, fontWeight: 'bold' }}>1</Text>
            </View>
            <Text style={styles.legendText}>Early Release</Text>
          </View>
          <View style={styles.legendItem}>
            <Svg width={12} height={12} viewBox="0 0 12 12">
              <Circle cx="6" cy="6" r="5" stroke={PTSA_RED} strokeWidth="1" fill="none" />
              <Text x="6" y="8" style={{ fontSize: 5 }} textAnchor="middle">1</Text>
            </Svg>
            <Text style={styles.legendText}>PTSA Event</Text>
          </View>
          <View style={styles.legendItem}>
            <Svg width={12} height={12} viewBox="0 0 12 12">
              <Rect x="2" y="2" width="8" height="8" stroke="#000" strokeWidth="1" fill="none" transform="rotate(45 6 6)" />
            </Svg>
            <Text style={styles.legendText}>First/Last Day</Text>
          </View>
          <View style={styles.legendItem}>
            <StripedBox />
            <Text style={styles.legendText}>Make-up Day</Text>
          </View>
        </View>

        {/* Important Dates */}
        <View style={styles.importantDates}>
          <View style={styles.importantDatesColumns}>
            {columns.map((column, colIndex) => (
              <View key={colIndex} style={styles.importantDatesColumn}>
                {column.map((date, i) => (
                  <View key={i} style={styles.importantDateItem}>
                    <Text style={date.isPtsa ? styles.importantDateTextPtsa : styles.importantDateText}>
                      {date.when} {date.label}
                    </Text>
                  </View>
                ))}
              </View>
            ))}
          </View>
        </View>

        {/* Footer */}
        <View style={styles.footer}>
          <Text>* See district calendar for details</Text>
          <Text>horacemann.my.lwsd.org</Text>
          <Text>Generated {new Date().toLocaleDateString()}</Text>
        </View>
      </Page>
    </Document>
  );
}

// Striped box for make-up days
function StripedBox() {
  return (
    <Svg width={12} height={12} viewBox="0 0 12 12" style={{ marginRight: 2 }}>
      <Rect x="0" y="0" width="12" height="12" fill={LIGHT_GREY} />
      <G>
        <Line x1="0" y1="3" x2="3" y2="0" stroke="#999" strokeWidth="0.5" />
        <Line x1="0" y1="6" x2="6" y2="0" stroke="#999" strokeWidth="0.5" />
        <Line x1="0" y1="9" x2="9" y2="0" stroke="#999" strokeWidth="0.5" />
        <Line x1="0" y1="12" x2="12" y2="0" stroke="#999" strokeWidth="0.5" />
        <Line x1="3" y1="12" x2="12" y2="3" stroke="#999" strokeWidth="0.5" />
        <Line x1="6" y1="12" x2="12" y2="6" stroke="#999" strokeWidth="0.5" />
        <Line x1="9" y1="12" x2="12" y2="9" stroke="#999" strokeWidth="0.5" />
      </G>
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
      <View style={styles.monthInner}>
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
    </View>
  );
}

// Day cell component with proper indicators
function DayCell({ cell }: { cell: CalendarCell | null }) {
  if (!cell) {
    return <View style={styles.dayCell} />;
  }

  const { day, marks, isWeekend, hasDiamond, hasCircle } = cell;

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

  // For closure/make-up days, show striped pattern
  if (isClosure && !isNoSchool && !isHalfDay) {
    return (
      <View style={styles.dayCell}>
        <Svg width="100%" height="100%" viewBox="0 0 20 11" style={{ position: 'absolute' }}>
          <Rect x="0" y="0" width="20" height="11" fill={LIGHT_GREY} />
          <Line x1="0" y1="3" x2="3" y2="0" stroke="#aaa" strokeWidth="0.5" />
          <Line x1="0" y1="6" x2="6" y2="0" stroke="#aaa" strokeWidth="0.5" />
          <Line x1="0" y1="9" x2="9" y2="0" stroke="#aaa" strokeWidth="0.5" />
          <Line x1="0" y1="11" x2="11" y2="0" stroke="#aaa" strokeWidth="0.5" />
          <Line x1="3" y1="11" x2="14" y2="0" stroke="#aaa" strokeWidth="0.5" />
          <Line x1="6" y1="11" x2="17" y2="0" stroke="#aaa" strokeWidth="0.5" />
          <Line x1="9" y1="11" x2="20" y2="0" stroke="#aaa" strokeWidth="0.5" />
          <Line x1="12" y1="11" x2="20" y2="3" stroke="#aaa" strokeWidth="0.5" />
          <Line x1="15" y1="11" x2="20" y2="6" stroke="#aaa" strokeWidth="0.5" />
          <Line x1="18" y1="11" x2="20" y2="9" stroke="#aaa" strokeWidth="0.5" />
        </Svg>
        <Text style={textStyle}>{day}</Text>
      </View>
    );
  }

  // For PTSA events, show circle
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

  // For first/last days, show diamond
  if (hasDiamond && !isNoSchool) {
    return (
      <View style={[styles.dayCell, { backgroundColor: bgColor }]}>
        <Svg width="100%" height="100%" viewBox="0 0 20 11" style={{ position: 'absolute' }}>
          <Rect x="5" y="0.5" width="7" height="7" stroke="#000" strokeWidth="0.75" fill="none" transform="rotate(45 10 5.5)" />
        </Svg>
        <Text style={textStyle}>{day}</Text>
      </View>
    );
  }

  return (
    <View style={[styles.dayCell, { backgroundColor: bgColor }]}>
      <Text style={textStyle}>{day}</Text>
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
