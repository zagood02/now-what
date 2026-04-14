"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AppSettings, readSettings } from "@/lib/settings";

const dayNames = ["일", "월", "화", "수", "목", "금", "토"];

type FixedSchedule = {
  id: string;
  user_id: string;
  title: string;
  freq_type: "WEEKLY" | "BIWEEKLY" | "MONTHLY";
  by_day: "MON" | "TUE" | "WED" | "THU" | "FRI" | "SAT" | "SUN" | null;
  by_month_day: number | null;
  start_time: string;
  end_time: string;
};

type VariableSchedule = {
  id: string;
  user_id: string;
  title: string;
  estimated_time: number;
  is_done: boolean;
  level: number;
  deadline: string;
};

const fixedSchedules: FixedSchedule[] = [
  {
    id: "1",
    user_id: "test_user",
    title: "수업",
    freq_type: "WEEKLY",
    by_day: "MON",
    by_month_day: null,
    start_time: "10:00:00",
    end_time: "12:00:00",
  },
  {
    id: "2",
    user_id: "test_user",
    title: "운동",
    freq_type: "WEEKLY",
    by_day: "WED",
    by_month_day: null,
    start_time: "18:00:00",
    end_time: "20:00:00",
  },
];

const variableSchedules: VariableSchedule[] = [
  {
    id: "v1",
    user_id: "test_user",
    title: "네트워크 과제",
    estimated_time: 120,
    is_done: false,
    level: 7,
    deadline: "2026-04-07 15:30:00+09",
  },
];

const dayMap: Record<string, number> = {
  SUN: 0,
  MON: 1,
  TUE: 2,
  WED: 3,
  THU: 4,
  FRI: 5,
  SAT: 6,
};

function timeToNumber(time: string) {
  const [h, m] = time.split(":").map(Number);
  return h + m / 60;
}

function formatHour(hour: number, format: AppSettings["timeFormat"]) {
  if (format === "24h") return `${String(hour).padStart(2, "0")}:00`;

  const h = hour % 12 === 0 ? 12 : hour % 12;

  if (format === "ampm") {
    return `${h} ${hour < 12 ? "AM" : "PM"}`;
  }

  return `${hour < 12 ? "오전" : "오후"} ${h}시`;
}

function getScheduleColors(title: string) {
  if (title.includes("수업")) {
    return {
      bg: "var(--card-blue-bg)",
      text: "var(--card-blue-text)",
    };
  }

  if (title.includes("운동")) {
    return {
      bg: "var(--card-green-bg)",
      text: "var(--card-green-text)",
    };
  }

  return {
    bg: "var(--card-red-bg)",
    text: "var(--card-red-text)",
  };
}

export default function WeekPage() {
  const params = useSearchParams();

  const week = Number(params.get("week") ?? 0);
  const year = Number(params.get("year") ?? new Date().getFullYear());
  const month = Number(params.get("month") ?? new Date().getMonth());

  const [settings] = useState<AppSettings>(() => readSettings());

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
                  className="h-20 px-2 flex items-start text-sm font-semibold border-b"
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
                  ></div>
                ))}

                {fixedSchedules
                  .filter((schedule) => {
                    if (!schedule.by_day) return false;
                    return dayMap[schedule.by_day] === dayIndex;
                  })
                  .map((schedule) => {
                    const top =
                      (timeToNumber(schedule.start_time) - startHour) * 80;
                    const height =
                      (timeToNumber(schedule.end_time) -
                        timeToNumber(schedule.start_time)) *
                      80;

                    const colors = getScheduleColors(schedule.title);

                    return (
                      <div
                        key={schedule.id}
                        className="absolute left-1 right-1 p-2 rounded shadow"
                        style={{
                          top,
                          height,
                          background: colors.bg,
                          color: colors.text,
                        }}
                      >
                        <div className="font-semibold">{schedule.title}</div>
                        <div className="text-xs mt-1 opacity-80">
                          {schedule.start_time.slice(0, 5)} ~{" "}
                          {schedule.end_time.slice(0, 5)}
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