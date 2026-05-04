"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AppSettings, readSettings } from "@/lib/settings";
import {
  type FailReason,
  type FixedScheduleSeries,
  type VariableSchedule,
  type WeekOccurrence,
  failReasonOptions,
  formatTimeRange,
  getEffectiveVariableStatus,
  getFailReasonLabel,
  getFixedScheduleSeries,
  getLevelLabel,
  getScheduleColorsByKey,
  getScheduleOccurrencesForDate,
  getStatusLabel,
  getVariableOccurrencesForDate,
  getVariableSchedules,
  saveVariableSchedules,
  timeToMinutes,
} from "@/lib/mockSchedules";

const dayNames = ["일", "월", "화", "수", "목", "금", "토"];
const HOUR_HEIGHT = 72;

function formatHour(hour: number, format: AppSettings["timeFormat"]) {
  if (format === "24h") return `${String(hour).padStart(2, "0")}:00`;

  const h = hour % 12 === 0 ? 12 : hour % 12;

  if (format === "ampm") {
    return `${h} ${hour < 12 ? "AM" : "PM"}`;
  }

  return `${hour < 12 ? "오전" : "오후"} ${h}시`;
}

function getDateKey(date: Date) {
  return `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()}`;
}

function getScheduleStyle(startTime: string, endTime: string, startHour: number, endHour: number) {
  const dayStartMinute = startHour * 60;
  const dayEndMinute = (endHour + 1) * 60;

  const rawStartMinute = timeToMinutes(startTime);
  const rawEndMinute = timeToMinutes(endTime);

  const startMinute = Math.max(rawStartMinute, dayStartMinute);
  const endMinute = Math.min(rawEndMinute, dayEndMinute);

  const top = ((startMinute - dayStartMinute) / 60) * HOUR_HEIGHT;
  const height = Math.max(((endMinute - startMinute) / 60) * HOUR_HEIGHT, 32);

  return { top, height };
}

