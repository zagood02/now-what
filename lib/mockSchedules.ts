export type DayCode =
  | "SUN"
  | "MON"
  | "TUE"
  | "WED"
  | "THU"
  | "FRI"
  | "SAT";

export type VariableSchedule = {
  id: string;
  user_id: string;
  title: string;
  estimated_time: number;
  is_done: boolean;
  level: number;
  deadline: string;
  scheduled_start: string | null;
  scheduled_end: string | null;
  fail_reason: string | null;
  priority: number | null;
  created_at: string | null;
  updated_at: string | null;
};

export type MonthRule = "START" | "MID" | "END" | "CUSTOM";
export type RepeatType = "WEEKLY" | "BIWEEKLY" | "MONTHLY";

export type FixedScheduleRule = {
  id: string;
  rule_id: string;
  freq_type: RepeatType;
  days: DayCode[];
  month_rule: MonthRule | null;
  month_days: number[];
  biweekly_start_date: string | null;
  start_time: string;
  end_time: string;
  created_at: string | null;
  updated_at: string | null;
};

export type FixedScheduleSeries = {
  id: string;
  series_id: string;
  user_id: string;
  title: string;
  color_key: number;
  created_at: string | null;
  updated_at: string | null;
  rules: FixedScheduleRule[];
};

export type WeekScheduleOccurrence = {
  id: string;
  series_id: string;
  rule_id: string;
  title: string;
  start_time: string;
  end_time: string;
  color_key: number;
  source_type: "fixed";
};

export type FixedScheduleDetailItem = {
  id: string;
  series_id: string;
  rule_id: string;
  title: string;
  label: string;
  start_time: string;
  end_time: string;
  freq_type: RepeatType;
  biweekly_start_date: string | null;
  target_day: DayCode | null;
  target_month_day: number | null;
};

export const STORAGE_KEYS = {
  fixedSeries: "fixed_schedule_series",
  variableSchedules: "variable_schedules",
} as const;

export const dayMap: Record<DayCode, number> = {
  SUN: 0,
  MON: 1,
  TUE: 2,
  WED: 3,
  THU: 4,
  FRI: 5,
  SAT: 6,
};

export const dayLabelMap: Record<DayCode, string> = {
  SUN: "일",
  MON: "월",
  TUE: "화",
  WED: "수",
  THU: "목",
  FRI: "금",
  SAT: "토",
};

export const dayOrder: DayCode[] = [
  "SUN",
  "MON",
  "TUE",
  "WED",
  "THU",
  "FRI",
  "SAT",
];

export const dayOptions: { code: DayCode; label: string }[] = [
  { code: "SUN", label: "일" },
  { code: "MON", label: "월" },
  { code: "TUE", label: "화" },
  { code: "WED", label: "수" },
  { code: "THU", label: "목" },
  { code: "FRI", label: "금" },
  { code: "SAT", label: "토" },
];

export const monthRuleOptions: { value: MonthRule; label: string }[] = [
  { value: "START", label: "매월 초" },
  { value: "MID", label: "매월 15일" },
  { value: "END", label: "매월 말일" },
  { value: "CUSTOM", label: "기타" },
];

