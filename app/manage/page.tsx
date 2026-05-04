"use client";

import { useEffect, useMemo, useState } from "react";
import {
  type DayCode,
  type FailReason,
  type FixedScheduleSeries,
  type MonthRule,
  type RepeatType,
  type VariableSchedule,
  colorOptions,
  dayOptions,
  expandRuleToDetailItems,
  failReasonOptions,
  formatDeadline,
  formatRuleSummary,
  formatTimeRange,
  getEffectiveVariableStatus,
  getFailReasonLabel,
  getFixedScheduleSeries,
  getLevelLabel,
  getNextColorKey,
  getScheduleColorsByKey,
  getStatusLabel,
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
  color_key: number;
  level: string;
};

type VariableFormState = {
  title: string;
  estimated_time: string;
  level: string;
  color_key: number;
  deadline: string;
};

type EditingFixedDetailState = {
  series_id: string;
  rule_id: string;
  freq_type: RepeatType;
  target_day: DayCode | null;
  target_month_day: number | null;
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
  color_key: 0,
  level: "5",
};

const variableInitialForm: VariableFormState = {
  title: "",
  estimated_time: "",
  level: "5",
  color_key: 0,
  deadline: "",
};

function toTimeWithSeconds(value: string) {
  return value.length === 5 ? `${value}:00` : value;
}

function toDeadlineWithTimezone(value: string) {
  return `${value}:00+09:00`;
}

