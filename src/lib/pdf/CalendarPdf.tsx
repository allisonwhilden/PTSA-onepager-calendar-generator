'use client';

import {
  Document,
  Page,
  Text,
  View,
  StyleSheet,
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

// Create styles
const styles = StyleSheet.create({
  page: {
    padding: 18,
    fontFamily: 'Helvetica',
    fontSize: 8,
  },
  header: {
    marginBottom: 8,
    textAlign: 'center',
  },
  title: {
    fontSize: 16,
    fontWeight: 'bold',
  },
  titleAccent: {
    color: PTSA_RED,
  },
  calendarGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  monthContainer: {
    width: '24%',
    marginBottom: 6,
  },
  monthName: {
    textAlign: 'center',
    fontSize: 9,
    fontWeight: 'bold',
    marginBottom: 2,
  },
  dayNamesRow: {
    flexDirection: 'row',
  },
  dayName: {
    width: '14.28%',
    textAlign: 'center',
    fontSize: 6,
    color: '#666',
  },
  weekRow: {
    flexDirection: 'row',
  },
  dayCell: {
    width: '14.28%',
    height: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  dayCellNoSchool: {
    width: '14.28%',
    height: 12,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#000',
  },
  dayCellHalfDay: {
    width: '14.28%',
    height: 12,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#ccc',
  },
  dayCellClosure: {
    width: '14.28%',
    height: 12,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#d9d9d9',
  },
  dayText: {
    fontSize: 7,
    textAlign: 'center',
  },
  dayTextBold: {
    fontSize: 7,
    textAlign: 'center',
    fontWeight: 'bold',
  },
  dayTextWhite: {
    fontSize: 7,
    textAlign: 'center',
    color: '#fff',
  },
  dayTextWeekend: {
    fontSize: 7,
    textAlign: 'center',
    color: '#999',
  },
  legend: {
    flexDirection: 'row',
    justifyContent: 'center',
    flexWrap: 'wrap',
    marginTop: 6,
    marginBottom: 8,
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginRight: 12,
    marginBottom: 2,
  },
  legendIconNoSchool: {
    width: 10,
    height: 10,
    marginRight: 3,
    backgroundColor: '#000',
    justifyContent: 'center',
    alignItems: 'center',
  },
  legendIconHalfDay: {
    width: 10,
    height: 10,
    marginRight: 3,
    backgroundColor: '#ccc',
    justifyContent: 'center',
    alignItems: 'center',
  },
  legendIconClosure: {
    width: 10,
    height: 10,
    marginRight: 3,
    backgroundColor: '#d9d9d9',
    justifyContent: 'center',
    alignItems: 'center',
  },
  legendIconPtsa: {
    width: 10,
    height: 10,
    marginRight: 3,
    borderRadius: 5,
    borderWidth: 1,
    borderColor: PTSA_RED,
    justifyContent: 'center',
    alignItems: 'center',
  },
  legendIconFirstLast: {
    width: 10,
    height: 10,
    marginRight: 3,
    borderWidth: 1,
    borderColor: '#000',
    justifyContent: 'center',
    alignItems: 'center',
  },
  legendText: {
    fontSize: 6,
  },
  legendIconText: {
    fontSize: 5,
  },
  legendIconTextWhite: {
    fontSize: 5,
    color: '#fff',
  },
  legendIconTextBold: {
    fontSize: 5,
    fontWeight: 'bold',
  },
  importantDates: {
    marginTop: 8,
  },
  importantDatesList: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  importantDateItem: {
    width: '50%',
    flexDirection: 'row',
    marginBottom: 2,
  },
  importantDateLabel: {
    fontSize: 7,
  },
  importantDateLabelPtsa: {
    fontSize: 7,
    color: PTSA_RED,
  },
  footer: {
    position: 'absolute',
    bottom: 12,
    left: 18,
    right: 18,
    flexDirection: 'row',
    justifyContent: 'space-between',
    fontSize: 6,
    color: '#666',
  },
});

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
  // Generate month data
  const monthRefs = getSchoolYearMonths(schoolYear);
  const months: MonthData[] = monthRefs.map(({ year, month }) => ({
    name: MONTH_NAMES[month],
    year,
    month,
    cells: generateMonthCells(year, month, events, config),
  }));

  // Generate important dates list
  const importantDates = generateImportantDates(events);

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
            <View style={styles.legendIconNoSchool}>
              <Text style={styles.legendIconTextWhite}>1</Text>
            </View>
            <Text style={styles.legendText}>No School</Text>
          </View>
          <View style={styles.legendItem}>
            <View style={styles.legendIconHalfDay}>
              <Text style={styles.legendIconText}>1</Text>
            </View>
            <Text style={styles.legendText}>Half Day</Text>
          </View>
          <View style={styles.legendItem}>
            <View style={styles.dayCell}>
              <Text style={styles.legendIconTextBold}>1</Text>
            </View>
            <Text style={styles.legendText}>Early Release</Text>
          </View>
          <View style={styles.legendItem}>
            <View style={styles.legendIconPtsa}>
              <Text style={styles.legendIconText}>1</Text>
            </View>
            <Text style={styles.legendText}>PTSA Event</Text>
          </View>
          <View style={styles.legendItem}>
            <View style={styles.legendIconFirstLast}>
              <Text style={styles.legendIconText}>1</Text>
            </View>
            <Text style={styles.legendText}>First/Last Day</Text>
          </View>
          <View style={styles.legendItem}>
            <View style={styles.legendIconClosure}>
              <Text style={styles.legendIconText}>1</Text>
            </View>
            <Text style={styles.legendText}>Make-up Day</Text>
          </View>
        </View>

        {/* Important Dates */}
        <View style={styles.importantDates}>
          <View style={styles.importantDatesList}>
            {importantDates.map((date, i) => (
              <View key={i} style={styles.importantDateItem}>
                <Text style={date.isPtsa ? styles.importantDateLabelPtsa : styles.importantDateLabel}>
                  {date.when} - {date.label}
                </Text>
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

// Month view component
function MonthView({ month }: { month: MonthData }) {
  const weeks: (CalendarCell | null)[][] = [];
  for (let i = 0; i < month.cells.length; i += 7) {
    weeks.push(month.cells.slice(i, i + 7));
  }

  return (
    <View style={styles.monthContainer}>
      <Text style={styles.monthName}>{month.name}</Text>

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

// Day cell component
function DayCell({ cell }: { cell: CalendarCell | null }) {
  if (!cell) {
    return <View style={styles.dayCell} />;
  }

  const { day, marks, isWeekend } = cell;

  // Determine styles based on marks
  const isNoSchool = marks.includes('no_school');
  const isHalfDay = marks.includes('half_day');
  const isClosure = marks.includes('closure_possible');
  const isEarlyRelease = marks.includes('early_release');

  // Choose cell style
  let cellStyle = styles.dayCell;
  if (isNoSchool) {
    cellStyle = styles.dayCellNoSchool;
  } else if (isHalfDay) {
    cellStyle = styles.dayCellHalfDay;
  } else if (isClosure) {
    cellStyle = styles.dayCellClosure;
  }

  // Choose text style
  let textStyle = styles.dayText;
  if (isNoSchool) {
    textStyle = styles.dayTextWhite;
  } else if (isWeekend) {
    textStyle = styles.dayTextWeekend;
  } else if (isEarlyRelease) {
    textStyle = styles.dayTextBold;
  }

  return (
    <View style={cellStyle}>
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
    // Skip early release - auto-generated
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

  // Sort by date
  dates.sort((a, b) => a.sortDate.getTime() - b.sortDate.getTime());

  return dates;
}
