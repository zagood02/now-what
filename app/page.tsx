"use client";

import { useEffect, useMemo, useState } from "react";
import { useAuth } from "@/app/contexts/AuthContext";
import { calendarAPI, handleApiError, plannerAPI, flexibleTaskAPI, variableScheduleAPI, type CalendarEvent } from "@/lib/api";
import HelpButton from "@/components/HelpButton";

export default function DashboardPage() {
  const { user, isLoading } = useAuth();
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [isLoadingEvents, setIsLoadingEvents] = useState(false);
  const [error, setError] = useState("");
  const [completingId, setCompletingId] = useState<string | null>(null);

  useEffect(() => {
    if (!user) {
      setEvents([]);
      setError("");
      return;
    }

    const loadCalendar = async () => {
      setIsLoadingEvents(true);
      setError("");

      const start = new Date();
      const end = new Date(start);
      end.setDate(end.getDate() + 7);

      try {
        const response = await calendarAPI.get({
          start: start.toISOString(),
          end: end.toISOString(),
        });
        setEvents(response.data.events ?? []);
      } catch (error) {
        setError(handleApiError(error));
      } finally {
        setIsLoadingEvents(false);
      }
    };

    loadCalendar();
  }, [user]);

  const now = useMemo(() => new Date(), []);
  const todayStart = useMemo(() => {
    const date = new Date();
    date.setHours(0, 0, 0, 0);
    return date;
  }, []);
  const todayEnd = useMemo(() => {
    const date = new Date();
    date.setHours(23, 59, 59, 999);
    return date;
  }, []);
  const tomorrowStart = useMemo(() => {
    const date = new Date();
    date.setDate(date.getDate() + 1);
    date.setHours(0, 0, 0, 0);
    return date;
  }, []);
  const tomorrowEnd = useMemo(() => {
    const date = new Date();
    date.setDate(date.getDate() + 1);
    date.setHours(23, 59, 59, 999);
    return date;
  }, []);
  const soonEnd = useMemo(() => {
    const date = new Date();
    date.setHours(date.getHours() + 48);
    return date;
  }, []);

  const dashboardEvents = useMemo(
    () => events.filter((event) => event.source_type !== "fixed_schedule"),
    [events]
  );

  const overview = useMemo(() => {
    const overdue = dashboardEvents.filter((event) => new Date(event.start_at) < now && event.status !== "completed");
    const today = dashboardEvents.filter((event) => {
      const start = new Date(event.start_at);
      return start >= todayStart && start <= todayEnd && event.status !== "completed";
    });
    const tomorrow = dashboardEvents.filter((event) => {
      const start = new Date(event.start_at);
      return start >= tomorrowStart && start <= tomorrowEnd && event.status !== "completed";
    });
    const soon = dashboardEvents.filter((event) => {
      const start = new Date(event.start_at);
      return start > now && start <= soonEnd && event.status !== "completed";
    });
    const thisWeek = dashboardEvents.filter((event) => new Date(event.start_at) >= now && new Date(event.start_at) <= new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000));

    return {
      overdue: overdue.sort((a, b) => new Date(a.start_at).getTime() - new Date(b.start_at).getTime()),
      today: today.sort((a, b) => new Date(a.start_at).getTime() - new Date(b.start_at).getTime()),
      tomorrow: tomorrow.sort((a, b) => new Date(a.start_at).getTime() - new Date(b.start_at).getTime()),
      soon: soon.sort((a, b) => new Date(a.start_at).getTime() - new Date(b.start_at).getTime()),
      thisWeek: thisWeek.sort((a, b) => new Date(a.start_at).getTime() - new Date(b.start_at).getTime()),
      counts: {
        today: today.length,
        soon: soon.length,
        thisWeek: thisWeek.length,
      },
    };
  }, [dashboardEvents, now, todayStart, todayEnd, tomorrowStart, tomorrowEnd, soonEnd]);

  const highlightedReminders = useMemo(() => {
    if (overview.overdue.length > 0) {
      return overview.overdue.slice(0, 3);
    }
    const todayAndTomorrow = [...overview.today, ...overview.tomorrow].slice(0, 3);
    if (todayAndTomorrow.length > 0) {
      return todayAndTomorrow;
    }
    return overview.soon.slice(0, 3);
  }, [overview.overdue, overview.today, overview.tomorrow, overview.soon]);

  const handleComplete = async (event: CalendarEvent) => {
    const eventKey = `${event.source_type}-${event.source_id}-${event.id}`;
    setCompletingId(eventKey);
    setError("");

    try {
      if (event.source_type === "ai_plan_item") {
        await plannerAPI.completePlanItem(event.source_id);
      } else if (event.source_type === "allocated_task") {
        await flexibleTaskAPI.update(event.source_id, { status: "completed" }as any);
      } else if (event.source_type === "variable_schedule") {
        await variableScheduleAPI.update(event.source_id, { status: "completed" }as any);
      }

      setEvents((prev) => prev.filter((e) => !(e.id === event.id && e.source_type === event.source_type)));
    } catch (err) {
      setError(handleApiError(err));
    } finally {
      setCompletingId(null);
    }
  };

  if (isLoading) {
    return <div>로딩 중...</div>;
  }

  if (!user) {
    return (
      <div>
        <h1 className="text-3xl font-bold mb-2" style={{ color: "var(--app-text)" }}>
          대시보드
        </h1>
        <p style={{ color: "var(--app-text-muted)" }}>
          로그인 후 오늘의 리마인더를 확인할 수 있습니다.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold" style={{ color: "var(--app-text)" }}>
            오늘의 리마인드
          </h1>
          <p className="mt-2 text-sm" style={{ color: "var(--app-text-muted)" }}>
            잊지 말아야 할 일정과 중요한 할 일을 한눈에 확인하세요.
          </p>
        </div>

        {/* <div className="flex items-start gap-3">
          <HelpButton title="대시보드 도움말">
            <p>오늘의 리마인더와 곧 다가올 일정들을 확인하고 완료 처리할 수 있습니다.</p>
          </HelpButton>         // 도움말 버튼 없어도 될듯
        </div> */}
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="rounded-2xl border p-4 shadow-sm" style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}>
          <div className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--app-text-muted)" }}>
            오늘
          </div>
          <div className="mt-3 text-3xl font-bold" style={{ color: "var(--app-text)" }}>
            {overview.counts.today}
          </div>
          <div className="mt-1 text-sm" style={{ color: "var(--app-text-muted)" }}>
            완료하지 않은 일정
          </div>
        </div>

        <div className="rounded-2xl border p-4 shadow-sm" style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}>
          <div className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--app-text-muted)" }}>
            48시간
          </div>
          <div className="mt-3 text-3xl font-bold" style={{ color: "var(--app-text)" }}>
            {overview.counts.soon}
          </div>
          <div className="mt-1 text-sm" style={{ color: "var(--app-text-muted)" }}>
            곧 시작할 일정
          </div>
        </div>

        <div className="rounded-2xl border p-4 shadow-sm" style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}>
          <div className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--app-text-muted)" }}>
            이번 주
          </div>
          <div className="mt-3 text-3xl font-bold" style={{ color: "var(--app-text)" }}>
            {overview.counts.thisWeek}
          </div>
          <div className="mt-1 text-sm" style={{ color: "var(--app-text-muted)" }}>
            다음 7일 일정
          </div>
        </div>
      </div>

      <section className="rounded-2xl border p-5 shadow-sm" style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}>
        <div className="flex items-center justify-between gap-4 mb-4">
          <div>
            <h2 className="text-xl font-bold" style={{ color: "var(--app-text)" }}>
              지금 챙겨야 할 일정
            </h2>
            <p className="text-sm mt-1" style={{ color: "var(--app-text-muted)" }}>
              우선 순위가 높은 일정부터 먼저 보여드립니다.
            </p>
          </div>
          <div className="text-sm font-semibold" style={{ color: "var(--app-text-muted)" }}>
            {overview.overdue.length > 0 ? "지금 바로 처리해야 함" : "곧 시작할 일정"}
          </div>
        </div>

        {isLoadingEvents ? (
          <div style={{ color: "var(--app-text-muted)" }}>데이터를 불러오는 중입니다...</div>
        ) : error ? (
          <div className="rounded-xl border p-4" style={{ background: "var(--app-bg)", borderColor: "var(--app-border)", color: "var(--app-text)" }}>
            {error}
          </div>
        ) : highlightedReminders.length === 0 ? (
          <div className="rounded-xl border p-4" style={{ background: "var(--app-bg)", borderColor: "var(--app-border)", color: "var(--app-text-muted)" }}>
            현재 확인해야 할 일정이 없습니다. 다음 일정이 생기면 여기에 표시됩니다.
          </div>
        ) : (
          <div className="space-y-3">
            {highlightedReminders.map((event) => {
              const isOverdue = new Date(event.start_at) < now && event.status !== "completed";
              const isToday = new Date(event.start_at) >= todayStart && new Date(event.start_at) <= todayEnd;
              const isTomorrow = new Date(event.start_at) >= tomorrowStart && new Date(event.start_at) <= tomorrowEnd;
              const isSoon = new Date(event.start_at) > now && new Date(event.start_at) <= soonEnd;

              let backgroundColor = "var(--app-bg)";
              let borderColor = "var(--app-border)";
              let accentColor = "transparent";

              if (isOverdue) {
                backgroundColor = "#fef2f2";
                borderColor = "#fecaca";
                accentColor = "#dc2626";
              } else if (isToday) {
                backgroundColor = "#fffbeb";
                borderColor = "#fde68a";
                accentColor = "#d97706";
              } else if (isTomorrow) {
                backgroundColor = "#f0fdf4";
                borderColor = "#bbf7d0";
                accentColor = "#16a34a";
              } else if (isSoon) {
                backgroundColor = "#eff6ff";
                borderColor = "#bfdbfe";
                accentColor = "#2563eb";
              }

              return (
                <div key={`${event.source_type}-${event.source_id}-${event.id}`} className="rounded-2xl border p-4 transition hover:shadow-md" style={{ background: backgroundColor, borderColor: borderColor, borderLeftWidth: "4px", borderLeftColor: accentColor }}>
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <div className="text-base font-bold" style={{ color: "var(--app-text)" }}>
                        {event.title}
                      </div>
                      <div className="mt-2 text-sm" style={{ color: "var(--app-text-muted)" }}>
                        {formatDateTime(event.start_at)} ~ {formatDateTime(event.end_at)}
                      </div>
                      <div className="mt-1 text-sm" style={{ color: "var(--app-text-muted)" }}>
                        {sourceLabel(event.source_type)} · 상태: {event.status || "대기"}
                      </div>
                    </div>
                    <div className="flex gap-2 flex-wrap items-center">
                      <span className="rounded-full border px-3 py-1 text-xs font-semibold" style={{ borderColor: accentColor, color: accentColor }}>
                        {event.source_type === "ai_plan_item" ? "AI 계획" : event.source_type === "allocated_task" ? "투두" : sourceLabel(event.source_type)}
                      </span>
                      {isOverdue ? (
                        <span className="rounded-full bg-red-100 px-3 py-1 text-xs font-semibold text-red-700">지연</span>
                      ) : isToday ? (
                        <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-700">오늘</span>
                      ) : isTomorrow ? (
                        <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-semibold text-green-700">내일</span>
                      ) : isSoon ? (
                        <span className="rounded-full bg-blue-100 px-3 py-1 text-xs font-semibold text-blue-700">곧</span>
                      ) : null}
                      <button
                        onClick={() => handleComplete(event)}
                        disabled={completingId === `${event.source_type}-${event.source_id}-${event.id}`}
                        className="ml-auto rounded-lg px-4 py-2 font-bold text-sm transition hover:opacity-90 disabled:opacity-60"
                        style={{ background: accentColor, color: "white" }}
                      >
                        {completingId === `${event.source_type}-${event.source_id}-${event.id}` ? "처리중..." : "완료"}
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <section className="rounded-2xl border p-5 shadow-sm" style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}>
        <h2 className="text-xl font-bold mb-4" style={{ color: "var(--app-text)" }}>
          전체 일정 요약
        </h2>
        <div className="grid gap-4 lg:grid-cols-2">
          <SummaryCard title="오늘 일정" subtitle="오늘 완료해야 할 일정" count={overview.counts.today} />
          <SummaryCard title="48시간 일정" subtitle="곧 시작할 일정" count={overview.counts.soon} />
          <SummaryCard title="이번 주 일정" subtitle="다음 7일 내 일정" count={overview.counts.thisWeek} />
          <SummaryCard title="고정 일정 제외" subtitle="대시보드에서 관리하지 않는 일정" count={events.filter((event) => event.source_type === "fixed_schedule").length} />
        </div>
      </section>
    </div>
  );
}

function SummaryCard({ title, subtitle, count }: { title: string; subtitle: string; count: number }) {
  return (
    <div className="rounded-2xl border p-4" style={{ background: "var(--app-bg)", borderColor: "var(--app-border)" }}>
      <div className="text-sm font-semibold uppercase tracking-wide" style={{ color: "var(--app-text-muted)" }}>
        {title}
      </div>
      <div className="mt-4 text-3xl font-bold" style={{ color: "var(--app-text)" }}>
        {count}
      </div>
      <div className="mt-2 text-sm" style={{ color: "var(--app-text-muted)" }}>
        {subtitle}
      </div>
    </div>
  );
}

function sourceLabel(sourceType: string) {
  if (sourceType === "ai_plan_item") return "AI 계획";
  if (sourceType === "allocated_task") return "투두";
  if (sourceType === "fixed_schedule") return "고정 일정";
  if (sourceType === "variable_schedule") return "변동 스케줄";
  return sourceType;
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