export const initialFixedScheduleSeries: FixedScheduleSeries[] = [
  {
    id: "series-1",
    series_id: "series-1",
    user_id: "test_user",
    title: "알고리즘 수업",
    color_key: 0,
    created_at: null,
    updated_at: null,
    rules: [
      {
        id: "rule-1",
        rule_id: "rule-1",
        freq_type: "WEEKLY",
        days: ["MON"],
        month_rule: null,
        month_days: [],
        biweekly_start_date: null,
        start_time: "10:00:00",
        end_time: "12:00:00",
        created_at: null,
        updated_at: null,
      },
    ],
  },
  {
    id: "series-2",
    series_id: "series-2",
    user_id: "test_user",
    title: "헬스장 운동",
    color_key: 1,
    created_at: null,
    updated_at: null,
    rules: [
      {
        id: "rule-2",
        rule_id: "rule-2",
        freq_type: "WEEKLY",
        days: ["WED", "SAT"],
        month_rule: null,
        month_days: [],
        biweekly_start_date: null,
        start_time: "18:00:00",
        end_time: "20:00:00",
        created_at: null,
        updated_at: null,
      },
    ],
  },
  {
    id: "series-3",
    series_id: "series-3",
    user_id: "test_user",
    title: "출근",
    color_key: 2,
    created_at: null,
    updated_at: null,
    rules: [
      {
        id: "rule-3",
        rule_id: "rule-3",
        freq_type: "WEEKLY",
        days: ["MON", "TUE", "WED", "THU"],
        month_rule: null,
        month_days: [],
        biweekly_start_date: null,
        start_time: "09:00:00",
        end_time: "17:00:00",
        created_at: null,
        updated_at: null,
      },
      {
        id: "rule-4",
        rule_id: "rule-4",
        freq_type: "BIWEEKLY",
        days: ["FRI"],
        month_rule: null,
        month_days: [],
        biweekly_start_date: "2026-04-03",
        start_time: "14:00:00",
        end_time: "20:00:00",
        created_at: null,
        updated_at: null,
      },
    ],
  },
  {
    id: "series-4",
    series_id: "series-4",
    user_id: "test_user",
    title: "월간 상담",
    color_key: 3,
    created_at: null,
    updated_at: null,
    rules: [
      {
        id: "rule-5",
        rule_id: "rule-5",
        freq_type: "MONTHLY",
        days: [],
        month_rule: "MID",
        month_days: [],
        biweekly_start_date: null,
        start_time: "16:00:00",
        end_time: "17:00:00",
        created_at: null,
        updated_at: null,
      },
    ],
  },
];

export const initialVariableSchedules: VariableSchedule[] = [
  {
    id: "v1",
    user_id: "test_user",
    title: "네트워크 과제",
    estimated_time: 120,
    is_done: false,
    level: 7,
    deadline: "2026-04-17T23:59:00+09:00",
    scheduled_start: null,
    scheduled_end: null,
    fail_reason: null,
    priority: 1,
    created_at: null,
    updated_at: null,
  },
  {
    id: "v2",
    user_id: "test_user",
    title: "캡스톤 발표 자료 수정",
    estimated_time: 90,
    is_done: false,
    level: 8,
    deadline: "2026-04-18T18:00:00+09:00",
    scheduled_start: null,
    scheduled_end: null,
    fail_reason: null,
    priority: 1,
    created_at: null,
    updated_at: null,
  },
  {
    id: "v3",
    user_id: "test_user",
    title: "운영체제 복습",
    estimated_time: 60,
    is_done: true,
    level: 5,
    deadline: "2026-04-16T21:00:00+09:00",
    scheduled_start: null,
    scheduled_end: null,
    fail_reason: null,
    priority: 2,
    created_at: null,
    updated_at: null,
  },
];

export function timeToNumber(time: string) {
  const [h, m] = time.split(":").map(Number);
  return h + m / 60;
}

export function formatTimeRange(startTime: string, endTime: string) {
  return `${startTime.slice(0, 5)}~${endTime.slice(0, 5)}`;
}

export function parseKstDateString(value: string) {
  const normalized = value
    .trim()
    .replace(" ", "T")
    .replace(/([+-]\d{2})$/, "$1:00");

  return new Date(normalized);
}

export function formatDeadline(value: string) {
  const date = parseKstDateString(value);

  if (Number.isNaN(date.getTime())) {
    return "-";
  }

  const month = date.getMonth() + 1;
  const day = date.getDate();
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");

  return `${month}/${day} ${hour}:${minute}`;
}

export function getLevelLabel(level: number) {
  if (level >= 8) return "매우 높음";
  if (level >= 6) return "높음";
  if (level >= 3) return "보통";
  return "낮음";
}

export function toggleSelectedDay(days: DayCode[], target: DayCode) {
  if (days.includes(target)) {
    if (days.length === 1) return days;
    return days.filter((day) => day !== target);
  }

  return [...days, target].sort(
    (a, b) => dayOrder.indexOf(a) - dayOrder.indexOf(b)
  );
}

export function toggleSelectedMonthDay(days: number[], target: number) {
  if (days.includes(target)) {
    if (days.length === 1) return days;
    return days.filter((day) => day !== target);
  }

  return [...days, target].sort((a, b) => a - b);
}

export function getScheduleColorsByKey(colorKey: number) {
  const palette = [
    {
      bg: "var(--card-blue-bg)",
      text: "var(--card-blue-text)",
    },
    {
      bg: "var(--card-green-bg)",
      text: "var(--card-green-text)",
    },
    {
      bg: "var(--card-yellow-bg)",
      text: "var(--card-yellow-text)",
    },
    {
      bg: "var(--card-red-bg)",
      text: "var(--card-red-text)",
    },
  ];

  return palette[((colorKey % palette.length) + palette.length) % palette.length];
}

