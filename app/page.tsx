"use client";

import { useEffect, useMemo, useState } from "react";
import {
  formatDeadline,
  getDeadlineDiffText,
  getEffectiveVariableStatus,
  getFailReasonLabel,
  getFixedScheduleSeries,
  getLevelLabel,
  getScheduleColorsByKey,
  getScheduleOccurrencesForDate,
  getStatusLabel,
  getVariableSchedules,
  type FixedScheduleSeries,
  type VariableSchedule,
} from "@/lib/mockSchedules";

export default function DashboardPage() {
  const [fixedSeriesList, setFixedSeriesList] = useState<FixedScheduleSeries[]>([]);
  const [variableList, setVariableList] = useState<VariableSchedule[]>([]);

  useEffect(() => {
    const syncData = () => {
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

  const todaySchedules = useMemo(() => {
    const today = new Date();
    return getScheduleOccurrencesForDate(today, fixedSeriesList);
  }, [fixedSeriesList]);

  const pendingTasks = useMemo(() => {
    return [...variableList]
      .filter((task) => getEffectiveVariableStatus(task) === "pending")
      .sort((a, b) => new Date(a.deadline).getTime() - new Date(b.deadline).getTime())
      .slice(0, 5);
  }, [variableList]);

  const failedTasks = useMemo(() => {
    return [...variableList]
      .filter((task) => getEffectiveVariableStatus(task) === "failed")
      .sort((a, b) => new Date(b.updated_at ?? b.deadline).getTime() - new Date(a.updated_at ?? a.deadline).getTime())
      .slice(0, 3);
  }, [variableList]);

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2" style={{ color: "var(--app-text)" }}>
        대시보드
      </h1>

      <p className="mb-6" style={{ color: "var(--app-text-muted)" }}>
        오늘 일정과 처리해야 할 변동 일정을 한눈에 확인하세요.
      </p>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section
          className="rounded-2xl border p-5 shadow-sm"
          style={{
            background: "var(--app-surface)",
            borderColor: "var(--app-border)",
          }}
        >
          <h2 className="text-xl font-bold mb-4" style={{ color: "var(--app-text)" }}>
            오늘의 일정
          </h2>

          {todaySchedules.length === 0 ? (
            <Empty>오늘 일정이 없습니다.</Empty>
          ) : (
            <div className="space-y-3">
              {todaySchedules.map((item) => {
                const colors = getScheduleColorsByKey(item.color_key);

                return (
                  <div
                    key={item.id}
                    className="rounded-xl border p-3"
                    style={{
                      background: colors.bg,
                      color: colors.text,
                      borderColor: colors.border,
                    }}
                  >
                    <div className="font-bold">{item.title}</div>

                    <div className="text-sm mt-1">
                      {item.start_time.slice(0, 5)} ~ {item.end_time.slice(0, 5)}
                    </div>

                    <div className="text-sm mt-1">
                      피로도 {item.level} · {getLevelLabel(item.level)}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        <section
          className="rounded-2xl border p-5 shadow-sm"
          style={{
            background: "var(--app-surface)",
            borderColor: "var(--app-border)",
          }}
        >
          <h2 className="text-xl font-bold mb-4" style={{ color: "var(--app-text)" }}>
            해야 할 변동 일정
          </h2>

          {pendingTasks.length === 0 ? (
            <Empty>현재 미완료 변동 일정이 없습니다.</Empty>
          ) : (
            <div className="space-y-3">
              {pendingTasks.map((task) => {
                const colors = getScheduleColorsByKey(task.color_key);
                const status = getEffectiveVariableStatus(task);

                return (
                  <div
                    key={task.id}
                    className="rounded-xl border p-3"
                    style={{
                      background: colors.bg,
                      color: colors.text,
                      borderColor: colors.border,
                    }}
                  >
                    <div className="flex items-center gap-2 flex-wrap">
                      <div className="font-bold">{task.title}</div>
                      <span
                        className="text-xs px-2 py-1 rounded-full font-bold"
                        style={{
                          background: "var(--app-surface)",
                          color: colors.text,
                        }}
                      >
                        {getStatusLabel(status)}
                      </span>
                    </div>

                    <div className="text-sm mt-1">
                      마감: {formatDeadline(task.deadline)} ({getDeadlineDiffText(task.deadline)})
                    </div>

                    <div className="text-sm mt-1">
                      예상 {task.estimated_time}분 · 피로도 {task.level} ({getLevelLabel(task.level)})
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      </div>

      <section
        className="rounded-2xl border p-5 shadow-sm mt-6"
        style={{
          background: "var(--app-surface)",
          borderColor: "var(--app-border)",
        }}
      >
        <h2 className="text-xl font-bold mb-4" style={{ color: "var(--app-text)" }}>
          실패 기록
        </h2>

        {failedTasks.length === 0 ? (
          <Empty>최근 실패한 일정이 없습니다.</Empty>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
            {failedTasks.map((task) => {
              const colors = getScheduleColorsByKey(task.color_key);
              const failLabel = getFailReasonLabel(task.fail_reason);

              return (
                <div
                  key={task.id}
                  className="rounded-xl border p-3"
                  style={{
                    background: colors.bg,
                    color: colors.text,
                    borderColor: colors.border,
                  }}
                >
                  <div className="font-bold">{task.title}</div>

                  <div className="text-sm mt-1">
                    마감: {formatDeadline(task.deadline)}
                  </div>

                  <div className="text-sm mt-1">
                    실패 이유: {failLabel ?? "마감 초과"}
                    {task.fail_reason_text ? ` / ${task.fail_reason_text}` : ""}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <section
        className="rounded-2xl border p-5 shadow-sm mt-6"
        style={{
          background: "var(--app-surface)",
          borderColor: "var(--app-border)",
        }}
      >
        <h2 className="text-xl font-bold mb-3" style={{ color: "var(--app-text)" }}>
          AI 추천
        </h2>

        <p style={{ color: "var(--app-text-muted)" }}>
          완료·실패 기록과 피로도를 기반으로 한 추천 기능은 추후 추가 예정입니다.
        </p>
      </section>
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
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