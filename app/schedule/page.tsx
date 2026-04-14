"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

type CalendarCell = {
  date: number;
  isCurrentMonth: boolean;
};

export default function CalendarPage() {
  const router = useRouter();
  const [currentDate, setCurrentDate] = useState(new Date());

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  const calendarCells = useMemo(() => {
    const firstDay = new Date(year, month, 1).getDay();
    const lastDate = new Date(year, month + 1, 0).getDate();
    const prevLastDate = new Date(year, month, 0).getDate();

    const cells: CalendarCell[] = [];

    for (let i = firstDay - 1; i >= 0; i--) {
      cells.push({
        date: prevLastDate - i,
        isCurrentMonth: false,
      });
    }

    for (let i = 1; i <= lastDate; i++) {
      cells.push({
        date: i,
        isCurrentMonth: true,
      });
    }

    const remaining = (7 - (cells.length % 7)) % 7;

    for (let i = 1; i <= remaining; i++) {
      cells.push({
        date: i,
        isCurrentMonth: false,
      });
    }

    return cells;
  }, [year, month]);

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
              <div className="w-2 h-2 rounded-full bg-green-400"></div>
              <div className="w-2 h-2 rounded-full bg-yellow-400"></div>
              <div className="w-2 h-2 rounded-full bg-red-400"></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}