export function getNextColorKey(seriesList: FixedScheduleSeries[]) {
  if (seriesList.length === 0) return 0;
  return Math.max(...seriesList.map((series) => series.color_key)) + 1;
}

export function getLastDayOfMonth(date: Date) {
  return new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate();
}

function startOfDay(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function diffDays(a: Date, b: Date) {
  const ms = startOfDay(a).getTime() - startOfDay(b).getTime();
  return Math.floor(ms / (1000 * 60 * 60 * 24));
}

function isBiweeklyMatch(date: Date, rule: FixedScheduleRule) {
  if (!rule.biweekly_start_date) return false;

  const start = new Date(rule.biweekly_start_date);
  if (Number.isNaN(start.getTime())) return false;

  const days = diffDays(date, start);
  if (days < 0) return false;

  const weeks = Math.floor(days / 7);
  return weeks % 2 === 0;
}

function isMonthlyMatch(date: Date, rule: FixedScheduleRule) {
  if (rule.month_rule === "START") {
    return date.getDate() === 1;
  }

  if (rule.month_rule === "MID") {
    return date.getDate() === 15;
  }

  if (rule.month_rule === "END") {
    return date.getDate() === getLastDayOfMonth(date);
  }

  if (rule.month_rule === "CUSTOM") {
    return rule.month_days.includes(date.getDate());
  }

  return false;
}

function getMonthRuleLabel(
  monthRule: MonthRule | null,
  monthDays: number[],
  includePrefix = true
) {
  if (monthRule === "START") return includePrefix ? "매월 초" : "초";
  if (monthRule === "MID") return includePrefix ? "매월 15일" : "15일";
  if (monthRule === "END") return includePrefix ? "매월 말일" : "말일";
  if (monthRule === "CUSTOM") {
    return includePrefix
      ? `매월 ${monthDays.join(", ")}일`
      : `${monthDays.join(", ")}일`;
  }

  return "-";
}

function compressDayLabels(days: DayCode[]) {
  const sorted = [...days].sort(
    (a, b) => dayOrder.indexOf(a) - dayOrder.indexOf(b)
  );

  const labels = sorted.map((day) => dayLabelMap[day]);
  const indexes = sorted.map((day) => dayOrder.indexOf(day));

  if (sorted.length >= 2) {
    let isContinuous = true;
    for (let i = 1; i < indexes.length; i++) {
      if (indexes[i] !== indexes[i - 1] + 1) {
        isContinuous = false;
        break;
      }
    }

    if (isContinuous) {
      return `${labels[0]}~${labels[labels.length - 1]}`;
    }
  }

  return labels.join(", ");
}

export function formatRuleSummary(rule: FixedScheduleRule) {
  if (rule.freq_type === "MONTHLY") {
    return `${getMonthRuleLabel(rule.month_rule, rule.month_days, true)} ${formatTimeRange(rule.start_time, rule.end_time)}`;
  }

  const dayText = compressDayLabels(rule.days);

  if (rule.freq_type === "WEEKLY") {
    return `매주 ${dayText} ${formatTimeRange(rule.start_time, rule.end_time)}`;
  }

  const startText = rule.biweekly_start_date
    ? ` 시작일 ${new Date(rule.biweekly_start_date).getMonth() + 1}/${new Date(
        rule.biweekly_start_date
      ).getDate()}`
    : "";

  return `격주 ${dayText} ${formatTimeRange(rule.start_time, rule.end_time)}${startText}`;
}

export function expandRuleToDetailItems(
  series: FixedScheduleSeries,
  rule: FixedScheduleRule
): FixedScheduleDetailItem[] {
  if (rule.freq_type === "MONTHLY") {
    if (rule.month_rule === "CUSTOM") {
      return rule.month_days.map((day) => ({
        id: `${series.id}-${rule.id}-month-${day}`,
        series_id: series.series_id,
        rule_id: rule.rule_id,
        title: series.title,
        label: `매월 ${day}일`,
        start_time: rule.start_time,
        end_time: rule.end_time,
        freq_type: rule.freq_type,
        biweekly_start_date: rule.biweekly_start_date,
        target_day: null,
        target_month_day: day,
      }));
    }

    return [
      {
        id: `${series.id}-${rule.id}-month`,
        series_id: series.series_id,
        rule_id: rule.rule_id,
        title: series.title,
        label: getMonthRuleLabel(rule.month_rule, rule.month_days, true),
        start_time: rule.start_time,
        end_time: rule.end_time,
        freq_type: rule.freq_type,
        biweekly_start_date: rule.biweekly_start_date,
        target_day: null,
        target_month_day: null,
      },
    ];
  }

  return rule.days.map((day) => {
    const base = rule.freq_type === "WEEKLY" ? "매주" : "격주";
    const startText =
      rule.freq_type === "BIWEEKLY" && rule.biweekly_start_date
        ? ` 시작일 ${new Date(rule.biweekly_start_date).getMonth() + 1}/${new Date(
            rule.biweekly_start_date
          ).getDate()}`
        : "";

    return {
      id: `${series.id}-${rule.id}-${day}`,
      series_id: series.series_id,
      rule_id: rule.rule_id,
      title: series.title,
      label: `${base} ${dayLabelMap[day]}${startText}`,
      start_time: rule.start_time,
      end_time: rule.end_time,
      freq_type: rule.freq_type,
      biweekly_start_date: rule.biweekly_start_date,
      target_day: day,
      target_month_day: null,
    };
  });
}

function normalizeLegacyFixedData(parsed: unknown): FixedScheduleSeries[] {
  if (!Array.isArray(parsed)) {
    return initialFixedScheduleSeries;
  }

  if (parsed.length === 0) {
    return [];
  }

  const first = parsed[0] as Record<string, unknown>;

  if (Array.isArray(first.rules)) {
    return (parsed as FixedScheduleSeries[]).map((series, seriesIndex) => ({
      ...series,
      series_id: series.series_id ?? series.id ?? `series-${seriesIndex}`,
      color_key:
        typeof series.color_key === "number" ? series.color_key : seriesIndex % 4,
      created_at: series.created_at ?? null,
      updated_at: series.updated_at ?? null,
      rules: series.rules.map((rule, ruleIndex) => ({
        ...rule,
        rule_id: rule.rule_id ?? rule.id ?? `rule-${seriesIndex}-${ruleIndex}`,
        start_time: rule.start_time ?? "09:00:00",
        end_time: rule.end_time ?? "10:00:00",
        created_at: rule.created_at ?? null,
        updated_at: rule.updated_at ?? null,
      })),
    }));
  }

  return initialFixedScheduleSeries;
}

export function getFixedScheduleSeries() {
  if (typeof window === "undefined") {
    return initialFixedScheduleSeries;
  }

  try {
    const raw = localStorage.getItem(STORAGE_KEYS.fixedSeries);
    if (!raw) return initialFixedScheduleSeries;

    const parsed = JSON.parse(raw);
    return normalizeLegacyFixedData(parsed);
  } catch {
    return initialFixedScheduleSeries;
  }
}

export function saveFixedScheduleSeries(seriesList: FixedScheduleSeries[]) {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEYS.fixedSeries, JSON.stringify(seriesList));
}