export default function WeekPageClient() {
  const params = useSearchParams();

  const week = Number(params.get("week") ?? 0);
  const year = Number(params.get("year") ?? new Date().getFullYear());
  const month = Number(params.get("month") ?? new Date().getMonth());

  const [settings, setSettings] = useState<AppSettings>(() => readSettings());
  const [fixedSeriesList, setFixedSeriesList] = useState<FixedScheduleSeries[]>([]);
  const [variableList, setVariableList] = useState<VariableSchedule[]>([]);
  const [selectedItem, setSelectedItem] = useState<WeekOccurrence | null>(null);

  const [failTargetId, setFailTargetId] = useState<string | null>(null);
  const [selectedFailReason, setSelectedFailReason] = useState<FailReason>("TIME_SHORTAGE");
  const [failReasonText, setFailReasonText] = useState("");

  useEffect(() => {
    const syncData = () => {
      setSettings(readSettings());
      setFixedSeriesList(getFixedScheduleSeries());
      setVariableList(getVariableSchedules());
    };

    syncData();

    window.addEventListener("storage", syncData);
    window.addEventListener("focus", syncData);

    return () => {
      window.removeEventListener("storage", syncData);
      window.removeEventListener("focus", syncData);
    };
  }, []);

  const weekDates = useMemo(() => {
    const firstDate = new Date(year, month, 1);
    const firstDay = firstDate.getDay();
    const start = new Date(year, month, 1 - firstDay + week * 7);

    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      return d;
    });
  }, [week, year, month]);

  const occurrencesByDay = useMemo(() => {
    return weekDates.map((date) => {
      const fixed = getScheduleOccurrencesForDate(date, fixedSeriesList);
      const variable = getVariableOccurrencesForDate(date, variableList);

      return [...fixed, ...variable].sort((a, b) => timeToMinutes(a.start_time) - timeToMinutes(b.start_time));
    });
  }, [weekDates, fixedSeriesList, variableList]);

  const { startHour, endHour, timeFormat } = settings;
  const hours = Array.from({ length: endHour - startHour + 1 }, (_, i) => i + startHour);
  const timetableHeight = hours.length * HOUR_HEIGHT;
  const todayKey = getDateKey(new Date());

  const saveVariables = (next: VariableSchedule[]) => {
    setVariableList(next);
    saveVariableSchedules(next);
  };

  const handleDone = (id: string) => {
    const next = variableList.map((item) =>
      item.id === id
        ? {
            ...item,
            is_done: true,
            status: "done" as const,
            fail_reason: null,
            fail_reason_text: null,
            updated_at: new Date().toISOString(),
          }
        : item
    );

    saveVariables(next);
    setSelectedItem(null);
  };

  const openFailModal = (id: string) => {
    setFailTargetId(id);
    setSelectedFailReason("TIME_SHORTAGE");
    setFailReasonText("");
  };

  const closeFailModal = () => {
    setFailTargetId(null);
    setSelectedFailReason("TIME_SHORTAGE");
    setFailReasonText("");
  };

  const handleConfirmFail = () => {
    if (!failTargetId) return;

    const next = variableList.map((item) =>
      item.id === failTargetId
        ? {
            ...item,
            is_done: false,
            status: "failed" as const,
            fail_reason: selectedFailReason,
            fail_reason_text: failReasonText.trim() || null,
            updated_at: new Date().toISOString(),
          }
        : item
    );

    saveVariables(next);
    closeFailModal();
    setSelectedItem(null);
  };

  const selectedVariable =
    selectedItem?.source_type === "variable" ? variableList.find((item) => item.id === selectedItem.id) : null;

  const selectedStatus = selectedVariable ? getEffectiveVariableStatus(selectedVariable) : null;

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-4 mb-6">
        <div>
          <h1 className="text-3xl font-bold" style={{ color: "var(--app-text)" }}>
            {month + 1}월 {week + 1}주차 시간표
          </h1>

          <p className="mt-1 font-medium" style={{ color: "var(--app-text-muted)" }}>
            {weekDates[0].getMonth() + 1}/{weekDates[0].getDate()} ~ {weekDates[6].getMonth() + 1}/
            {weekDates[6].getDate()}
          </p>
        </div>

        <Link
          href="/schedule"
          className="px-4 py-2 rounded-full font-semibold shadow transition text-center"
          style={{
            background: "var(--primary-button-bg)",
            color: "var(--primary-button-text)",
          }}
        >
          월간으로
        </Link>
      </div>

      <div className="hidden md:block overflow-x-auto">
        <div
          className="rounded-xl border overflow-hidden"
          style={{
            minWidth: "960px",
            background: "var(--app-surface)",
            borderColor: "var(--app-border)",
          }}
        >
          <div className="grid" style={{ gridTemplateColumns: "80px repeat(7, minmax(120px, 1fr))" }}>
            <div
              className="border-b border-r p-3 text-sm font-semibold"
              style={{
                borderColor: "var(--app-border)",
                color: "var(--app-text-muted)",
              }}
            >
              시간
            </div>

            {weekDates.map((date, index) => {
              const isToday = getDateKey(date) === todayKey;

              return (
                <div
                  key={date.toISOString()}
                  className="border-b border-r p-3 text-center"
                  style={{
                    borderColor: "var(--app-border)",
                    background: isToday ? "var(--sky-button-bg)" : "transparent",
                  }}
                >
                  <div className="font-bold" style={{ color: "var(--app-text)" }}>
                    {dayNames[index]}
                  </div>
                  <div className="text-sm" style={{ color: "var(--app-text-muted)" }}>
                    {date.getMonth() + 1}/{date.getDate()}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="grid" style={{ gridTemplateColumns: "80px repeat(7, minmax(120px, 1fr))" }}>
            <div style={{ height: timetableHeight }}>
              {hours.map((hour) => (
                <div
                  key={hour}
                  className="border-r border-b px-3 py-2 text-sm font-medium"
                  style={{
                    height: HOUR_HEIGHT,
                    borderColor: "var(--app-border)",
                    color: "var(--app-text-muted)",
                  }}
                >
                  {formatHour(hour, timeFormat)}
                </div>
              ))}
            </div>

            {weekDates.map((date, dayIndex) => {
              const isToday = getDateKey(date) === todayKey;

              return (
                <div
                  key={date.toISOString()}
                  className="relative border-r"
                  style={{
                    height: timetableHeight,
                    borderColor: "var(--app-border)",
                    background: isToday ? "var(--sky-button-bg)" : "transparent",
                  }}
                >
                  {hours.map((hour) => (
                    <div
                      key={hour}
                      className="border-b"
                      style={{
                        height: HOUR_HEIGHT,
                        borderColor: "var(--app-border)",
                      }}
                    />
                  ))}

                  {occurrencesByDay[dayIndex].map((item) => {
                    const colors = getScheduleColorsByKey(item.color_key);
                    const scheduleStyle = getScheduleStyle(item.start_time, item.end_time, startHour, endHour);
                    const isVariable = item.source_type === "variable";
                    const status = isVariable ? item.status : null;

                    return (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => setSelectedItem(item)}
                        title={`${item.title}\n${formatTimeRange(item.start_time, item.end_time)}\n피로도 ${
                          item.level
                        } · ${getLevelLabel(item.level)}${isVariable ? `\n상태: ${getStatusLabel(status!)}` : ""}`}
                        className="absolute left-2 right-2 rounded-lg border p-2 text-xs shadow-sm overflow-visible text-left group"
                        style={{
                          top: scheduleStyle.top,
                          height: scheduleStyle.height,
                          background: colors.bg,
                          color: colors.text,
                          borderColor: colors.border,
                        }}
                      >
                        <div className="h-full overflow-hidden">
                          <div className="font-bold truncate">{item.title}</div>

                          {scheduleStyle.height >= 44 && (
                            <div className="mt-1 truncate opacity-90">{formatTimeRange(item.start_time, item.end_time)}</div>
                          )}

                          {scheduleStyle.height >= 60 && (
                            <div className="mt-1 truncate opacity-90">
                              피로도 {item.level} · {getLevelLabel(item.level)}
                            </div>
                          )}

                          {isVariable && scheduleStyle.height >= 78 && (
                            <div className="mt-1 truncate opacity-90">상태: {getStatusLabel(status!)}</div>
                          )}
                        </div>

                        <div
                          className="pointer-events-none absolute hidden group-hover:block left-0 top-full mt-2 w-64 rounded-xl border p-3 shadow-xl"
                          style={{
                            zIndex: 80,
                            background: "var(--app-surface)",
                            color: "var(--app-text)",
                            borderColor: "var(--app-border)",
                          }}
                        >
                          <div className="font-bold mb-1">{item.title}</div>
                          <div>{formatTimeRange(item.start_time, item.end_time)}</div>
                          <div>
                            피로도 {item.level} · {getLevelLabel(item.level)}
                          </div>
                          {isVariable && (
                            <>
                              <div>상태: {getStatusLabel(status!)}</div>
                              {item.fail_reason && (
                                <div>
                                  실패 이유: {getFailReasonLabel(item.fail_reason)}
                                  {item.fail_reason_text ? ` / ${item.fail_reason_text}` : ""}
                                </div>
                              )}
                            </>
                          )}
                        </div>
                      </button>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="md:hidden space-y-4">
        <div
          className="rounded-2xl border p-4"
          style={{
            background: "var(--app-surface)",
            borderColor: "var(--app-border)",
          }}
        >
          <p className="text-sm font-semibold" style={{ color: "var(--app-text)" }}>
            모바일 주간 보기
          </p>
          <p className="text-xs mt-1" style={{ color: "var(--app-text-muted)" }}>
            모바일에서는 시간표 표 대신 요일별 카드로 표시합니다.
          </p>
        </div>

        {weekDates.map((date, dayIndex) => {
          const schedules = occurrencesByDay[dayIndex];
          const isToday = getDateKey(date) === todayKey;

          return (
            <section
              key={date.toISOString()}
              className="rounded-2xl border p-4 shadow-sm"
              style={{
                background: isToday ? "var(--sky-button-bg)" : "var(--app-surface)",
                borderColor: isToday ? "var(--sky-button-border)" : "var(--app-border)",
              }}
            >
              <div className="flex justify-between items-center mb-3">
                <h2 className="text-lg font-bold" style={{ color: "var(--app-text)" }}>
                  {dayNames[dayIndex]}요일
                </h2>
                <span className="text-sm font-semibold" style={{ color: "var(--app-text-muted)" }}>
                  {date.getMonth() + 1}/{date.getDate()}
                </span>
              </div>

              {schedules.length === 0 ? (
                <p className="text-sm" style={{ color: "var(--app-text-muted)" }}>
                  등록된 일정이 없습니다.
                </p>
              ) : (
                <div className="space-y-2">
                  {schedules.map((item) => {
                    const colors = getScheduleColorsByKey(item.color_key);
                    const isVariable = item.source_type === "variable";

                    return (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => setSelectedItem(item)}
                        className="w-full rounded-xl border p-3 text-left"
                        style={{
                          background: colors.bg,
                          color: colors.text,
                          borderColor: colors.border,
                        }}
                      >
                        <div className="font-bold">{item.title}</div>
                        <div className="text-sm mt-1">{formatTimeRange(item.start_time, item.end_time)}</div>
                        <div className="text-sm mt-1">
                          피로도 {item.level} · {getLevelLabel(item.level)}
                        </div>
                        {isVariable && <div className="text-sm mt-1">상태: {getStatusLabel(item.status)}</div>}
                      </button>
                    );
                  })}
                </div>
              )}
            </section>
          );
        })}
      </div>

      {selectedItem && (
        <div
          className="fixed inset-0 flex items-center justify-center p-4"
          style={{
            zIndex: 70,
            background: "rgba(0,0,0,0.45)",
          }}
          onClick={() => setSelectedItem(null)}
        >
          <div
            className="w-full max-w-md rounded-2xl border p-5 shadow-xl"
            style={{
              background: "var(--app-surface)",
              borderColor: "var(--app-border)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between gap-3 mb-4">
              <div>
                <h3 className="text-xl font-bold" style={{ color: "var(--app-text)" }}>
                  {selectedItem.title}
                </h3>
                <p className="text-sm mt-1" style={{ color: "var(--app-text-muted)" }}>
                  {selectedItem.source_type === "fixed" ? "고정 일정" : "변동 일정"}
                </p>
              </div>

              <button
                type="button"
                onClick={() => setSelectedItem(null)}
                className="w-9 h-9 rounded-full font-bold"
                style={{ background: "var(--app-surface-muted)", color: "var(--app-text)" }}
              >
                ×
              </button>
            </div>

            <div className="space-y-2 text-sm mb-5" style={{ color: "var(--app-text)" }}>
              <div>시간: {formatTimeRange(selectedItem.start_time, selectedItem.end_time)}</div>
              <div>
                피로도: {selectedItem.level} · {getLevelLabel(selectedItem.level)}
              </div>

              {selectedItem.source_type === "variable" && (
                <>
                  <div>상태: {selectedStatus ? getStatusLabel(selectedStatus) : "미완료"}</div>

                  {selectedVariable?.fail_reason && (
                    <div>
                      실패 이유: {getFailReasonLabel(selectedVariable.fail_reason)}
                      {selectedVariable.fail_reason_text ? ` / ${selectedVariable.fail_reason_text}` : ""}
                    </div>
                  )}
                </>
              )}
            </div>

            {selectedItem.source_type === "variable" && (
              <div className="grid grid-cols-2 gap-2 mb-3">
                <button
                  type="button"
                  onClick={() => handleDone(selectedItem.id)}
                  className="rounded-xl py-3 font-bold"
                  style={{ background: "var(--card-green-bg)", color: "var(--card-green-text)" }}
                >
                  완료
                </button>

                <button
                  type="button"
                  onClick={() => openFailModal(selectedItem.id)}
                  className="rounded-xl py-3 font-bold"
                  style={{ background: "var(--card-yellow-bg)", color: "var(--card-yellow-text)" }}
                >
                  실패
                </button>
              </div>
            )}

            <button
              type="button"
              onClick={() => setSelectedItem(null)}
              className="w-full rounded-xl py-3 font-bold"
              style={{ background: "var(--app-surface-muted)", color: "var(--app-text)" }}
            >
              닫기
            </button>
          </div>
        </div>
      )}

      {failTargetId && (
        <div
          className="fixed inset-0 flex items-center justify-center p-4"
          style={{
            zIndex: 90,
            background: "rgba(0,0,0,0.45)",
          }}
          onClick={closeFailModal}
        >
          <div
            className="w-full max-w-md rounded-2xl border p-5 shadow-xl"
            style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-xl font-bold mb-2" style={{ color: "var(--app-text)" }}>
              실패 이유 선택
            </h3>

            <p className="text-sm mb-4" style={{ color: "var(--app-text-muted)" }}>
              실패 이유는 이후 피로도 조정과 일정 재배치에 활용할 수 있습니다.
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
              className="week-textarea"
            />

            <div className="flex gap-2 mt-4">
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
        .week-textarea {
          width: 100%;
          min-height: 96px;
          resize: none;
          border-radius: 0.75rem;
          border: 1px solid var(--app-border);
          background: var(--app-bg);
          color: var(--app-text);
          padding: 0.75rem;
          outline: none;
        }
      `}</style>
    </div>
  );
}