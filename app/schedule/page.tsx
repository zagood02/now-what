"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { calendarAPI, type CalendarEvent } from "@/lib/api";

type CalendarCell = {
  date: number;
  isCurrentMonth: boolean;
  events: CalendarEvent[];
};

export default function CalendarPage() {
  const router = useRouter();
  const [currentDate, setCurrentDate] = useState(() => new Date(2026, 4, 1));  // 2026년 5월로 초기화
  const [calendarEvents, setCalendarEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  useEffect(() => {
    const fetchCalendarData = async () => {
      try {
        setLoading(true);
        const startDate = new Date(year, month, 1);
        const endDate = new Date(year, month + 1, 0);
        endDate.setHours(23, 59, 59, 999);

        const response = await calendarAPI.get({
          user_id: 1, // 테스트 유저 ID
          start: startDate.toISOString(),
          end: endDate.toISOString(),
        });

        setCalendarEvents(response.data.events);
      } catch (error) {
        console.error("Failed to fetch calendar data:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchCalendarData();
  }, [year, month]);

  const calendarCells = useMemo(() => {
    const getEventsForDate = (date: Date) => {
      const dayStart = new Date(date);
      dayStart.setHours(0, 0, 0, 0);
      const dayEnd = new Date(date);
      dayEnd.setHours(23, 59, 59, 999);

      return calendarEvents.filter((event) => {
        const eventStart = new Date(event.start_at);
        const eventEnd = new Date(event.end_at);
        return eventStart >= dayStart && eventStart <= dayEnd;
      });
    };

    const firstDay = new Date(year, month, 1).getDay();
    const lastDate = new Date(year, month + 1, 0).getDate();
    const prevLastDate = new Date(year, month, 0).getDate();

    const cells: CalendarCell[] = [];

    for (let i = firstDay - 1; i >= 0; i--) {
      const cellDate = new Date(year, month - 1, prevLastDate - i);
      cells.push({
        date: prevLastDate - i,
        isCurrentMonth: false,
        events: getEventsForDate(cellDate),
      });
    }

    for (let i = 1; i <= lastDate; i++) {
      const cellDate = new Date(year, month, i);
      cells.push({
        date: i,
        isCurrentMonth: true,
        events: getEventsForDate(cellDate),
      });
    }

    const remaining = (7 - (cells.length % 7)) % 7;

    for (let i = 1; i <= remaining; i++) {
      const cellDate = new Date(year, month + 1, i);
      cells.push({
        date: i,
        isCurrentMonth: false,
        events: getEventsForDate(cellDate),
      });
    }

    return cells;
  }, [year, month, calendarEvents]);

  const handlePrevMonth = () => {
    setCurrentDate(new Date(year, month - 1, 1));
  };

  const handleNextMonth = () => {
    setCurrentDate(new Date(year, month + 1, 1));
  };

  const handleWeekClick = (index: number) => {
    const weekIndex = Math.floor(index / 7);
    router.push(`/schedule/week?week=${weekIndex}&year=${year}&month=${month}`);
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-lg" style={{ color: "var(--app-text-muted)" }}>
          월간 일정을 불러오는 중...
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <button
          onClick={handlePrevMonth}
          className="flex items-center justify-center w-10 h-10 rounded-xl border text-lg font-bold hover:opacity-90"
          style={{
            background: "var(--sky-button-bg)",
            color: "var(--sky-button-text)",
            borderColor: "var(--sky-button-border)",
          }}
        >
          ◀
        </button>

        <h1
          className="text-3xl font-bold"
          style={{ color: "var(--app-text)" }}
        >
          {year}년 {month + 1}월
        </h1>

        <button
          onClick={handleNextMonth}
          className="flex items-center justify-center w-10 h-10 rounded-xl border text-lg font-bold hover:opacity-90"
          style={{
            background: "var(--sky-button-bg)",
            color: "var(--sky-button-text)",
            borderColor: "var(--sky-button-border)",
          }}
        >
          ▶
        </button>
      </div>

      <div
        className="grid grid-cols-7 text-center font-bold mb-2"
        style={{ color: "var(--app-text-muted)" }}
      >
        {["일", "월", "화", "수", "목", "금", "토"].map((day) => (
          <div key={day} className="py-2">
            {day}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-2">
        {calendarCells.map((cell, index) => (
          <div
            key={index}
            onClick={() => handleWeekClick(index)}
            className="h-24 rounded-xl border p-3 transition cursor-pointer hover:opacity-90"
            style={{
              background: cell.isCurrentMonth
                ? "var(--app-surface)"
                : "var(--app-surface-soft)",
              borderColor: "var(--app-border)",
            }}
          >
            <div
              className="text-sm font-semibold"
              style={{
                color: cell.isCurrentMonth
                  ? "var(--app-text)"
                  : "var(--app-text-muted)",
                opacity: cell.isCurrentMonth ? 1 : 0.6,
              }}
            >
              {cell.date}
            </div>

            <div className="mt-3 flex gap-1">
              {cell.events.slice(0, 3).map((event, eventIndex) => {
                let dotColor = "bg-gray-400";
                if (event.source_type === "fixed_schedule") {
                  dotColor = "bg-blue-400";
                } else if (event.source_type === "allocated_task") {
                  dotColor = "bg-green-400";
                } else if (event.source_type === "ai_plan_item") {
                  dotColor = "bg-yellow-400";
                }
                return (
                  <div key={eventIndex} className={`w-2 h-2 rounded-full ${dotColor}`}></div>
                );
              })}
              {cell.events.length > 3 && (
                <div className="text-xs text-gray-500">+{cell.events.length - 3}</div>
              )}
            </div>

            {cell.events.length > 0 && (
              <div className="mt-1 space-y-1">
                {cell.events.slice(0, 2).map((event, eventIndex) => (
                  <div
                    key={eventIndex}
                    className="text-xs truncate rounded px-1 py-0.5"
                    style={{
                      background: event.source_type === "fixed_schedule"
                        ? "var(--card-blue-bg)"
                        : event.source_type === "allocated_task"
                        ? "var(--card-green-bg)"
                        : "var(--card-yellow-bg)",
                      color: event.source_type === "fixed_schedule"
                        ? "var(--card-blue-text)"
                        : event.source_type === "allocated_task"
                        ? "var(--card-green-text)"
                        : "var(--card-yellow-text)",
                    }}
                    title={event.title}
                  >
                    {event.title}
                  </div>
                ))}
                {cell.events.length > 2 && (
                  <div className="text-xs text-gray-500">
                    +{cell.events.length - 2}개 더보기
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}