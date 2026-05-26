export type DayCode = "SUN" | "MON" | "TUE" | "WED" | "THU" | "FRI" | "SAT";
export type MonthRule = "START" | "MID" | "END" | "CUSTOM";
export type RepeatType = "WEEKLY" | "BIWEEKLY" | "MONTHLY";
export type VariableStatus = "pending" | "done" | "failed";

export type FailReason =
  | "TIME_SHORTAGE"
  | "ENERGY_SHORTAGE"
  | "TRAVEL_TIME_SHORTAGE"
  | "TOOK_LONGER_THAN_EXPECTED"
  | "SUDDEN_SCHEDULE"
  | "LOW_FOCUS"
  | "ETC";

export type VariableSchedule = {
  id: string;
  user_id: string;
  title: string;
  estimated_time: number;
  is_done: boolean;
  status: VariableStatus;
  level: number;
  color_key: number;
  deadline: string;
  scheduled_start: string | null;
  scheduled_end: string | null;
  fail_reason: FailReason | null;
  fail_reason_text: string | null;
  priority: number | null;
  created_at: string | null;
  updated_at: string | null;
};

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
  level: number;
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
  level: number;
  source_type: "fixed";
};

export type WeekVariableOccurrence = {
  id: string;
  title: string;
  start_time: string;
  end_time: string;
  color_key: number;
  level: number;
  status: VariableStatus;
  fail_reason: FailReason | null;
  fail_reason_text: string | null;
  source_type: "variable";
};

export type WeekOccurrence = WeekScheduleOccurrence | WeekVariableOccurrence;

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

export const dayOrder: DayCode[] = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];

export const dayOptions = dayOrder.map((code) => ({
  code,
  label: dayLabelMap[code],
}));

export const monthRuleOptions: { value: MonthRule; label: string }[] = [
  { value: "START", label: "매월 초" },
  { value: "MID", label: "매월 15일" },
  { value: "END", label: "매월 말일" },
  { value: "CUSTOM", label: "기타 날짜" },
];

export const colorOptions = [
  { key: 0, label: "파랑" },
  { key: 1, label: "초록" },
  { key: 2, label: "노랑" },
  { key: 3, label: "빨강" },
  { key: 4, label: "보라" },
  { key: 5, label: "분홍" },
];

export const failReasonOptions: { value: FailReason; label: string }[] = [
  { value: "TIME_SHORTAGE", label: "시간 부족" },
  { value: "ENERGY_SHORTAGE", label: "체력 부족" },
  { value: "TRAVEL_TIME_SHORTAGE", label: "이동시간 부족" },
  { value: "TOOK_LONGER_THAN_EXPECTED", label: "예상보다 오래 걸림" },
  { value: "SUDDEN_SCHEDULE", label: "갑작스러운 일정 발생" },
  { value: "LOW_FOCUS", label: "집중력 부족" },
  { value: "ETC", label: "기타" },
];

