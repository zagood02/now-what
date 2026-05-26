"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/app/contexts/AuthContext";
import { AppSettings, readSettings } from "@/lib/settings";
import { calendarAPI, type CalendarEvent } from "@/lib/api";

const dayNames = ["일", "월", "화", "수", "목", "금", "토"];

function formatHour(hour: number, format: AppSettings["timeFormat"]) {
  if (format === "24h") return `${String(hour).padStart(2, "0")}:00`;

  const h = hour % 12 === 0 ? 12 : hour % 12;

  if (format === "ampm") {
    return `${h} ${hour < 12 ? "AM" : "PM"}`;
  }

  return `${hour < 12 ? "오전" : "오후"} ${h}시`;
}

function timeToNumber(timeString: string): number {
  const [hours, minutes] = timeString.split(':').map(Number);
  return hours + minutes / 60;
}

function formatTimeRange(startTime: string, endTime: string): string {
  const start = startTime.slice(0, 5); // HH:MM
  const end = endTime.slice(0, 5); // HH:MM
  return `${start} - ${end}`;
}

function getScheduleColorsByKey(colorKey: number) {
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

export default function WeekPageClient() {
  const params = useSearchParams();
  const { user, isLoading: isAuthLoading } = useAuth();

  const week = Number(params.get("week") ?? 0);
  const year = Number(params.get("year") ?? 2026);  // 기본값을 2026으로
  const month = Number(params.get("month") ?? 4);   // 기본값을 4로 (5월)

  const [settings] = useState<AppSettings>(() => readSettings());
  const [calendarEvents, setCalendarEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const weekDates = useMemo(() => {
    // month 파라미터는 0-based (0=1월, 4=5월)
    const firstDate = new Date(year, month, 1);  // month는 이미 0-based
    const firstDay = firstDate.getDay();
    const start = new Date(year, month, 1 - firstDay + week * 7);

    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      return d;
    });
  }, [week, year, month]);

  useEffect(() => {
    const fetchCalendarData = async () => {
      if (isAuthLoading) {
        return;
      }

      if (!user) {
        setCalendarEvents([]);
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);

        const startDate = weekDates[0];
        const endDate = new Date(weekDates[6]);
        endDate.setHours(23, 59, 59, 999);

        const response = await calendarAPI.get({
          start: startDate.toISOString(),
          end: endDate.toISOString(),
        });

        setCalendarEvents(response.data.events ?? []);
      } catch (err) {
        console.error("Failed to fetch calendar data:", err);
        setCalendarEvents([]);
        setError("시간표 데이터를 불러오는데 실패했습니다.");
      } finally {
        setLoading(false);
      }
    };

    if (weekDates.length > 0) {
      fetchCalendarData();
    }
  }, [isAuthLoading, user, weekDates]);

  const { startHour, endHour, timeFormat } = settings;
  const hours = Array.from(
    { length: endHour - startHour + 1 },
    (_, i) => i + startHour
  );

  const occurrencesByDay = useMemo(() => {
    return weekDates.map((date) => {
      const dayStart = new Date(date);
      dayStart.setHours(0, 0, 0, 0);
      const dayEnd = new Date(date);
      dayEnd.setHours(23, 59, 59, 999);

      return calendarEvents
        .filter((event) => {
          const eventStart = new Date(event.start_at);
          return eventStart >= dayStart && eventStart <= dayEnd;
        })
        .sort((a, b) => {
          const aStart = new Date(a.start_at);
          const bStart = new Date(b.start_at);
          return aStart.getTime() - bStart.getTime();
        })
        .map((event) => ({
          id: event.id,
          title: event.title,
          start_time: new Date(event.start_at).toTimeString().slice(0, 8),
          end_time: new Date(event.end_at).toTimeString().slice(0, 8),
          color_key: event.source_type === "fixed_schedule" ? 0 :
                    event.source_type === "allocated_task" ? 1 :
                    event.source_type === "ai_plan_item" ? 2 : 3,
          source_type: event.source_type as "fixed",
        }));
    });
  }, [weekDates, calendarEvents]);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-lg" style={{ color: "var(--app-text-muted)" }}>
          시간표를 불러오는 중...
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-lg" style={{ color: "var(--app-text-muted)" }}>
          로그인 후 시간표를 확인할 수 있습니다.
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-lg text-red-500">{error}</div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex justify-between items-start mb-6 gap-4">
        <div>
          <h1
            className="text-3xl font-bold"
            style={{ color: "var(--app-text)" }}
          >
            {month + 1}월 {week + 1}주차 시간표
          </h1>

          <p
            className="mt-1 font-medium"
            style={{ color: "var(--app-text-muted)" }}
          >
            {weekDates[0].getMonth() + 1}/{weekDates[0].getDate()} ~{" "}
            {weekDates[6].getMonth() + 1}/{weekDates[6].getDate()}
          </p>
        </div>

        <Link
          href="/schedule"
          className="px-4 py-2 rounded-full font-semibold shadow transition"
          style={{
            background: "var(--primary-button-bg)",
            color: "var(--primary-button-text)",
          }}
        >
          월간으로
        </Link>
      </div>

      <div className="overflow-x-auto">
        <div
          className="min-w-full rounded-xl border"
          style={{
            background: "var(--app-surface)",
            borderColor: "var(--app-border)",
          }}
        >
          <div
            className="grid grid-cols-[80px_repeat(7,1fr)] border-b"
            style={{
              background: "var(--app-surface-muted)",
              borderColor: "var(--app-border)",
            }}
          >
            <div></div>

            {weekDates.map((d, i) => (
              <div key={i} className="text-center p-3">
                <div
                  className="text-lg font-bold"
                  style={{ color: "var(--app-text)" }}
                >
                  {dayNames[i]}
                </div>
                <div
                  className="text-sm mt-1"
                  style={{ color: "var(--app-text-muted)" }}
                >
                  {d.getMonth() + 1}/{d.getDate()}
                </div>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-[80px_repeat(7,1fr)]">
            <div>
              {hours.map((h) => (
                <div
                  key={h}
                  className="h-20 px-2 pt-1 text-sm font-semibold border-b"
                  style={{
                    color: "var(--app-text-muted)",
                    borderColor: "var(--app-border)",
                  }}
                >
                  {formatHour(h, timeFormat)}
                </div>
              ))}
            </div>

            {weekDates.map((_, dayIndex) => (
              <div
                key={dayIndex}
                className="relative border-l"
                style={{ borderColor: "var(--app-border)" }}
              >
                {hours.map((h) => (
                  <div
                    key={h}
                    className="h-20 border-b"
                    style={{ borderColor: "var(--app-border)" }}
                  />
                ))}

                {occurrencesByDay[dayIndex]?.map((schedule) => {
                  const top =
                    (timeToNumber(schedule.start_time) - startHour) * 80;
                  const height =
                    (timeToNumber(schedule.end_time) -
                      timeToNumber(schedule.start_time)) *
                    80;

                  const colors = getScheduleColorsByKey(schedule.color_key);

                  return (
                    <div
                      key={schedule.id}
                      className="absolute left-1 right-1 p-2 rounded-lg shadow-sm overflow-hidden"
                      style={{
                        top,
                        height,
                        background: colors.bg,
                        color: colors.text,
                      }}
                    >
                      <div className="font-semibold text-sm">{schedule.title}</div>
                      <div className="text-xs mt-1 opacity-80">
                        {formatTimeRange(schedule.start_time, schedule.end_time)}
                      </div>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