function toDateTimeLocalValue(value: string) {
  const date = parseKstDateString(value);
  if (Number.isNaN(date.getTime())) return "";

  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(
    date.getDate()
  ).padStart(2, "0")}T${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

function createVariableFormFromItem(item: VariableSchedule): VariableFormState {
  return {
    title: item.title,
    estimated_time: String(item.estimated_time),
    level: String(item.level),
    color_key: item.color_key ?? 0,
    deadline: toDateTimeLocalValue(item.deadline),
  };
}

function removeFixedDetailFromSeries(series: FixedScheduleSeries, target: EditingFixedDetailState): FixedScheduleSeries {
  const nextRules = series.rules
    .map((rule) => {
      if (rule.rule_id !== target.rule_id) return rule;

      if (target.freq_type === "MONTHLY") {
        if (rule.month_rule === "CUSTOM" && target.target_month_day !== null) {
          return {
            ...rule,
            month_days: rule.month_days.filter((day) => day !== target.target_month_day),
            updated_at: new Date().toISOString(),
          };
        }

        return null;
      }

      if (target.target_day !== null) {
        return {
          ...rule,
          days: rule.days.filter((day) => day !== target.target_day),
          updated_at: new Date().toISOString(),
        };
      }

      return rule;
    })
    .filter((rule): rule is FixedScheduleSeries["rules"][number] => {
      if (!rule) return false;
      if (rule.freq_type === "MONTHLY" && rule.month_rule === "CUSTOM") return rule.month_days.length > 0;
      if (rule.freq_type === "WEEKLY" || rule.freq_type === "BIWEEKLY") return rule.days.length > 0;
      return true;
    });

  return {
    ...series,
    rules: nextRules,
    updated_at: new Date().toISOString(),
  };
}

export default function ManagePage() {
  const [activeTab, setActiveTab] = useState<"fixed" | "variable">("fixed");
  const [variableStatusTab, setVariableStatusTab] = useState<"pending" | "done" | "failed">("pending");

  const [fixedForm, setFixedForm] = useState<FixedFormState>(fixedInitialForm);
  const [variableForm, setVariableForm] = useState<VariableFormState>(variableInitialForm);

  const [fixedSeriesList, setFixedSeriesList] = useState<FixedScheduleSeries[]>([]);
  const [variableList, setVariableList] = useState<VariableSchedule[]>([]);

  const [expandedSeriesId, setExpandedSeriesId] = useState<string | null>(null);
  const [editingSeriesId, setEditingSeriesId] = useState<string | null>(null);
  const [editingFixedDetail, setEditingFixedDetail] = useState<EditingFixedDetailState | null>(null);
  const [editingVariableId, setEditingVariableId] = useState<string | null>(null);

  const [failModalTargetId, setFailModalTargetId] = useState<string | null>(null);
  const [selectedFailReason, setSelectedFailReason] = useState<FailReason>("TIME_SHORTAGE");
  const [failReasonText, setFailReasonText] = useState("");

  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    const fixedData = getFixedScheduleSeries();
    const variableData = getVariableSchedules();

    setFixedSeriesList(fixedData);
    setVariableList(variableData);
    setFixedForm((prev) => ({ ...prev, color_key: getNextColorKey(fixedData) }));
    setVariableForm((prev) => ({ ...prev, color_key: getNextColorKey(variableData) }));
    setIsLoaded(true);
  }, []);

  useEffect(() => {
    if (isLoaded) saveFixedScheduleSeries(fixedSeriesList);
  }, [fixedSeriesList, isLoaded]);

  useEffect(() => {
    if (isLoaded) saveVariableSchedules(variableList);
  }, [variableList, isLoaded]);

  const sortedFixedSeriesList = useMemo(
    () => [...fixedSeriesList].sort((a, b) => a.title.localeCompare(b.title)),
    [fixedSeriesList]
  );

  const variableCounts = useMemo(() => {
    return variableList.reduce(
      (acc, item) => {
        const status = getEffectiveVariableStatus(item);
        acc[status] += 1;
        return acc;
      },
      { pending: 0, done: 0, failed: 0 }
    );
  }, [variableList]);

  const filteredVariableList = useMemo(() => {
    return [...variableList]
      .filter((item) => getEffectiveVariableStatus(item) === variableStatusTab)
      .sort((a, b) => parseKstDateString(a.deadline).getTime() - parseKstDateString(b.deadline).getTime());
  }, [variableList, variableStatusTab]);

  const resetFixedForm = () => {
    setEditingSeriesId(null);
    setEditingFixedDetail(null);
    setFixedForm({ ...fixedInitialForm, color_key: getNextColorKey(fixedSeriesList) });
  };

  const resetVariableForm = () => {
    setEditingVariableId(null);
    setVariableForm({ ...variableInitialForm, color_key: getNextColorKey(variableList) });
  };

  const buildRuleFromFixedForm = (ruleId: string, now: string): FixedScheduleSeries["rules"][number] => {
    return {
      id: ruleId,
      rule_id: ruleId,
      freq_type: fixedForm.freq_type,
      days: fixedForm.freq_type === "MONTHLY" ? [] : fixedForm.selected_days,
      month_rule: fixedForm.freq_type === "MONTHLY" ? fixedForm.month_rule : null,
      month_days:
        fixedForm.freq_type === "MONTHLY" && fixedForm.month_rule === "CUSTOM" ? fixedForm.selected_month_days : [],
      biweekly_start_date: fixedForm.freq_type === "BIWEEKLY" ? fixedForm.biweekly_start_date : null,
      start_time: toTimeWithSeconds(fixedForm.start_time),
      end_time: toTimeWithSeconds(fixedForm.end_time),
      created_at: now,
      updated_at: now,
    };
  };

  const handleFixedSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!fixedForm.title.trim() || !fixedForm.start_time || !fixedForm.end_time) return;
    if ((fixedForm.freq_type === "WEEKLY" || fixedForm.freq_type === "BIWEEKLY") && fixedForm.selected_days.length === 0)
      return;
    if (fixedForm.freq_type === "BIWEEKLY" && !fixedForm.biweekly_start_date) return;
    if (fixedForm.freq_type === "MONTHLY" && fixedForm.month_rule === "CUSTOM" && fixedForm.selected_month_days.length === 0)
      return;

    const now = new Date().toISOString();

    if (editingFixedDetail) {
      const newSeriesId = `series-${Date.now()}`;
      const newRuleId = `rule-${Date.now()}`;

      const newSeries: FixedScheduleSeries = {
        id: newSeriesId,
        series_id: newSeriesId,
        user_id: "test_user",
        title: fixedForm.title.trim(),
        color_key: fixedForm.color_key,
        level: Number(fixedForm.level),
        created_at: now,
        updated_at: now,
        rules: [buildRuleFromFixedForm(newRuleId, now)],
      };

      setFixedSeriesList((prev) => {
        const removed = prev
          .map((series) =>
            series.series_id === editingFixedDetail.series_id ? removeFixedDetailFromSeries(series, editingFixedDetail) : series
          )
          .filter((series) => series.rules.length > 0);

        return [...removed, newSeries];
      });

      setExpandedSeriesId(newSeries.series_id);
      resetFixedForm();
      return;
    }

    const seriesId = editingSeriesId ?? `series-${Date.now()}`;
    const ruleId = `rule-${Date.now()}`;

    const nextSeries: FixedScheduleSeries = {
      id: seriesId,
      series_id: seriesId,
      user_id: "test_user",
      title: fixedForm.title.trim(),
      color_key: fixedForm.color_key,
      level: Number(fixedForm.level),
      created_at: now,
      updated_at: now,
      rules: [buildRuleFromFixedForm(ruleId, now)],
    };

    setFixedSeriesList((prev) =>
      editingSeriesId
        ? prev.map((series) =>
            series.series_id === editingSeriesId
              ? { ...nextSeries, created_at: series.created_at, id: series.id, series_id: series.series_id }
              : series
          )
        : [...prev, nextSeries]
    );

    setExpandedSeriesId(nextSeries.series_id);
    resetFixedForm();
  };

  const handleEditSeries = (series: FixedScheduleSeries) => {
    const rule = series.rules[0];

    setActiveTab("fixed");
    setEditingFixedDetail(null);
    setEditingSeriesId(series.series_id);
    setFixedForm({
      title: series.title,
      start_time: rule.start_time.slice(0, 5),
      end_time: rule.end_time.slice(0, 5),
      freq_type: rule.freq_type,
      selected_days: rule.days.length > 0 ? rule.days : ["MON"],
      month_rule: rule.month_rule ?? "START",
      selected_month_days: rule.month_days.length > 0 ? rule.month_days : [1],
      biweekly_start_date: rule.biweekly_start_date ?? "",
      color_key: series.color_key,
      level: String(series.level ?? 5),
    });
  };

  const handleEditFixedDetail = (
    series: FixedScheduleSeries,
    item: ReturnType<typeof expandRuleToDetailItems>[number]
  ) => {
    const rule = series.rules.find((ruleItem) => ruleItem.rule_id === item.rule_id);
    if (!rule) return;

    setActiveTab("fixed");
    setEditingSeriesId(null);
    setEditingFixedDetail({
      series_id: series.series_id,
      rule_id: item.rule_id,
      freq_type: item.freq_type,
      target_day: item.target_day,
      target_month_day: item.target_month_day,
    });

    setFixedForm({
      title: series.title,
      start_time: item.start_time.slice(0, 5),
      end_time: item.end_time.slice(0, 5),
      freq_type: item.freq_type,
      selected_days: item.target_day ? [item.target_day] : rule.days.length > 0 ? rule.days : ["MON"],
      month_rule: rule.month_rule ?? "START",
      selected_month_days:
        item.target_month_day !== null ? [item.target_month_day] : rule.month_days.length > 0 ? rule.month_days : [1],
      biweekly_start_date: item.biweekly_start_date ?? "",
      color_key: series.color_key,
      level: String(series.level ?? 5),
    });
  };

  const handleDeleteFixedDetail = (
    series: FixedScheduleSeries,
    item: ReturnType<typeof expandRuleToDetailItems>[number]
  ) => {
    const target: EditingFixedDetailState = {
      series_id: series.series_id,
      rule_id: item.rule_id,
      freq_type: item.freq_type,
      target_day: item.target_day,
      target_month_day: item.target_month_day,
    };

    setFixedSeriesList((prev) =>
      prev
        .map((seriesItem) => (seriesItem.series_id === series.series_id ? removeFixedDetailFromSeries(seriesItem, target) : seriesItem))
        .filter((seriesItem) => seriesItem.rules.length > 0)
    );

    if (editingFixedDetail?.series_id === series.series_id && editingFixedDetail.rule_id === item.rule_id) {
      resetFixedForm();
    }
  };

  const handleDeleteSeries = (seriesId: string) => {
    setFixedSeriesList((prev) => prev.filter((series) => series.series_id !== seriesId));
    if (expandedSeriesId === seriesId) setExpandedSeriesId(null);
    if (editingSeriesId === seriesId || editingFixedDetail?.series_id === seriesId) resetFixedForm();
  };

  const handleVariableSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!variableForm.title.trim() || Number(variableForm.estimated_time) <= 0 || !variableForm.deadline) return;
    if (Number(variableForm.level) < 0 || Number(variableForm.level) > 10) return;

    const now = new Date().toISOString();
    const existing = editingVariableId ? variableList.find((item) => item.id === editingVariableId) : null;

    const nextItem: VariableSchedule = {
      id: existing?.id ?? `variable-${Date.now()}`,
      user_id: "test_user",
      title: variableForm.title.trim(),
      estimated_time: Number(variableForm.estimated_time),
      is_done: existing?.is_done ?? false,
      status: existing?.status ?? "pending",
      level: Number(variableForm.level),
      color_key: variableForm.color_key,
      deadline: toDeadlineWithTimezone(variableForm.deadline),
      scheduled_start: existing?.scheduled_start ?? null,
      scheduled_end: existing?.scheduled_end ?? null,
      fail_reason: existing?.fail_reason ?? null,
      fail_reason_text: existing?.fail_reason_text ?? null,
      priority: existing?.priority ?? null,
      created_at: existing?.created_at ?? now,
      updated_at: now,
    };

    setVariableList((prev) =>
      editingVariableId ? prev.map((item) => (item.id === editingVariableId ? nextItem : item)) : [...prev, nextItem]
    );

    resetVariableForm();
  };

  const handleEditVariable = (item: VariableSchedule) => {
    setActiveTab("variable");
    setEditingVariableId(item.id);
    setVariableForm(createVariableFormFromItem(item));
  };

  const handleMarkDone = (id: string) => {
    setVariableList((prev) =>
      prev.map((item) =>
        item.id === id
          ? {
              ...item,
              is_done: true,
              status: "done",
              fail_reason: null,
              fail_reason_text: null,
              updated_at: new Date().toISOString(),
            }
          : item
      )
    );
  };

  const openFailModal = (id: string) => {
    setFailModalTargetId(id);
    setSelectedFailReason("TIME_SHORTAGE");
    setFailReasonText("");
  };

  const closeFailModal = () => {
    setFailModalTargetId(null);
    setSelectedFailReason("TIME_SHORTAGE");
    setFailReasonText("");
  };

  const handleConfirmFail = () => {
    if (!failModalTargetId) return;

    setVariableList((prev) =>
      prev.map((item) =>
        item.id === failModalTargetId
          ? {
              ...item,
              is_done: false,
              status: "failed",
              fail_reason: selectedFailReason,
              fail_reason_text: failReasonText.trim() || null,
              updated_at: new Date().toISOString(),
            }
          : item
      )
    );

    closeFailModal();
    setVariableStatusTab("failed");
  };

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2" style={{ color: "var(--app-text)" }}>
        일정 관리
      </h1>

      <p className="mb-6" style={{ color: "var(--app-text-muted)" }}>
        고정 일정과 변동 일정을 등록하고, 색상·피로도·완료·실패 상태를 함께 관리합니다.
      </p>

      <div className="flex gap-2 mb-6">
        {[
          { id: "fixed", label: "고정 스케줄" },
          { id: "variable", label: "변동 스케줄" },
        ].map((tab) => {
          const active = activeTab === tab.id;

          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as "fixed" | "variable")}
              className="px-4 py-2 rounded-full font-semibold"
              style={{
                background: active ? "var(--primary-button-bg)" : "var(--app-surface)",
                color: active ? "var(--primary-button-text)" : "var(--app-text)",
                border: "1px solid var(--app-border)",
              }}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {activeTab === "fixed" ? (
        <div className="grid grid-cols-1 xl:grid-cols-[420px_1fr] gap-6">
          <section
            className="rounded-2xl border p-5 shadow-sm"
            style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}
          >
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold" style={{ color: "var(--app-text)" }}>
                {editingFixedDetail ? "고정 스케줄 개별 항목 수정" : editingSeriesId ? "고정 스케줄 수정" : "고정 스케줄 등록"}
              </h2>

              {(editingSeriesId || editingFixedDetail) && (
                <button
                  type="button"
                  onClick={resetFixedForm}
                  className="px-3 py-2 rounded-lg text-sm font-semibold"
                  style={{ background: "var(--app-surface-muted)", color: "var(--app-text)" }}
                >
                  취소
                </button>
              )}
            </div>

            <form onSubmit={handleFixedSubmit} className="space-y-4">
              <InputLabel label="일정 이름">
                <input
                  value={fixedForm.title}
                  onChange={(e) => setFixedForm((p) => ({ ...p, title: e.target.value }))}
                  placeholder="예: 출근"
                  className="form-input"
                />
              </InputLabel>

              <div className="grid grid-cols-2 gap-3">
                <InputLabel label="시작 시간">
                  <input
                    type="time"
                    value={fixedForm.start_time}
                    onChange={(e) => setFixedForm((p) => ({ ...p, start_time: e.target.value }))}
                    className="form-input"
                  />
                </InputLabel>

                <InputLabel label="종료 시간">
                  <input
                    type="time"
                    value={fixedForm.end_time}
                    onChange={(e) => setFixedForm((p) => ({ ...p, end_time: e.target.value }))}
                    className="form-input"
                  />
                </InputLabel>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <InputLabel label="일정 색상">
                  <select
                    value={fixedForm.color_key}
                    onChange={(e) => setFixedForm((p) => ({ ...p, color_key: Number(e.target.value) }))}
                    className="form-input"
                  >
                    {colorOptions.map((color) => (
                      <option key={color.key} value={color.key}>
                        {color.label}
                      </option>
                    ))}
                  </select>
                </InputLabel>

                <InputLabel label="피로도">
                  <input
                    type="number"
                    min="0"
                    max="10"
                    value={fixedForm.level}
                    onChange={(e) => setFixedForm((p) => ({ ...p, level: e.target.value }))}
                    className="form-input"
                  />
                </InputLabel>
              </div>

              <InputLabel label="반복 유형">
                <select
                  value={fixedForm.freq_type}
                  onChange={(e) => setFixedForm((p) => ({ ...p, freq_type: e.target.value as RepeatType }))}
                  className="form-input"
                >
                  <option value="WEEKLY">매주</option>
                  <option value="BIWEEKLY">격주</option>
                  <option value="MONTHLY">매월</option>
                </select>
              </InputLabel>

              {(fixedForm.freq_type === "WEEKLY" || fixedForm.freq_type === "BIWEEKLY") && (
                <div>
                  <FormLabel>요일 선택</FormLabel>
                  <div className="grid grid-cols-7 gap-2">
                    {dayOptions.map((day) => (
                      <ToggleButton
                        key={day.code}
                        selected={fixedForm.selected_days.includes(day.code)}
                        onClick={() =>
                          setFixedForm((p) => ({
                            ...p,
                            selected_days: toggleSelectedDay(p.selected_days, day.code),
                          }))
                        }
                      >
                        {day.label}
                      </ToggleButton>
                    ))}
                  </div>
                </div>
              )}

              {fixedForm.freq_type === "BIWEEKLY" && (
                <InputLabel label="격주 시작일">
                  <input
                    type="date"
                    value={fixedForm.biweekly_start_date}
                    onChange={(e) => setFixedForm((p) => ({ ...p, biweekly_start_date: e.target.value }))}
                    className="form-input"
                  />
                </InputLabel>
              )}

              {fixedForm.freq_type === "MONTHLY" && (
                <div className="space-y-3">
                  <div>
                    <FormLabel>월간 반복 방식</FormLabel>
                    <div className="grid grid-cols-2 gap-2">
                      {monthRuleOptions.map((option) => (
                        <ToggleButton
                          key={option.value}
                          selected={fixedForm.month_rule === option.value}
                          onClick={() => setFixedForm((p) => ({ ...p, month_rule: option.value }))}
                        >
                          {option.label}
                        </ToggleButton>
                      ))}
                    </div>
                  </div>

                  {fixedForm.month_rule === "CUSTOM" && (
                    <div>
                      <FormLabel>기타 날짜 선택</FormLabel>
                      <div className="grid grid-cols-7 gap-2">
                        {Array.from({ length: 31 }, (_, index) => index + 1).map((day) => (
                          <ToggleButton
                            key={day}
                            selected={fixedForm.selected_month_days.includes(day)}
                            onClick={() =>
                              setFixedForm((p) => ({
                                ...p,
                                selected_month_days: toggleSelectedMonthDay(p.selected_month_days, day),
                              }))
                            }
                          >
                            {day}
                          </ToggleButton>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <button
                type="submit"
                className="w-full rounded-xl py-3 font-semibold hover:opacity-90"
                style={{ background: "var(--primary-button-bg)", color: "var(--primary-button-text)" }}
              >
                {editingFixedDetail ? "개별 항목 저장" : editingSeriesId ? "고정 스케줄 저장" : "고정 스케줄 추가"}
              </button>
            </form>
          </section>

          <section
            className="rounded-2xl border p-5 shadow-sm"
            style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}
          >
            <h2 className="text-xl font-bold mb-4" style={{ color: "var(--app-text)" }}>
              등록된 고정 스케줄
            </h2>

            <div className="space-y-3">
              {sortedFixedSeriesList.length === 0 ? (
                <EmptyText>등록된 고정 스케줄이 없습니다.</EmptyText>
              ) : (
                sortedFixedSeriesList.map((series) => {
                  const colors = getScheduleColorsByKey(series.color_key);
                  const expanded = expandedSeriesId === series.series_id;

                  return (
                    <div
                      key={series.series_id}
                      className="rounded-xl border p-4"
                      style={{ background: "var(--app-bg)", borderColor: "var(--app-border)" }}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <button
                          type="button"
                          onClick={() => setExpandedSeriesId(expanded ? null : series.series_id)}
                          className="text-left min-w-0 flex-1"
                        >
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="w-3 h-3 rounded-full" style={{ background: colors.bg }} />
                            <strong style={{ color: "var(--app-text)" }}>{series.title}</strong>
                            <span className="text-xs px-2 py-1 rounded-full" style={{ background: colors.bg, color: colors.text }}>
                              피로도 {series.level} · {getLevelLabel(series.level)}
                            </span>
                          </div>

                          <div className="mt-2 space-y-1">
                            {series.rules.map((rule) => (
                              <div key={rule.rule_id} className="text-sm" style={{ color: "var(--app-text-muted)" }}>
                                {formatRuleSummary(rule)}
                              </div>
                            ))}
                          </div>
                        </button>

                        <div className="flex flex-col gap-2 shrink-0">
                          <button type="button" onClick={() => handleEditSeries(series)} className="small-blue">
                            묶음 수정
                          </button>
                          <button type="button" onClick={() => handleDeleteSeries(series.series_id)} className="small-red">
                            묶음 삭제
                          </button>
                        </div>
                      </div>

                      {expanded && (
                        <div className="mt-4 pt-4 border-t space-y-2" style={{ borderColor: "var(--app-border)" }}>
                          {series.rules.flatMap((rule) => expandRuleToDetailItems(series, rule)).map((item) => (
                            <div
                              key={item.id}
                              className="rounded-lg border p-3 text-sm"
                              style={{
                                background: "var(--app-surface)",
                                borderColor: "var(--app-border)",
                                color: "var(--app-text-muted)",
                              }}
                            >
                              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                                <div>
                                  {item.label} {formatTimeRange(item.start_time, item.end_time)}
                                </div>

                                <div className="flex gap-2 shrink-0">
                                  <button
                                    type="button"
                                    onClick={() => handleEditFixedDetail(series, item)}
                                    className="small-blue"
                                  >
                                    개별 수정
                                  </button>

                                  <button
                                    type="button"
                                    onClick={() => handleDeleteFixedDetail(series, item)}
                                    className="small-red"
                                  >
                                    개별 삭제
                                  </button>
                                </div>
                              </div>
                            </div>
                          ))}
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
            style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}
          >
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold" style={{ color: "var(--app-text)" }}>
                {editingVariableId ? "변동 스케줄 수정" : "변동 스케줄 등록"}
              </h2>

              {editingVariableId && (
                <button
                  type="button"
                  onClick={resetVariableForm}
                  className="px-3 py-2 rounded-lg text-sm font-semibold"
                  style={{ background: "var(--app-surface-muted)", color: "var(--app-text)" }}
                >
                  취소
                </button>
              )}
            </div>

            <form onSubmit={handleVariableSubmit} className="space-y-4">
              <InputLabel label="일정 이름">
                <input
                  value={variableForm.title}
                  onChange={(e) => setVariableForm((p) => ({ ...p, title: e.target.value }))}
                  placeholder="예: 과제 제출"
                  className="form-input"
                />
              </InputLabel>

              <InputLabel label="예상 소요 시간(분)">
                <input
                  type="number"
                  min="1"
                  value={variableForm.estimated_time}
                  onChange={(e) => setVariableForm((p) => ({ ...p, estimated_time: e.target.value }))}
                  className="form-input"
                />
              </InputLabel>

              <div className="grid grid-cols-2 gap-3">
                <InputLabel label="난이도 및 피로도">
                  <input
                    type="number"
                    min="0"
                    max="10"
                    value={variableForm.level}
                    onChange={(e) => setVariableForm((p) => ({ ...p, level: e.target.value }))}
                    className="form-input"
                  />
                </InputLabel>

                <InputLabel label="일정 색상">
                  <select
                    value={variableForm.color_key}
                    onChange={(e) => setVariableForm((p) => ({ ...p, color_key: Number(e.target.value) }))}
                    className="form-input"
                  >
                    {colorOptions.map((color) => (
                      <option key={color.key} value={color.key}>
                        {color.label}
                      </option>
                    ))}
                  </select>
                </InputLabel>
              </div>

              <InputLabel label="마감 기한">
                <input
                  type="datetime-local"
                  value={variableForm.deadline}
                  onChange={(e) => setVariableForm((p) => ({ ...p, deadline: e.target.value }))}
                  className="form-input"
                />
              </InputLabel>

              <button
                type="submit"
                className="w-full rounded-xl py-3 font-semibold hover:opacity-90"
                style={{ background: "var(--primary-button-bg)", color: "var(--primary-button-text)" }}
              >
                {editingVariableId ? "변동 스케줄 저장" : "변동 스케줄 추가"}
              </button>
            </form>
          </section>

          <section
            className="rounded-2xl border p-5 shadow-sm"
            style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}
          >
            <h2 className="text-xl font-bold mb-4" style={{ color: "var(--app-text)" }}>
              등록된 변동 스케줄
            </h2>

            <div className="grid grid-cols-3 gap-2 mb-4">
              {[
                { id: "pending", label: "미완료", count: variableCounts.pending },
                { id: "done", label: "완료", count: variableCounts.done },
                { id: "failed", label: "실패", count: variableCounts.failed },
              ].map((tab) => {
                const active = variableStatusTab === tab.id;

                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setVariableStatusTab(tab.id as "pending" | "done" | "failed")}
                    className="rounded-xl px-3 py-3 text-sm font-bold"
                    style={{
                      background: active ? "var(--primary-button-bg)" : "var(--app-bg)",
                      color: active ? "var(--primary-button-text)" : "var(--app-text)",
                      border: "1px solid var(--app-border)",
                    }}
                  >
                    {tab.label} {tab.count}
                  </button>
                );
              })}
            </div>

            <div className="space-y-3">
              {filteredVariableList.length === 0 ? (
                <EmptyText>해당 상태의 변동 스케줄이 없습니다.</EmptyText>
              ) : (
                filteredVariableList.map((schedule) => {
                  const colors = getScheduleColorsByKey(schedule.color_key);
                  const status = getEffectiveVariableStatus(schedule);
                  const failLabel = getFailReasonLabel(schedule.fail_reason);

                  return (
                    <div
                      key={schedule.id}
                      className="rounded-xl border p-4"
                      style={{ background: colors.bg, borderColor: colors.border }}
                    >
                      <div className="flex flex-col lg:flex-row lg:justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <strong style={{ color: colors.text }}>{schedule.title}</strong>
                            <span
                              className="text-xs px-2 py-1 rounded-full font-bold"
                              style={{ background: "var(--app-surface)", color: colors.text }}
                            >
                              {getStatusLabel(status)}
                            </span>
                          </div>

                          <div className="text-sm mt-2" style={{ color: colors.text }}>
                            마감: {formatDeadline(schedule.deadline)} · {schedule.estimated_time}분 · 피로도{" "}
                            {schedule.level} ({getLevelLabel(schedule.level)})
                          </div>

                          {status === "failed" && (
                            <div className="text-sm mt-2" style={{ color: colors.text }}>
                              실패 이유: {failLabel ?? "마감 초과"}
                              {schedule.fail_reason_text ? ` / ${schedule.fail_reason_text}` : ""}
                            </div>
                          )}
                        </div>

                        <div className="flex gap-2 shrink-0 flex-wrap">
                          {status !== "done" && (
                            <button type="button" onClick={() => handleMarkDone(schedule.id)} className="small-green">
                              완료
                            </button>
                          )}

                          {status !== "failed" && (
                            <button type="button" onClick={() => openFailModal(schedule.id)} className="small-yellow">
                              실패
                            </button>
                          )}

                          <button type="button" onClick={() => handleEditVariable(schedule)} className="small-blue">
                            수정
                          </button>

                          <button
                            type="button"
                            onClick={() => setVariableList((prev) => prev.filter((item) => item.id !== schedule.id))}
                            className="small-red"
                          >
                            삭제
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </section>
        </div>
      )}

      {failModalTargetId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.45)" }}>
          <div
            className="w-full max-w-md rounded-2xl border p-5 shadow-xl"
            style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}
          >
            <h3 className="text-xl font-bold mb-2" style={{ color: "var(--app-text)" }}>
              실패 이유 선택
            </h3>

            <p className="text-sm mb-4" style={{ color: "var(--app-text-muted)" }}>
              나중에 AI가 실패 원인을 분석하고 다음 일정에 반영할 수 있도록 실패 이유를 저장합니다.
            </p>

            <div className="space-y-2 mb-4">
              {failReasonOptions.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setSelectedFailReason(option.value)}
                  className="w-full rounded-xl border px-3 py-3 text-left font-semibold"
                  style={{
                    background: selectedFailReason === option.value ? "var(--primary-button-bg)" : "var(--app-bg)",
                    color: selectedFailReason === option.value ? "var(--primary-button-text)" : "var(--app-text)",
                    borderColor: "var(--app-border)",
                  }}
                >
                  {option.label}
                </button>
              ))}
            </div>

            <textarea
              value={failReasonText}
              onChange={(e) => setFailReasonText(e.target.value)}
              placeholder="추가 메모가 있으면 입력하세요."
              className="form-input min-h-24 resize-none mb-4"
            />

            <div className="flex gap-2">
              <button
                type="button"
                onClick={closeFailModal}
                className="flex-1 rounded-xl py-3 font-bold"
                style={{ background: "var(--app-surface-muted)", color: "var(--app-text)" }}
              >
                취소
              </button>

              <button
                type="button"
                onClick={handleConfirmFail}
                className="flex-1 rounded-xl py-3 font-bold"
                style={{ background: "var(--card-red-bg)", color: "var(--card-red-text)" }}
              >
                실패 저장
              </button>
            </div>
          </div>
        </div>
      )}

      <style jsx global>{`
        .form-input {
          width: 100%;
          border-radius: 0.75rem;
          border: 1px solid var(--app-border);
          background: var(--app-bg);
          color: var(--app-text);
          padding: 0.75rem;
          outline: none;
        }

        .small-blue,
        .small-green,
        .small-red,
        .small-yellow {
          border-radius: 0.5rem;
          padding: 0.45rem 0.65rem;
          font-size: 0.8rem;
          font-weight: 700;
        }

        .small-blue {
          background: var(--card-blue-bg);
          color: var(--card-blue-text);
        }

        .small-green {
          background: var(--card-green-bg);
          color: var(--card-green-text);
        }

        .small-red {
          background: var(--card-red-bg);
          color: var(--card-red-text);
        }

        .small-yellow {
          background: var(--card-yellow-bg);
          color: var(--card-yellow-text);
        }
      `}</style>
    </div>
  );
}

function FormLabel({ children }: { children: React.ReactNode }) {
  return (
    <label className="block text-sm font-semibold mb-2" style={{ color: "var(--app-text)" }}>
      {children}
    </label>
  );
}

function InputLabel({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <FormLabel>{label}</FormLabel>
      {children}
    </div>
  );
}

function ToggleButton({
  selected,
  onClick,
  children,
}: {
  selected: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="h-11 rounded-lg border text-sm font-bold transition"
      style={{
        background: selected ? "var(--primary-button-bg)" : "var(--app-bg)",
        color: selected ? "var(--primary-button-text)" : "var(--app-text)",
        borderColor: selected ? "var(--primary-button-bg)" : "var(--app-border)",
      }}
    >
      {children}
    </button>
  );
}

function EmptyText({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="rounded-xl border p-4 text-center"
      style={{
        background: "var(--app-bg)",
        borderColor: "var(--app-border)",
        color: "var(--app-text-muted)",
      }}
    >
      {children}
    </div>
  );
}