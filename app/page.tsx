"use client";

import { useEffect, useMemo, useState } from "react";
import { useAuth } from "@/app/contexts/AuthContext";
import { calendarAPI, handleApiError, type CalendarEvent } from "@/lib/api";

export default function DashboardPage() {
  const { user, isLoading } = useAuth();
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [isLoadingEvents, setIsLoadingEvents] = useState(false);
  const [error, setError] = useState("");

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
        setEvents(response.data.events);
      } catch (error) {
        setError(handleApiError(error));
      } finally {
        setIsLoadingEvents(false);
      }
    };

    loadCalendar();
  }, [user]);

  const summary = useMemo(() => {
    const countBySource = events.reduce<Record<string, number>>((acc, event) => {
      acc[event.source_type] = (acc[event.source_type] ?? 0) + 1;
      return acc;
    }, {});

    return {
      total: events.length,
      countBySource,
    };
  }, [events]);

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
          로그인 후 실시간 캘린더 데이터를 확인할 수 있습니다.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2" style={{ color: "var(--app-text)" }}>
        대시보드
      </h1>

      <p className="mb-6" style={{ color: "var(--app-text-muted)" }}>
        다음 7일간의 캘린더 이벤트를 백엔드에서 불러옵니다.
      </p>

      <section className="rounded-2xl border p-5 shadow-sm mb-6" style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="text-sm text-slate-500" style={{ color: "var(--app-text-muted)" }}>
              이벤트 개수
            </div>
            <div className="text-3xl font-bold" style={{ color: "var(--app-text)" }}>
              {summary.total}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {Object.entries(summary.countBySource).map(([source, count]) => (
              <div key={source} className="rounded-xl border p-4" style={{ background: "var(--app-bg)", borderColor: "var(--app-border)" }}>
                <div className="text-xs uppercase tracking-wide" style={{ color: "var(--app-text-muted)" }}>
                  {source}
                </div>
                <div className="text-xl font-bold mt-2" style={{ color: "var(--app-text)" }}>
                  {count}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="rounded-2xl border p-5 shadow-sm" style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}>
        <h2 className="text-xl font-bold mb-4" style={{ color: "var(--app-text)" }}>
          캘린더 이벤트
        </h2>

        {isLoadingEvents ? (
          <div style={{ color: "var(--app-text-muted)" }}>데이터를 불러오는 중입니다...</div>
        ) : error ? (
          <div className="rounded-xl border p-4" style={{ background: "var(--app-bg)", borderColor: "var(--app-border)", color: "var(--app-text)" }}>
            {error}
          </div>
        ) : events.length === 0 ? (
          <div className="rounded-xl border p-4" style={{ background: "var(--app-bg)", borderColor: "var(--app-border)", color: "var(--app-text-muted)" }}>
            다음 7일간 등록된 일정이 없습니다.
          </div>
        ) : (
          <div className="space-y-4">
            {events.map((event) => (
              <div key={`${event.source_type}-${event.source_id}-${event.id}`} className="rounded-xl border p-4" style={{ background: "var(--app-bg)", borderColor: "var(--app-border)" }}>
                <div className="font-bold" style={{ color: "var(--app-text)" }}>
                  {event.title}
                </div>
                <div className="text-sm mt-2" style={{ color: "var(--app-text-muted)" }}>
                  {formatDateTime(event.start_at)} ~ {formatDateTime(event.end_at)}
                </div>
                <div className="text-sm mt-1" style={{ color: "var(--app-text-muted)" }}>
                  {event.source_type} · 상태: {event.status}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
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