export function getVariableSchedules() {
  if (typeof window === "undefined") {
    return initialVariableSchedules;
  }

  try {
    const raw = localStorage.getItem(STORAGE_KEYS.variableSchedules);
    if (!raw) return initialVariableSchedules;

    const parsed = JSON.parse(raw);

    if (!Array.isArray(parsed)) {
      return initialVariableSchedules;
    }

    return parsed as VariableSchedule[];
  } catch {
    return initialVariableSchedules;
  }
}

export function saveVariableSchedules(schedules: VariableSchedule[]) {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEYS.variableSchedules, JSON.stringify(schedules));
}

export function getScheduleOccurrencesForDate(
  date: Date,
  seriesList: FixedScheduleSeries[]
) {
  const dayIndex = date.getDay();

  const occurrences: WeekScheduleOccurrence[] = [];

  seriesList.forEach((series) => {
    series.rules.forEach((rule) => {
      let matched = false;

      if (rule.freq_type === "MONTHLY") {
        matched = isMonthlyMatch(date, rule);
      } else {
        const dayMatched = rule.days.some((day) => dayMap[day] === dayIndex);

        if (dayMatched) {
          if (rule.freq_type === "WEEKLY") {
            matched = true;
          } else if (rule.freq_type === "BIWEEKLY") {
            matched = isBiweeklyMatch(date, rule);
          }
        }
      }

      if (matched) {
        occurrences.push({
          id: `${series.series_id}-${rule.rule_id}-${date.toISOString()}`,
          series_id: series.series_id,
          rule_id: rule.rule_id,
          title: series.title,
          start_time: rule.start_time,
          end_time: rule.end_time,
          color_key: series.color_key,
          source_type: "fixed",
        });
      }
    });
  });

  return occurrences;
}

