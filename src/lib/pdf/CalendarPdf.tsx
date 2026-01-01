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

// Color constants
const PTSA_RED = '#C40A0C';
const GREY_BG = '#cccccc';
const LIGHT_GREY = '#e5e5e5';
const WEEKEND_COLOR = '#888888';
const CELL_BORDER = '#ddd';

// Create styles
const styles = StyleSheet.create({
  page: {
    padding: 14,
    fontFamily: 'Helvetica',
    fontSize: 7,
  },
  header: {
    marginBottom: 8,
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
    paddingHorizontal: 3,
    paddingVertical: 2,
  },
  monthName: {
    textAlign: 'center',
    fontSize: 8,
    fontWeight: 'bold',
    marginBottom: 3,
  },
  dayNamesRow: {
    flexDirection: 'row',
  },
  dayName: {
    width: '14.28%',
    textAlign: 'center',
    fontSize: 5,
    fontWeight: 'bold',
    paddingBottom: 2,
  },
  weekRow: {
    flexDirection: 'row',
  },
  dayCell: {
    width: '14.28%',
    height: 12,
    justifyContent: 'center',
    alignItems: 'center',
    position: 'relative',
    borderWidth: 0.25,
    borderColor: CELL_BORDER,
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
  // Legend
  legend: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 8,
    marginBottom: 8,
    paddingVertical: 6,
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: 10,
  },
  legendBox: {
    width: 12,
    height: 12,
    marginRight: 4,
    justifyContent: 'center',
    alignItems: 'center',
  },
  legendText: {
    fontSize: 6,
  },
  // Important dates
  importantDates: {
    flex: 1,
    marginTop: 4,
  },
  importantDatesColumns: {
    flexDirection: 'row',
  },
  importantDatesColumn: {
    width: '25%',
    paddingHorizontal: 4,
  },
  importantDateItem: {
    flexDirection: 'row',
    marginBottom: 3,
  },
  ptsaBar: {
    width: 2,
    backgroundColor: PTSA_RED,
    marginRight: 3,
  },
  importantDateText: {
    fontSize: 5.5,
    flex: 1,
  },
  importantDateTextPtsa: {
    fontSize: 5.5,
    color: PTSA_RED,
    flex: 1,
  },
  // Footer
  footer: {
    position: 'absolute',
    bottom: 10,
    left: 14,
    right: 14,
    flexDirection: 'row',
    justifyContent: 'space-between',
    fontSize: 5,
    color: '#666',
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
              <Text style={{ color: '#fff', fontSize: 6 }}>1</Text>
            </View>
            <Text style={styles.legendText}>No School</Text>
          </View>
          <View style={styles.legendItem}>
            <View style={[styles.legendBox, { backgroundColor: GREY_BG }]}>
              <Text style={{ fontSize: 6 }}>1</Text>
            </View>
            <Text style={styles.legendText}>Half Day</Text>
          </View>
          <View style={styles.legendItem}>
            <View style={styles.legendBox}>
              <Text style={{ fontSize: 6, fontWeight: 'bold' }}>1</Text>
            </View>
            <Text style={styles.legendText}>Early Release</Text>
          </View>
          <View style={styles.legendItem}>
            <Svg width={14} height={14} viewBox="0 0 14 14">
              <Circle cx="7" cy="7" r="6" stroke={PTSA_RED} strokeWidth="1" fill="none" />
            </Svg>
            <Text style={[styles.legendText, { marginLeft: 4 }]}>PTSA Event</Text>
          </View>
          <View style={styles.legendItem}>
            <Svg width={14} height={14} viewBox="0 0 14 14">
              <Rect x="1" y="1" width="12" height="12" stroke="#000" strokeWidth="1" fill="none" />
            </Svg>
            <Text style={[styles.legendText, { marginLeft: 4 }]}>First/Last Day</Text>
          </View>
          <View style={styles.legendItem}>
            <StripedBox />
            <Text style={[styles.legendText, { marginLeft: 4 }]}>Make-up Day</Text>
          </View>
          <View style={styles.legendItem}>
            <Text style={{ fontSize: 8 }}>*</Text>
            <Text style={[styles.legendText, { marginLeft: 2 }]}>=See Dates</Text>
          </View>
        </View>

        {/* Important Dates */}
        <View style={styles.importantDates}>
          <View style={styles.importantDatesColumns}>
            {columns.map((column, colIndex) => (
              <View key={colIndex} style={styles.importantDatesColumn}>
                {column.map((date, i) => (
                  <View key={i} style={styles.importantDateItem}>
                    {date.isPtsa && <View style={styles.ptsaBar} />}
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

// Striped box for make-up days (light grey and white stripes)
function StripedBox() {
  return (
    <Svg width={14} height={14} viewBox="0 0 14 14">
      <Rect x="0" y="0" width="14" height="14" fill={LIGHT_GREY} />
      <Line x1="0" y1="2" x2="2" y2="0" stroke="#fff" strokeWidth="1" />
      <Line x1="0" y1="5" x2="5" y2="0" stroke="#fff" strokeWidth="1" />
      <Line x1="0" y1="8" x2="8" y2="0" stroke="#fff" strokeWidth="1" />
      <Line x1="0" y1="11" x2="11" y2="0" stroke="#fff" strokeWidth="1" />
      <Line x1="0" y1="14" x2="14" y2="0" stroke="#fff" strokeWidth="1" />
      <Line x1="3" y1="14" x2="14" y2="3" stroke="#fff" strokeWidth="1" />
      <Line x1="6" y1="14" x2="14" y2="6" stroke="#fff" strokeWidth="1" />
      <Line x1="9" y1="14" x2="14" y2="9" stroke="#fff" strokeWidth="1" />
      <Line x1="12" y1="14" x2="14" y2="12" stroke="#fff" strokeWidth="1" />
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

  // For closure/make-up days, show striped pattern (light grey + white)
  if (isClosure && !isNoSchool && !isHalfDay) {
    return (
      <View style={styles.dayCell}>
        <Svg width="100%" height="100%" viewBox="0 0 20 12" style={{ position: 'absolute' }}>
          <Rect x="0" y="0" width="20" height="12" fill={LIGHT_GREY} />
          <Line x1="0" y1="2" x2="2" y2="0" stroke="#fff" strokeWidth="1" />
          <Line x1="0" y1="5" x2="5" y2="0" stroke="#fff" strokeWidth="1" />
          <Line x1="0" y1="8" x2="8" y2="0" stroke="#fff" strokeWidth="1" />
          <Line x1="0" y1="11" x2="11" y2="0" stroke="#fff" strokeWidth="1" />
          <Line x1="2" y1="12" x2="14" y2="0" stroke="#fff" strokeWidth="1" />
          <Line x1="5" y1="12" x2="17" y2="0" stroke="#fff" strokeWidth="1" />
          <Line x1="8" y1="12" x2="20" y2="0" stroke="#fff" strokeWidth="1" />
          <Line x1="11" y1="12" x2="20" y2="3" stroke="#fff" strokeWidth="1" />
          <Line x1="14" y1="12" x2="20" y2="6" stroke="#fff" strokeWidth="1" />
          <Line x1="17" y1="12" x2="20" y2="9" stroke="#fff" strokeWidth="1" />
        </Svg>
        <Text style={textStyle}>{day}</Text>
        {showAsterisk && <Text style={{ position: 'absolute', top: 0, right: 1, fontSize: 5 }}>*</Text>}
      </View>
    );
  }

  // For PTSA events, show circle
  if (hasCircle && !isNoSchool) {
    return (
      <View style={[styles.dayCell, { backgroundColor: bgColor }]}>
        <Svg width="100%" height="100%" viewBox="0 0 20 12" style={{ position: 'absolute' }}>
          <Circle cx="10" cy="6" r="5.5" stroke={PTSA_RED} strokeWidth="1" fill="none" />
        </Svg>
        <Text style={isEarlyRelease ? styles.dayTextBold : styles.dayText}>{day}</Text>
      </View>
    );
  }

  // For first/last days, show SQUARE (not diamond)
  if (hasDiamond && !isNoSchool) {
    return (
      <View style={[styles.dayCell, { backgroundColor: bgColor }]}>
        <Svg width="100%" height="100%" viewBox="0 0 20 12" style={{ position: 'absolute' }}>
          <Rect x="3" y="0.5" width="14" height="11" stroke="#000" strokeWidth="0.75" fill="none" />
        </Svg>
        <Text style={textStyle}>{day}</Text>
        {showAsterisk && <Text style={{ position: 'absolute', top: 0, right: 1, fontSize: 5 }}>*</Text>}
      </View>
    );
  }

  return (
    <View style={[styles.dayCell, { backgroundColor: bgColor }]}>
      <Text style={textStyle}>{day}</Text>
      {showAsterisk && <Text style={{ position: 'absolute', top: 0, right: 1, fontSize: 5 }}>*</Text>}
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