export const initialFixedScheduleSeries: FixedScheduleSeries[] = [
  {
    id: "series-1",
    series_id: "series-1",
    user_id: "test_user",
    title: "알고리즘 수업",
    color_key: 0,
    level: 5,
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
];

export const initialVariableSchedules: VariableSchedule[] = [
  {
    id: "v1",
    user_id: "test_user",
    title: "네트워크 과제",
    estimated_time: 120,
    is_done: false,
    status: "pending",
    level: 7,
    color_key: 3,
    deadline: "2026-04-30T23:59:00+09:00",
    scheduled_start: null,
    scheduled_end: null,
    fail_reason: null,
    fail_reason_text: null,
    priority: 1,
    created_at: null,
    updated_at: null,
  },
];

export function timeToNumber(time: string) {
  const [h, m] = time.split(":").map(Number);
  return h + m / 60;
}

export function timeToMinutes(time: string) {
  const [h, m] = time.split(":").map(Number);
  return h * 60 + m;
}

export function formatTimeRange(startTime: string, endTime: string) {
  return `${startTime.slice(0, 5)}~${endTime.slice(0, 5)}`;
}

export function parseKstDateString(value: string) {
  return new Date(value.trim().replace(" ", "T").replace(/([+-]\d{2})$/, "$1:00"));
}

export function formatDeadline(value: string) {
  const date = parseKstDateString(value);
  if (Number.isNaN(date.getTime())) return "-";

  return `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, "0")}:${String(
    date.getMinutes()
  ).padStart(2, "0")}`;
}

export function getDeadlineDiffText(value: string) {
  const deadline = parseKstDateString(value);
  if (Number.isNaN(deadline.getTime())) return "마감일 확인 필요";

  const today = new Date();
  const todayStart = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime();
  const deadlineStart = new Date(deadline.getFullYear(), deadline.getMonth(), deadline.getDate()).getTime();
  const diff = Math.ceil((deadlineStart - todayStart) / (1000 * 60 * 60 * 24));

  if (diff < 0) return `${Math.abs(diff)}일 지남`;
  if (diff === 0) return "오늘 마감";
  return `D-${diff}`;
}

export function isDeadlinePassed(value: string) {
  const deadline = parseKstDateString(value);
  if (Number.isNaN(deadline.getTime())) return false;
  return deadline.getTime() < new Date().getTime();
}

export function getLevelLabel(level: number) {
  if (level >= 8) return "매우 높음";
  if (level >= 6) return "높음";
  if (level >= 3) return "보통";
  return "낮음";
}

export function getStatusLabel(status: VariableStatus) {
  if (status === "done") return "완료";
  if (status === "failed") return "실패";
  return "미완료";
}

export function getFailReasonLabel(reason: FailReason | null) {
  if (!reason) return null;
  return failReasonOptions.find((item) => item.value === reason)?.label ?? "기타";
}

export function getEffectiveVariableStatus(schedule: VariableSchedule): VariableStatus {
  if (schedule.status === "done") return "done";
  if (schedule.status === "failed") return "failed";
  if (schedule.is_done) return "done";
  if (isDeadlinePassed(schedule.deadline)) return "failed";
  return "pending";
}

export function toggleSelectedDay(days: DayCode[], target: DayCode) {
  if (days.includes(target)) {
    if (days.length === 1) return days;
    return days.filter((day) => day !== target);
  }

  return [...days, target].sort((a, b) => dayOrder.indexOf(a) - dayOrder.indexOf(b));
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
    { bg: "var(--card-blue-bg)", text: "var(--card-blue-text)", border: "var(--card-blue-border)" },
    { bg: "var(--card-green-bg)", text: "var(--card-green-text)", border: "var(--card-green-border)" },
    { bg: "var(--card-yellow-bg)", text: "var(--card-yellow-text)", border: "var(--card-yellow-border)" },
    { bg: "var(--card-red-bg)", text: "var(--card-red-text)", border: "var(--card-red-border)" },
    { bg: "var(--card-purple-bg)", text: "var(--card-purple-text)", border: "var(--card-purple-border)" },
    { bg: "var(--card-pink-bg)", text: "var(--card-pink-text)", border: "var(--card-pink-border)" },
  ];

  return palette[((colorKey % palette.length) + palette.length) % palette.length];
}

export function getNextColorKey(items: { color_key?: number }[]) {
  if (items.length === 0) return 0;
  return Math.max(...items.map((item) => item.color_key ?? 0)) + 1;
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

  return Math.floor(days / 7) % 2 === 0;
}

function isMonthlyMatch(date: Date, rule: FixedScheduleRule) {
  if (rule.month_rule === "START") return date.getDate() === 1;
  if (rule.month_rule === "MID") return date.getDate() === 15;
  if (rule.month_rule === "END") return date.getDate() === getLastDayOfMonth(date);
  if (rule.month_rule === "CUSTOM") return rule.month_days.includes(date.getDate());
  return false;
}