export function flattenSeriesToDbRows(seriesList: FixedScheduleSeries[]) {
  const rows: Array<{
    id: string;
    series_id: string;
    rule_id: string;
    user_id: string;
    title: string;
    freq_type: RepeatType;
    by_day: DayCode | null;
    by_month_day: number | null;
    start_time: string;
    end_time: string;
    biweekly_start_date: string | null;
    month_rule: MonthRule | null;
    color_key: number;
    created_at: string | null;
    updated_at: string | null;
  }> = [];

  seriesList.forEach((series) => {
    series.rules.forEach((rule) => {
      if (rule.freq_type === "MONTHLY") {
        if (rule.month_rule === "START") {
          rows.push({
            id: `${series.series_id}-${rule.rule_id}-db-1`,
            series_id: series.series_id,
            rule_id: rule.rule_id,
            user_id: series.user_id,
            title: series.title,
            freq_type: "MONTHLY",
            by_day: null,
            by_month_day: 1,
            start_time: rule.start_time,
            end_time: rule.end_time,
            biweekly_start_date: rule.biweekly_start_date,
            month_rule: rule.month_rule,
            color_key: series.color_key,
            created_at: rule.created_at,
            updated_at: rule.updated_at,
          });
        } else if (rule.month_rule === "MID") {
          rows.push({
            id: `${series.series_id}-${rule.rule_id}-db-15`,
            series_id: series.series_id,
            rule_id: rule.rule_id,
            user_id: series.user_id,
            title: series.title,
            freq_type: "MONTHLY",
            by_day: null,
            by_month_day: 15,
            start_time: rule.start_time,
            end_time: rule.end_time,
            biweekly_start_date: rule.biweekly_start_date,
            month_rule: rule.month_rule,
            color_key: series.color_key,
            created_at: rule.created_at,
            updated_at: rule.updated_at,
          });
        } else if (rule.month_rule === "CUSTOM") {
          rule.month_days.forEach((day) => {
            rows.push({
              id: `${series.series_id}-${rule.rule_id}-db-${day}`,
              series_id: series.series_id,
              rule_id: rule.rule_id,
              user_id: series.user_id,
              title: series.title,
              freq_type: "MONTHLY",
              by_day: null,
              by_month_day: day,
              start_time: rule.start_time,
              end_time: rule.end_time,
              biweekly_start_date: rule.biweekly_start_date,
              month_rule: rule.month_rule,
              color_key: series.color_key,
              created_at: rule.created_at,
              updated_at: rule.updated_at,
            });
          });
        } else if (rule.month_rule === "END") {
          rows.push({
            id: `${series.series_id}-${rule.rule_id}-db-end`,
            series_id: series.series_id,
            rule_id: rule.rule_id,
            user_id: series.user_id,
            title: series.title,
            freq_type: "MONTHLY",
            by_day: null,
            by_month_day: null,
            start_time: rule.start_time,
            end_time: rule.end_time,
            biweekly_start_date: rule.biweekly_start_date,
            month_rule: rule.month_rule,
            color_key: series.color_key,
            created_at: rule.created_at,
            updated_at: rule.updated_at,
          });
        }
      } else {
        rule.days.forEach((day) => {
          rows.push({
            id: `${series.series_id}-${rule.rule_id}-db-${day}`,
            series_id: series.series_id,
            rule_id: rule.rule_id,
            user_id: series.user_id,
            title: series.title,
            freq_type: rule.freq_type,
            by_day: day,
            by_month_day: null,
            start_time: rule.start_time,
            end_time: rule.end_time,
            biweekly_start_date: rule.biweekly_start_date,
            month_rule: rule.month_rule,
            color_key: series.color_key,
            created_at: rule.created_at,
            updated_at: rule.updated_at,
          });
        });
      }
    });
  });

  return rows;
}