"use client";

import { useEffect, useMemo, useState } from "react";
import {
  type DayCode,
  type FixedScheduleDetailItem,
  type FixedScheduleRule,
  type FixedScheduleSeries,
  type MonthRule,
  type RepeatType,
  type VariableSchedule,
  dayOptions,
  expandRuleToDetailItems,
  formatDeadline,
  formatRuleSummary,
  formatTimeRange,
  getFixedScheduleSeries,
  getLevelLabel,
  getNextColorKey,
  getScheduleColorsByKey,
  getVariableSchedules,
  monthRuleOptions,
  parseKstDateString,
  saveFixedScheduleSeries,
  saveVariableSchedules,
  toggleSelectedDay,
  toggleSelectedMonthDay,
} from "@/lib/mockSchedules";

type FixedFormState = {
  title: string;
  start_time: string;
  end_time: string;
  freq_type: RepeatType;
  selected_days: DayCode[];
  month_rule: MonthRule;
  selected_month_days: number[];
  biweekly_start_date: string;
};

type VariableFormState = {
  title: string;
  estimated_time: string;
  level: string;
  deadline: string;
};

const fixedInitialForm: FixedFormState = {
  title: "",
  start_time: "09:00",
  end_time: "10:00",
  freq_type: "WEEKLY",
  selected_days: ["MON"],
  month_rule: "START",
  selected_month_days: [1],
  biweekly_start_date: "",
};

const variableInitialForm: VariableFormState = {
  title: "",
  estimated_time: "",
  level: "5",
  deadline: "",
};

function toTimeWithSeconds(value: string) {
  return value.length === 5 ? `${value}:00` : value;
}

function toDeadlineWithTimezone(value: string) {
  return `${value}:00+09:00`;
}

function toDateInputValue(value: string | null) {
  return value ?? "";
}

function toDateTimeLocalValue(value: string) {
  const date = parseKstDateString(value);

  if (Number.isNaN(date.getTime())) return "";

  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");

  return `${year}-${month}-${day}T${hour}:${minute}`;
}

function createFormFromDetailItem(
  item: FixedScheduleDetailItem
): FixedFormState {
  return {
    title: item.title,
    start_time: item.start_time.slice(0, 5),
    end_time: item.end_time.slice(0, 5),
    freq_type: item.freq_type,
    selected_days: item.target_day ? [item.target_day] : ["MON"],
    month_rule:
      item.freq_type === "MONTHLY"
        ? item.target_month_day
          ? "CUSTOM"
          : "START"
        : "START",
    selected_month_days: item.target_month_day ? [item.target_month_day] : [1],
    biweekly_start_date: item.biweekly_start_date ?? "",
  };
}

function createVariableFormFromItem(item: VariableSchedule): VariableFormState {
  return {
    title: item.title,
    estimated_time: String(item.estimated_time),
    level: String(item.level),
    deadline: toDateTimeLocalValue(item.deadline),
  };
}