function getMonthRuleLabel(monthRule: MonthRule | null, monthDays: number[], includePrefix = true) {
  if (monthRule === "START") return includePrefix ? "매월 초" : "초";
  if (monthRule === "MID") return includePrefix ? "매월 15일" : "15일";
  if (monthRule === "END") return includePrefix ? "매월 말일" : "말일";
  if (monthRule === "CUSTOM") return includePrefix ? `매월 ${monthDays.join(", ")}일` : `${monthDays.join(", ")}일`;
  return "-";
}

function compressDayLabels(days: DayCode[]) {
  return [...days]
    .sort((a, b) => dayOrder.indexOf(a) - dayOrder.indexOf(b))
    .map((day) => dayLabelMap[day])
    .join(", ");
}

export function formatRuleSummary(rule: FixedScheduleRule) {
  if (rule.freq_type === "MONTHLY") {
    return `${getMonthRuleLabel(rule.month_rule, rule.month_days, true)} ${formatTimeRange(
      rule.start_time,
      rule.end_time
    )}`;
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

export function expandRuleToDetailItems(series: FixedScheduleSeries, rule: FixedScheduleRule): FixedScheduleDetailItem[] {
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
  if (!Array.isArray(parsed)) return initialFixedScheduleSeries;
  if (parsed.length === 0) return [];

  return (parsed as Partial<FixedScheduleSeries>[]).map((series, seriesIndex) => ({
    id: series.id ?? `series-${seriesIndex}`,
    series_id: series.series_id ?? series.id ?? `series-${seriesIndex}`,
    user_id: series.user_id ?? "test_user",
    title: series.title ?? "제목 없음",
    color_key: typeof series.color_key === "number" ? series.color_key : seriesIndex % colorOptions.length,
    level: typeof series.level === "number" ? series.level : 5,
    created_at: series.created_at ?? null,
    updated_at: series.updated_at ?? null,
    rules: Array.isArray(series.rules)
      ? series.rules.map((rule, ruleIndex) => ({
          id: rule.id ?? `rule-${seriesIndex}-${ruleIndex}`,
          rule_id: rule.rule_id ?? rule.id ?? `rule-${seriesIndex}-${ruleIndex}`,
          freq_type: rule.freq_type ?? "WEEKLY",
          days: Array.isArray(rule.days) ? rule.days : [],
          month_rule: rule.month_rule ?? null,
          month_days: Array.isArray(rule.month_days) ? rule.month_days : [],
          biweekly_start_date: rule.biweekly_start_date ?? null,
          start_time: rule.start_time ?? "09:00:00",
          end_time: rule.end_time ?? "10:00:00",
          created_at: rule.created_at ?? null,
          updated_at: rule.updated_at ?? null,
        }))
      : [],
  }));
}

function normalizeLegacyVariableData(parsed: unknown): VariableSchedule[] {
  if (!Array.isArray(parsed)) return initialVariableSchedules;

  return (parsed as Partial<VariableSchedule>[]).map((item, index) => {
    const isDone = Boolean(item.is_done);
    const status: VariableStatus =
      item.status === "done" || item.status === "failed" || item.status === "pending"
        ? item.status
        : isDone
          ? "done"
          : "pending";

    return {
      id: item.id ?? `variable-${index}`,
      user_id: item.user_id ?? "test_user",
      title: item.title ?? "제목 없음",
      estimated_time: typeof item.estimated_time === "number" ? item.estimated_time : 60,
      is_done: isDone,
      status,
      level: typeof item.level === "number" ? item.level : 5,
      color_key: typeof item.color_key === "number" ? item.color_key : index % colorOptions.length,
      deadline: item.deadline ?? new Date().toISOString(),
      scheduled_start: item.scheduled_start ?? null,
      scheduled_end: item.scheduled_end ?? null,
      fail_reason: item.fail_reason ?? null,
      fail_reason_text: item.fail_reason_text ?? null,
      priority: item.priority ?? null,
      created_at: item.created_at ?? null,
      updated_at: item.updated_at ?? null,
    };
  });
}

export function getFixedScheduleSeries() {
  if (typeof window === "undefined") return initialFixedScheduleSeries;

  try {
    const raw = localStorage.getItem(STORAGE_KEYS.fixedSeries);
    if (!raw) return initialFixedScheduleSeries;
    return normalizeLegacyFixedData(JSON.parse(raw));
  } catch {
    return initialFixedScheduleSeries;
  }
}

export function saveFixedScheduleSeries(seriesList: FixedScheduleSeries[]) {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEYS.fixedSeries, JSON.stringify(seriesList));
}

export function getVariableSchedules() {
  if (typeof window === "undefined") return initialVariableSchedules;

  try {
    const raw = localStorage.getItem(STORAGE_KEYS.variableSchedules);
    if (!raw) return initialVariableSchedules;
    return normalizeLegacyVariableData(JSON.parse(raw));
  } catch {
    return initialVariableSchedules;
  }
}

export function saveVariableSchedules(schedules: VariableSchedule[]) {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEYS.variableSchedules, JSON.stringify(schedules));
}

