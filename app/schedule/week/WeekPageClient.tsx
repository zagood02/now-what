"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AppSettings, readSettings } from "@/lib/settings";
import {
  type FixedScheduleSeries,
  formatTimeRange,
  getFixedScheduleSeries,
  getScheduleColorsByKey,
  getScheduleOccurrencesForDate,
  timeToNumber,
} from "@/lib/mockSchedules";

const dayNames = ["일", "월", "화", "수", "목", "금", "토"];

function formatHour(hour: number, format: AppSettings["timeFormat"]) {
  if (format === "24h") return `${String(hour).padStart(2, "0")}:00`;

  const h = hour % 12 === 0 ? 12 : hour % 12;

  if (format === "ampm") {
    return `${h} ${hour < 12 ? "AM" : "PM"}`;
  }

  return `${hour < 12 ? "오전" : "오후"} ${h}시`;
}

export default function WeekPageClient() {
  const params = useSearchParams();

  const week = Number(params.get("week") ?? 0);
  const year = Number(params.get("year") ?? new Date().getFullYear());
  const month = Number(params.get("month") ?? new Date().getMonth());

  const [settings] = useState<AppSettings>(() => readSettings());
  const [fixedSeriesList, setFixedSeriesList] = useState<FixedScheduleSeries[]>([]);

  useEffect(() => {
    setFixedSeriesList(getFixedScheduleSeries());

    const handleStorage = () => {
      setFixedSeriesList(getFixedScheduleSeries());
    };

    window.addEventListener("storage", handleStorage);
    window.addEventListener("focus", handleStorage);

    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener("focus", handleStorage);
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
    return weekDates.map((date) =>
      getScheduleOccurrencesForDate(date, fixedSeriesList).sort((a, b) => {
        return timeToNumber(a.start_time) - timeToNumber(b.start_time);
      })
    );
  }, [weekDates, fixedSeriesList]);

  const { startHour, endHour, timeFormat } = settings;
  const hours = Array.from(
    { length: endHour - startHour + 1 },
    (_, i) => i + startHour
  );

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