export default function ManagePage() {
  const [activeTab, setActiveTab] = useState<"fixed" | "variable">("fixed");
  const [fixedForm, setFixedForm] = useState<FixedFormState>(fixedInitialForm);
  const [variableForm, setVariableForm] =
    useState<VariableFormState>(variableInitialForm);

  const [fixedSeriesList, setFixedSeriesList] = useState<FixedScheduleSeries[]>([]);
  const [variableList, setVariableList] = useState<VariableSchedule[]>([]);

  const [expandedSeriesId, setExpandedSeriesId] = useState<string | null>(null);

  const [editingSeriesId, setEditingSeriesId] = useState<string | null>(null);
  const [editingRuleId, setEditingRuleId] = useState<string | null>(null);
  const [editingDetail, setEditingDetail] = useState<FixedScheduleDetailItem | null>(
    null
  );

  const [addingToSeriesId, setAddingToSeriesId] = useState<string | null>(null);

  const [editingVariableId, setEditingVariableId] = useState<string | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    setFixedSeriesList(getFixedScheduleSeries());
    setVariableList(getVariableSchedules());
    setIsLoaded(true);
  }, []);

  useEffect(() => {
    if (!isLoaded) return;
    saveFixedScheduleSeries(fixedSeriesList);
  }, [fixedSeriesList, isLoaded]);

  useEffect(() => {
    if (!isLoaded) return;
    saveVariableSchedules(variableList);
  }, [variableList, isLoaded]);

  const sortedFixedSeriesList = useMemo(() => {
    return [...fixedSeriesList].sort((a, b) => a.title.localeCompare(b.title));
  }, [fixedSeriesList]);

  const sortedVariableList = useMemo(() => {
    return [...variableList].sort((a, b) => {
      return (
        parseKstDateString(a.deadline).getTime() -
        parseKstDateString(b.deadline).getTime()
      );
    });
  }, [variableList]);

  const resetFixedEditState = () => {
    setEditingSeriesId(null);
    setEditingRuleId(null);
    setEditingDetail(null);
    setAddingToSeriesId(null);
    setFixedForm(fixedInitialForm);
  };

  const handleFixedSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!fixedForm.title.trim()) return;
    if (!fixedForm.start_time || !fixedForm.end_time) return;

    if (
      (fixedForm.freq_type === "WEEKLY" || fixedForm.freq_type === "BIWEEKLY") &&
      fixedForm.selected_days.length === 0
    ) {
      return;
    }

    if (
      fixedForm.freq_type === "BIWEEKLY" &&
      !fixedForm.biweekly_start_date.trim()
    ) {
      return;
    }

    if (
      fixedForm.freq_type === "MONTHLY" &&
      fixedForm.month_rule === "CUSTOM" &&
      fixedForm.selected_month_days.length === 0
    ) {
      return;
    }

    const now = new Date().toISOString();
    const generatedRuleId = `rule-${Date.now()}`;

    const newRule: FixedScheduleRule = {
      id: editingRuleId ?? generatedRuleId,
      rule_id: editingRuleId ?? generatedRuleId,
      freq_type: fixedForm.freq_type,
      days: fixedForm.freq_type === "MONTHLY" ? [] : fixedForm.selected_days,
      month_rule: fixedForm.freq_type === "MONTHLY" ? fixedForm.month_rule : null,
      month_days:
        fixedForm.freq_type === "MONTHLY" && fixedForm.month_rule === "CUSTOM"
          ? fixedForm.selected_month_days
          : [],
      biweekly_start_date:
        fixedForm.freq_type === "BIWEEKLY"
          ? fixedForm.biweekly_start_date
          : null,
      start_time: toTimeWithSeconds(fixedForm.start_time),
      end_time: toTimeWithSeconds(fixedForm.end_time),
      created_at: null,
      updated_at: now,
    };

    if (editingSeriesId && editingRuleId && editingDetail) {
      setFixedSeriesList((prev) =>
        prev.map((series) => {
          if (series.series_id !== editingSeriesId) return series;

          const nextRules: FixedScheduleRule[] = [];

          series.rules.forEach((rule) => {
            if (rule.rule_id !== editingRuleId) {
              nextRules.push(rule);
              return;
            }

            if (editingDetail.target_day) {
              const remainingDays = rule.days.filter(
                (day) => day !== editingDetail.target_day
              );

              if (remainingDays.length > 0) {
                nextRules.push({
                  ...rule,
                  days: remainingDays,
                  updated_at: now,
                });
              }

              nextRules.push({
                ...newRule,
                id: `${generatedRuleId}-${editingDetail.target_day}`,
                rule_id: `${generatedRuleId}-${editingDetail.target_day}`,
                days: [editingDetail.target_day],
              });
              return;
            }

            if (editingDetail.target_month_day !== null) {
              const remainingMonthDays = rule.month_days.filter(
                (day) => day !== editingDetail.target_month_day
              );

              if (
                rule.month_rule === "CUSTOM" &&
                remainingMonthDays.length > 0
              ) {
                nextRules.push({
                  ...rule,
                  month_days: remainingMonthDays,
                  updated_at: now,
                });
              }

              nextRules.push({
                ...newRule,
                id: `${generatedRuleId}-month-${editingDetail.target_month_day}`,
                rule_id: `${generatedRuleId}-month-${editingDetail.target_month_day}`,
              });
              return;
            }

            nextRules.push(newRule);
          });

          return {
            ...series,
            title: fixedForm.title.trim(),
            updated_at: now,
            rules: nextRules,
          };
        })
      );

      setExpandedSeriesId(editingSeriesId);
      resetFixedEditState();
      return;
    }

    if (addingToSeriesId) {
      setFixedSeriesList((prev) =>
        prev.map((series) => {
          if (series.series_id !== addingToSeriesId) return series;

          return {
            ...series,
            title: fixedForm.title.trim(),
            updated_at: now,
            rules: [
              ...series.rules,
              {
                ...newRule,
                id: generatedRuleId,
                rule_id: generatedRuleId,
                created_at: now,
              },
            ],
          };
        })
      );
      setExpandedSeriesId(addingToSeriesId);
      resetFixedEditState();
      return;
    }

    const newSeriesId = `series-${Date.now()}`;

    const newSeries: FixedScheduleSeries = {
      id: newSeriesId,
      series_id: newSeriesId,
      user_id: "test_user",
      title: fixedForm.title.trim(),
      color_key: getNextColorKey(fixedSeriesList),
      created_at: now,
      updated_at: now,
      rules: [
        {
          ...newRule,
          id: generatedRuleId,
          rule_id: generatedRuleId,
          created_at: now,
        },
      ],
    };

    setFixedSeriesList((prev) => [...prev, newSeries]);
    setExpandedSeriesId(newSeriesId);
    resetFixedEditState();
  };

  const handleEditDetail = (
    series: FixedScheduleSeries,
    detail: FixedScheduleDetailItem
  ) => {
    setActiveTab("fixed");
    setEditingSeriesId(series.series_id);
    setEditingRuleId(detail.rule_id);
    setEditingDetail(detail);
    setAddingToSeriesId(null);
    setFixedForm(createFormFromDetailItem(detail));
  };

  const handleAddRuleToSeries = (series: FixedScheduleSeries) => {
    setActiveTab("fixed");
    setAddingToSeriesId(series.series_id);
    setEditingSeriesId(null);
    setEditingRuleId(null);
    setEditingDetail(null);
    setFixedForm({
      title: series.title,
      start_time: "09:00",
      end_time: "10:00",
      freq_type: "WEEKLY",
      selected_days: ["MON"],
      month_rule: "START",
      selected_month_days: [1],
      biweekly_start_date: "",
    });
  };

  const handleDeleteDetail = (
    seriesId: string,
    detail: FixedScheduleDetailItem
  ) => {
    const now = new Date().toISOString();

    setFixedSeriesList((prev) =>
      prev
        .map((series) => {
          if (series.series_id !== seriesId) return series;

          const nextRules: FixedScheduleRule[] = [];

          series.rules.forEach((rule) => {
            if (rule.rule_id !== detail.rule_id) {
              nextRules.push(rule);
              return;
            }

            if (detail.target_day) {
              const remainingDays = rule.days.filter(
                (day) => day !== detail.target_day
              );

              if (remainingDays.length > 0) {
                nextRules.push({
                  ...rule,
                  days: remainingDays,
                  updated_at: now,
                });
              }
              return;
            }

            if (detail.target_month_day !== null) {
              if (rule.month_rule === "CUSTOM") {
                const remainingMonthDays = rule.month_days.filter(
                  (day) => day !== detail.target_month_day
                );

                if (remainingMonthDays.length > 0) {
                  nextRules.push({
                    ...rule,
                    month_days: remainingMonthDays,
                    updated_at: now,
                  });
                }
              }
              return;
            }

            // 단일 규칙이면 삭제
          });

          return {
            ...series,
            updated_at: now,
            rules: nextRules,
          };
        })
        .filter((series) => series.rules.length > 0)
    );

    if (
      editingSeriesId === seriesId &&
      editingRuleId === detail.rule_id
    ) {
      resetFixedEditState();
    }
  };

  const handleToggleSeriesDetail = (seriesId: string) => {
    setExpandedSeriesId((prev) => (prev === seriesId ? null : seriesId));
  };

  const handleDeleteSeries = (seriesId: string) => {
    setFixedSeriesList((prev) => prev.filter((series) => series.series_id !== seriesId));

    if (expandedSeriesId === seriesId) {
      setExpandedSeriesId(null);
    }

    if (editingSeriesId === seriesId || addingToSeriesId === seriesId) {
      resetFixedEditState();
    }
  };

  const handleEditVariable = (item: VariableSchedule) => {
    setActiveTab("variable");
    setEditingVariableId(item.id);
    setVariableForm(createVariableFormFromItem(item));
  };

  const handleVariableSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!variableForm.title.trim()) return;
    if (!variableForm.estimated_time || Number(variableForm.estimated_time) <= 0)
      return;
    if (
      !variableForm.level ||
      Number(variableForm.level) < 0 ||
      Number(variableForm.level) > 10
    )
      return;
    if (!variableForm.deadline) return;

    const now = new Date().toISOString();

    const existing = editingVariableId
      ? variableList.find((item) => item.id === editingVariableId)
      : null;

    const nextItem: VariableSchedule = {
      id: existing?.id ?? `variable-${Date.now()}`,
      user_id: "test_user",
      title: variableForm.title.trim(),
      estimated_time: Number(variableForm.estimated_time),
      is_done: existing?.is_done ?? false,
      level: Number(variableForm.level),
      deadline: toDeadlineWithTimezone(variableForm.deadline),
      scheduled_start: existing?.scheduled_start ?? null,
      scheduled_end: existing?.scheduled_end ?? null,
      fail_reason: existing?.fail_reason ?? null,
      priority: existing?.priority ?? null,
      created_at: existing?.created_at ?? now,
      updated_at: now,
    };

    if (editingVariableId) {
      setVariableList((prev) =>
        prev.map((item) => (item.id === editingVariableId ? nextItem : item))
      );
    } else {
      setVariableList((prev) => [...prev, nextItem]);
    }

    setEditingVariableId(null);
    setVariableForm(variableInitialForm);
  };

  const handleDeleteVariable = (id: string) => {
    setVariableList((prev) => prev.filter((item) => item.id !== id));

    if (editingVariableId === id) {
      setEditingVariableId(null);
      setVariableForm(variableInitialForm);
    }
  };

  const handleToggleDone = (id: string) => {
    const now = new Date().toISOString();

    setVariableList((prev) =>
      prev.map((item) =>
        item.id === id
          ? { ...item, is_done: !item.is_done, updated_at: now }
          : item
      )
    );
  };

  const handleCancelVariableEdit = () => {
    setEditingVariableId(null);
    setVariableForm(variableInitialForm);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1
          className="text-3xl font-bold mb-2"
          style={{ color: "var(--app-text)" }}
        >
          일정 관리
        </h1>
        <p style={{ color: "var(--app-text-muted)" }}>
          고정 스케줄과 변동 스케줄을 나눠 등록하고 관리할 수 있습니다.
        </p>
      </div>

      <div className="flex gap-3">
        <button
          type="button"
          onClick={() => setActiveTab("fixed")}
          className="px-4 py-2 rounded-full border font-semibold transition"
          style={{
            background:
              activeTab === "fixed"
                ? "var(--primary-button-bg)"
                : "var(--app-surface)",
            color:
              activeTab === "fixed"
                ? "var(--primary-button-text)"
                : "var(--app-text)",
            borderColor: "var(--app-border)",
          }}
        >
          고정 스케줄
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("variable")}
          className="px-4 py-2 rounded-full border font-semibold transition"
          style={{
            background:
              activeTab === "variable"
                ? "var(--primary-button-bg)"
                : "var(--app-surface)",
            color:
              activeTab === "variable"
                ? "var(--primary-button-text)"
                : "var(--app-text)",
            borderColor: "var(--app-border)",
          }}
        >
          변동 스케줄
        </button>
      </div>

      {activeTab === "fixed" ? (
        <div className="grid grid-cols-1 xl:grid-cols-[500px_1fr] gap-6">
          <section
            className="rounded-2xl border p-5 shadow-sm"
            style={{
              background: "var(--app-surface)",
              borderColor: "var(--app-border)",
            }}
          >
            <div className="flex items-center justify-between mb-4">
              <h2
                className="text-xl font-bold"
                style={{ color: "var(--app-text)" }}
              >
                {editingDetail
                  ? "개별 일정 수정"
                  : addingToSeriesId
                    ? "반복 항목 추가"
                    : "고정 스케줄 등록"}
              </h2>

              {(editingDetail || addingToSeriesId) && (
                <button
                  type="button"
                  onClick={resetFixedEditState}
                  className="px-3 py-2 rounded-lg text-sm font-semibold"
                  style={{
                    background: "var(--app-surface-muted)",
                    color: "var(--app-text)",
                  }}
                >
                  취소
                </button>
              )}
            </div>

            <form onSubmit={handleFixedSubmit} className="space-y-4">
              <div>
                <label
                  className="block text-sm font-semibold mb-2"
                  style={{ color: "var(--app-text)" }}
                >
                  일정 이름
                </label>
                <input
                  value={fixedForm.title}
                  onChange={(e) =>
                    setFixedForm((prev) => ({ ...prev, title: e.target.value }))
                  }
                  placeholder="예: 출근"
                  className="w-full rounded-xl border px-3 py-2 outline-none"
                  style={{
                    background: "var(--app-bg)",
                    borderColor: "var(--app-border)",
                    color: "var(--app-text)",
                  }}
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label
                    className="block text-sm font-semibold mb-2"
                    style={{ color: "var(--app-text)" }}
                  >
                    시작 시간
                  </label>
                  <input
                    type="time"
                    value={fixedForm.start_time}
                    onChange={(e) =>
                      setFixedForm((prev) => ({
                        ...prev,
                        start_time: e.target.value,
                      }))
                    }
                    className="w-full rounded-xl border px-3 py-2 outline-none"
                    style={{
                      background: "var(--app-bg)",
                      borderColor: "var(--app-border)",
                      color: "var(--app-text)",
                    }}
                  />
                </div>

                <div>
                  <label
                    className="block text-sm font-semibold mb-2"
                    style={{ color: "var(--app-text)" }}
                  >
                    종료 시간
                  </label>
                  <input
                    type="time"
                    value={fixedForm.end_time}
                    onChange={(e) =>
                      setFixedForm((prev) => ({
                        ...prev,
                        end_time: e.target.value,
                      }))
                    }
                    className="w-full rounded-xl border px-3 py-2 outline-none"
                    style={{
                      background: "var(--app-bg)",
                      borderColor: "var(--app-border)",
                      color: "var(--app-text)",
                    }}
                  />
                </div>
              </div>

              <div>
                <label
                  className="block text-sm font-semibold mb-2"
                  style={{ color: "var(--app-text)" }}
                >
                  반복 유형
                </label>
                <select
                  value={fixedForm.freq_type}
                  onChange={(e) =>
                    setFixedForm((prev) => ({
                      ...prev,
                      freq_type: e.target.value as RepeatType,
                    }))
                  }
                  disabled={Boolean(editingDetail)}
                  className="w-full rounded-xl border px-3 py-2 outline-none disabled:opacity-60"
                  style={{
                    background: "var(--app-bg)",
                    borderColor: "var(--app-border)",
                    color: "var(--app-text)",
                  }}
                >
                  <option value="WEEKLY">매주</option>
                  <option value="BIWEEKLY">격주</option>
                  <option value="MONTHLY">매월</option>
                </select>
              </div>

              {!editingDetail &&
                (fixedForm.freq_type === "WEEKLY" ||
                  fixedForm.freq_type === "BIWEEKLY") && (
                  <div>
                    <label
                      className="block text-sm font-semibold mb-2"
                      style={{ color: "var(--app-text)" }}
                    >
                      요일 선택
                    </label>

                    <div className="grid grid-cols-7 gap-2">
                      {dayOptions.map((day) => {
                        const selected = fixedForm.selected_days.includes(day.code);

                        return (
                          <button
                            key={day.code}
                            type="button"
                            onClick={() =>
                              setFixedForm((prev) => ({
                                ...prev,
                                selected_days: toggleSelectedDay(
                                  prev.selected_days,
                                  day.code
                                ),
                              }))
                            }
                            className="h-11 rounded-lg border text-sm font-bold transition"
                            style={{
                              background: selected
                                ? "var(--primary-button-bg)"
                                : "var(--app-bg)",
                              color: selected
                                ? "var(--primary-button-text)"
                                : "var(--app-text)",
                              borderColor: selected
                                ? "var(--primary-button-bg)"
                                : "var(--app-border)",
                            }}
                          >
                            {day.label}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

              {editingDetail && (
                <div
                  className="rounded-xl border px-3 py-3 text-sm"
                  style={{
                    background: "var(--app-bg)",
                    borderColor: "var(--app-border)",
                    color: "var(--app-text-muted)",
                  }}
                >
                  수정 대상: {editingDetail.label}
                </div>
              )}

              {fixedForm.freq_type === "BIWEEKLY" && (
                <div>
                  <label
                    className="block text-sm font-semibold mb-2"
                    style={{ color: "var(--app-text)" }}
                  >
                    격주 시작일
                  </label>
                  <input
                    type="date"
                    value={toDateInputValue(fixedForm.biweekly_start_date)}
                    onChange={(e) =>
                      setFixedForm((prev) => ({
                        ...prev,
                        biweekly_start_date: e.target.value,
                      }))
                    }
                    className="w-full rounded-xl border px-3 py-2 outline-none"
                    style={{
                      background: "var(--app-bg)",
                      borderColor: "var(--app-border)",
                      color: "var(--app-text)",
                    }}
                  />
                </div>
              )}

              {!editingDetail && fixedForm.freq_type === "MONTHLY" && (
                <div className="space-y-3">
                  <div>
                    <label
                      className="block text-sm font-semibold mb-2"
                      style={{ color: "var(--app-text)" }}
                    >
                      월간 반복 방식
                    </label>

                    <div className="grid grid-cols-2 gap-2">
                      {monthRuleOptions.map((option) => {
                        const selected = fixedForm.month_rule === option.value;

                        return (
                          <button
                            key={option.value}
                            type="button"
                            onClick={() =>
                              setFixedForm((prev) => ({
                                ...prev,
                                month_rule: option.value,
                              }))
                            }
                            className="h-11 rounded-lg border text-sm font-semibold transition"
                            style={{
                              background: selected
                                ? "var(--primary-button-bg)"
                                : "var(--app-bg)",
                              color: selected
                                ? "var(--primary-button-text)"
                                : "var(--app-text)",
                              borderColor: selected
                                ? "var(--primary-button-bg)"
                                : "var(--app-border)",
                            }}
                          >
                            {option.label}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {fixedForm.month_rule === "CUSTOM" && (
                    <div>
                      <label
                        className="block text-sm font-semibold mb-2"
                        style={{ color: "var(--app-text)" }}
                      >
                        기타 날짜 선택
                      </label>

                      <div className="grid grid-cols-7 gap-2">
                        {Array.from({ length: 31 }, (_, i) => i + 1).map((day) => {
                          const selected =
                            fixedForm.selected_month_days.includes(day);

                          return (
                            <button
                              key={day}
                              type="button"
                              onClick={() =>
                                setFixedForm((prev) => ({
                                  ...prev,
                                  selected_month_days: toggleSelectedMonthDay(
                                    prev.selected_month_days,
                                    day
                                  ),
                                }))
                              }
                              className="h-11 rounded-lg border text-sm font-semibold transition"
                              style={{
                                background: selected
                                  ? "var(--primary-button-bg)"
                                  : "var(--app-bg)",
                                color: selected
                                  ? "var(--primary-button-text)"
                                  : "var(--app-text)",
                                borderColor: selected
                                  ? "var(--primary-button-bg)"
                                  : "var(--app-border)",
                              }}
                            >
                              {day}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <button
                type="submit"
                className="w-full rounded-xl py-3 font-semibold transition hover:opacity-90"
                style={{
                  background: "var(--primary-button-bg)",
                  color: "var(--primary-button-text)",
                }}
              >
                {editingDetail
                  ? "개별 일정 저장"
                  : addingToSeriesId
                    ? "반복 항목 추가"
                    : "고정 스케줄 추가"}
              </button>
            </form>
          </section>

          <section
            className="rounded-2xl border p-5 shadow-sm"
            style={{
              background: "var(--app-surface)",
              borderColor: "var(--app-border)",
            }}
          >
            <div className="flex items-center justify-between mb-4">
              <h2
                className="text-xl font-bold"
                style={{ color: "var(--app-text)" }}
              >
                등록된 고정 스케줄
              </h2>
              <span
                className="text-sm font-medium"
                style={{ color: "var(--app-text-muted)" }}
              >
                총 {sortedFixedSeriesList.length}개
              </span>
            </div>

            <div className="space-y-3">
              {sortedFixedSeriesList.length === 0 ? (
                <div
                  className="rounded-xl border px-4 py-6 text-center"
                  style={{
                    background: "var(--app-bg)",
                    borderColor: "var(--app-border)",
                    color: "var(--app-text-muted)",
                  }}
                >
                  등록된 고정 스케줄이 없습니다.
                </div>
              ) : (
                sortedFixedSeriesList.map((series) => {
                  const colors = getScheduleColorsByKey(series.color_key);
                  const expanded = expandedSeriesId === series.series_id;

                  return (
                    <div
                      key={series.series_id}
                      className="rounded-xl border p-4"
                      style={{
                        background: "var(--app-bg)",
                        borderColor: "var(--app-border)",
                      }}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <button
                          type="button"
                          onClick={() => handleToggleSeriesDetail(series.series_id)}
                          className="text-left min-w-0 flex-1"
                        >
                          <div className="flex items-center gap-2 flex-wrap">
                            <div
                              className="w-3 h-3 rounded-full"
                              style={{ background: colors.bg }}
                            />
                            <div
                              className="font-bold text-base"
                              style={{ color: "var(--app-text)" }}
                            >
                              {series.title}
                            </div>
                          </div>

                          <div className="mt-2 space-y-1">
                            {series.rules.map((rule) => (
                              <div
                                key={rule.rule_id}
                                className="text-sm"
                                style={{ color: "var(--app-text-muted)" }}
                              >
                                {formatRuleSummary(rule)}
                              </div>
                            ))}
                          </div>
                        </button>

                        <div className="flex flex-col gap-2 shrink-0">
                          <button
                            type="button"
                            onClick={() => handleAddRuleToSeries(series)}
                            className="px-3 py-2 rounded-lg font-semibold text-sm"
                            style={{
                              background: "var(--card-yellow-bg)",
                              color: "var(--card-yellow-text)",
                            }}
                          >
                            추가
                          </button>

                          <button
                            type="button"
                            onClick={() => handleDeleteSeries(series.series_id)}
                            className="px-3 py-2 rounded-lg font-semibold text-sm"
                            style={{
                              background: "var(--card-red-bg)",
                              color: "var(--card-red-text)",
                            }}
                          >
                            전체 삭제
                          </button>
                        </div>
                      </div>

                      {expanded && (
                        <div
                          className="mt-4 pt-4 border-t space-y-3"
                          style={{ borderColor: "var(--app-border)" }}
                        >
                          {series.rules.flatMap((rule) =>
                            expandRuleToDetailItems(series, rule).map((item) => (
                              <div
                                key={item.id}
                                className="rounded-lg border p-3"
                                style={{
                                  background: "var(--app-surface)",
                                  borderColor: "var(--app-border)",
                                }}
                              >
                                <div className="flex items-start justify-between gap-3">
                                  <div>
                                    <div
                                      className="font-semibold"
                                      style={{ color: "var(--app-text)" }}
                                    >
                                      {item.title}
                                    </div>
                                    <div
                                      className="text-sm mt-1"
                                      style={{ color: "var(--app-text-muted)" }}
                                    >
                                      {item.label} {formatTimeRange(item.start_time, item.end_time)}
                                    </div>
                                  </div>

                                  <div className="flex flex-col gap-2 shrink-0">
                                    <button
                                      type="button"
                                      onClick={() => handleEditDetail(series, item)}
                                      className="px-3 py-2 rounded-lg font-semibold text-sm"
                                      style={{
                                        background: "var(--card-blue-bg)",
                                        color: "var(--card-blue-text)",
                                      }}
                                    >
                                      수정
                                    </button>

                                    <button
                                      type="button"
                                      onClick={() =>
                                        handleDeleteDetail(series.series_id, item)
                                      }
                                      className="px-3 py-2 rounded-lg font-semibold text-sm"
                                      style={{
                                        background: "var(--card-red-bg)",
                                        color: "var(--card-red-text)",
                                      }}
                                    >
                                      삭제
                                    </button>
                                  </div>
                                </div>
                              </div>
                            ))
                          )}
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </section>
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-[420px_1fr] gap-6">
          <section
            className="rounded-2xl border p-5 shadow-sm"
            style={{
              background: "var(--app-surface)",
              borderColor: "var(--app-border)",
            }}
          >
            <div className="flex items-center justify-between mb-4">
              <h2
                className="text-xl font-bold"
                style={{ color: "var(--app-text)" }}
              >
                {editingVariableId ? "변동 스케줄 수정" : "변동 스케줄 등록"}
              </h2>

              {editingVariableId && (
                <button
                  type="button"
                  onClick={handleCancelVariableEdit}
                  className="px-3 py-2 rounded-lg text-sm font-semibold"
                  style={{
                    background: "var(--app-surface-muted)",
                    color: "var(--app-text)",
                  }}
                >
                  수정 취소
                </button>
              )}
            </div>

            <form onSubmit={handleVariableSubmit} className="space-y-4">
              <div>
                <label
                  className="block text-sm font-semibold mb-2"
                  style={{ color: "var(--app-text)" }}
                >
                  일정 이름
                </label>
                <input
                  value={variableForm.title}
                  onChange={(e) =>
                    setVariableForm((prev) => ({
                      ...prev,
                      title: e.target.value,
                    }))
                  }
                  placeholder="예: 운영체제 과제"
                  className="w-full rounded-xl border px-3 py-2 outline-none"
                  style={{
                    background: "var(--app-bg)",
                    borderColor: "var(--app-border)",
                    color: "var(--app-text)",
                  }}
                />
              </div>

              <div>
                <label
                  className="block text-sm font-semibold mb-2"
                  style={{ color: "var(--app-text)" }}
                >
                  소요 시간
                </label>
                <input
                  type="number"
                  min={1}
                  value={variableForm.estimated_time}
                  onChange={(e) =>
                    setVariableForm((prev) => ({
                      ...prev,
                      estimated_time: e.target.value,
                    }))
                  }
                  placeholder="분 단위 입력"
                  className="w-full rounded-xl border px-3 py-2 outline-none"
                  style={{
                    background: "var(--app-bg)",
                    borderColor: "var(--app-border)",
                    color: "var(--app-text)",
                  }}
                />
              </div>

              <div>
                <label
                  className="block text-sm font-semibold mb-2"
                  style={{ color: "var(--app-text)" }}
                >
                  난이도 및 피로도
                </label>
                <input
                  type="number"
                  min={0}
                  max={10}
                  value={variableForm.level}
                  onChange={(e) =>
                    setVariableForm((prev) => ({
                      ...prev,
                      level: e.target.value,
                    }))
                  }
                  className="w-full rounded-xl border px-3 py-2 outline-none"
                  style={{
                    background: "var(--app-bg)",
                    borderColor: "var(--app-border)",
                    color: "var(--app-text)",
                  }}
                />
              </div>

              <div>
                <label
                  className="block text-sm font-semibold mb-2"
                  style={{ color: "var(--app-text)" }}
                >
                  마감 기한
                </label>
                <input
                  type="datetime-local"
                  value={variableForm.deadline}
                  onChange={(e) =>
                    setVariableForm((prev) => ({
                      ...prev,
                      deadline: e.target.value,
                    }))
                  }
                  className="w-full rounded-xl border px-3 py-2 outline-none"
                  style={{
                    background: "var(--app-bg)",
                    borderColor: "var(--app-border)",
                    color: "var(--app-text)",
                  }}
                />
              </div>

              <button
                type="submit"
                className="w-full rounded-xl py-3 font-semibold transition hover:opacity-90"
                style={{
                  background: "var(--primary-button-bg)",
                  color: "var(--primary-button-text)",
                }}
              >
                {editingVariableId ? "변동 스케줄 저장" : "변동 스케줄 추가"}
              </button>
            </form>
          </section>

          <section
            className="rounded-2xl border p-5 shadow-sm"
            style={{
              background: "var(--app-surface)",
              borderColor: "var(--app-border)",
            }}
          >
            <div className="flex items-center justify-between mb-4">
              <h2
                className="text-xl font-bold"
                style={{ color: "var(--app-text)" }}
              >
                등록된 변동 스케줄
              </h2>
              <span
                className="text-sm font-medium"
                style={{ color: "var(--app-text-muted)" }}
              >
                총 {sortedVariableList.length}개
              </span>
            </div>

            <div className="space-y-3">
              {sortedVariableList.length === 0 ? (
                <div
                  className="rounded-xl border px-4 py-6 text-center"
                  style={{
                    background: "var(--app-bg)",
                    borderColor: "var(--app-border)",
                    color: "var(--app-text-muted)",
                  }}
                >
                  등록된 변동 스케줄이 없습니다.
                </div>
              ) : (
                sortedVariableList.map((schedule) => (
                  <div
                    key={schedule.id}
                    className="rounded-xl border p-4"
                    style={{
                      background: "var(--app-bg)",
                      borderColor: "var(--app-border)",
                    }}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1">
                        <div
                          className="font-bold text-base"
                          style={{ color: "var(--app-text)" }}
                        >
                          {schedule.title}
                        </div>

                        <div
                          className="text-sm"
                          style={{ color: "var(--app-text-muted)" }}
                        >
                          예상 소요 시간: {schedule.estimated_time}분
                        </div>

                        <div
                          className="text-sm"
                          style={{ color: "var(--app-text-muted)" }}
                        >
                          난이도/피로도: {schedule.level} ({getLevelLabel(schedule.level)})
                        </div>

                        <div
                          className="text-sm"
                          style={{ color: "var(--app-text-muted)" }}
                        >
                          마감: {formatDeadline(schedule.deadline)}
                        </div>

                        <div className="flex items-center gap-2 pt-1">
                          <span
                            className="px-2 py-1 rounded-full text-xs font-semibold"
                            style={{
                              background: schedule.is_done
                                ? "var(--card-green-bg)"
                                : "var(--card-yellow-bg)",
                              color: schedule.is_done
                                ? "var(--card-green-text)"
                                : "var(--card-yellow-text)",
                            }}
                          >
                            {schedule.is_done ? "완료" : "진행 전"}
                          </span>
                        </div>
                      </div>

                      <div className="flex flex-col gap-2">
                        <button
                          type="button"
                          onClick={() => handleEditVariable(schedule)}
                          className="px-3 py-2 rounded-lg font-semibold text-sm"
                          style={{
                            background: "var(--card-blue-bg)",
                            color: "var(--card-blue-text)",
                          }}
                        >
                          수정
                        </button>

                        <button
                          type="button"
                          onClick={() => handleToggleDone(schedule.id)}
                          className="px-3 py-2 rounded-lg font-semibold text-sm"
                          style={{
                            background: "var(--card-green-bg)",
                            color: "var(--card-green-text)",
                          }}
                        >
                          완료 전환
                        </button>

                        <button
                          type="button"
                          onClick={() => handleDeleteVariable(schedule.id)}
                          className="px-3 py-2 rounded-lg font-semibold text-sm"
                          style={{
                            background: "var(--card-red-bg)",
                            color: "var(--card-red-text)",
                          }}
                        >
                          삭제
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}