export function getScheduleOccurrencesForDate(date: Date, seriesList: FixedScheduleSeries[]) {
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
          matched = rule.freq_type === "WEEKLY" ? true : isBiweeklyMatch(date, rule);
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
          level: series.level ?? 5,
          source_type: "fixed",
        });
      }
    });
  });

  return occurrences;
}

function isSameDate(a: Date, b: Date) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function toTimeStringFromDate(date: Date) {
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}:00`;
}

export function getVariableOccurrencesForDate(date: Date, schedules: VariableSchedule[]) {
  const occurrences: WeekVariableOccurrence[] = [];

  schedules.forEach((schedule) => {
    if (!schedule.scheduled_start || !schedule.scheduled_end) return;

    const start = parseKstDateString(schedule.scheduled_start);
    const end = parseKstDateString(schedule.scheduled_end);

    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return;
    if (!isSameDate(date, start)) return;

    occurrences.push({
      id: schedule.id,
      title: schedule.title,
      start_time: toTimeStringFromDate(start),
      end_time: toTimeStringFromDate(end),
      color_key: schedule.color_key,
      level: schedule.level,
      status: getEffectiveVariableStatus(schedule),
      fail_reason: schedule.fail_reason,
      fail_reason_text: schedule.fail_reason_text,
      source_type: "variable",
    });
  });

  return occurrences;
}

export function flattenSeriesToDbRows(seriesList: FixedScheduleSeries[]) {
  return seriesList.flatMap((series) =>
    series.rules.flatMap((rule) => {
      if (rule.freq_type === "MONTHLY") {
        const monthDays =
          rule.month_rule === "START"
            ? [1]
            : rule.month_rule === "MID"
              ? [15]
              : rule.month_rule === "CUSTOM"
                ? rule.month_days
                : [null];

        return monthDays.map((day) => ({
          id: `${series.series_id}-${rule.rule_id}-db-${day ?? "end"}`,
          series_id: series.series_id,
          rule_id: rule.rule_id,
          user_id: series.user_id,
          title: series.title,
          freq_type: rule.freq_type,
          by_day: null as DayCode | null,
          by_month_day: day,
          start_time: rule.start_time,
          end_time: rule.end_time,
          biweekly_start_date: rule.biweekly_start_date,
          month_rule: rule.month_rule,
          color_key: series.color_key,
          level: series.level,
          created_at: rule.created_at,
          updated_at: rule.updated_at,
        }));
      }

      return rule.days.map((day) => ({
        id: `${series.series_id}-${rule.rule_id}-db-${day}`,
        series_id: series.series_id,
        rule_id: rule.rule_id,
        user_id: series.user_id,
        title: series.title,
        freq_type: rule.freq_type,
        by_day: day,
        by_month_day: null as number | null,
        start_time: rule.start_time,
        end_time: rule.end_time,
        biweekly_start_date: rule.biweekly_start_date,
        month_rule: rule.month_rule,
        color_key: series.color_key,
        level: series.level,
        created_at: rule.created_at,
        updated_at: rule.updated_at,
      }));
    })
  );
}