"use client";

import { useState } from "react";
import {
  AppSettings,
  readSettings,
  saveSettings,
} from "@/lib/settings";
import { applyThemeClass } from "@/components/ThemeInitializer";

function ToggleSwitch({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  label: string;
}) {
  return (
    <div className="flex items-center justify-between">
      <span
        className="text-sm font-semibold"
        style={{ color: "var(--app-text)" }}
      >
        {label}
      </span>

      <button
        type="button"
        onClick={() => onChange(!checked)}
        className="relative inline-flex h-7 w-12 items-center rounded-full transition"
        style={{
          background: checked ? "#3b82f6" : "#9ca3af",
        }}
      >
        <span
          className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition ${
            checked ? "translate-x-6" : "translate-x-1"
          }`}
        />
      </button>
    </div>
  );
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings>(() => readSettings());

  const updateSettings = <K extends keyof AppSettings>(
    key: K,
    value: AppSettings[K]
  ) => {
    const next = { ...settings, [key]: value };
    setSettings(next);
    saveSettings(next);
    applyThemeClass();
    window.dispatchEvent(new Event("theme-refresh"));
  };

  return (
    <div>
      <h1
        className="text-3xl font-bold mb-6"
        style={{ color: "var(--app-text)" }}
      >
        설정
      </h1>

      <div
        className="rounded-2xl border shadow-sm"
        style={{
          background: "var(--app-surface)",
          color: "var(--app-text)",
          borderColor: "var(--app-border)",
        }}
      >
        <div className="p-6 space-y-8">
          <div>
            <h2
              className="text-lg font-bold mb-4"
              style={{ color: "var(--app-text)" }}
            >
              시간 설정
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label
                  className="block text-sm font-semibold mb-2"
                  style={{ color: "var(--app-text-muted)" }}
                >
                  시작 시간
                </label>
                <select
                  value={settings.startHour}
                  onChange={(e) =>
                    updateSettings("startHour", Number(e.target.value))
                  }
                  className="w-full rounded-xl border px-3 py-2"
                  style={{
                    background: "var(--app-surface)",
                    color: "var(--app-text)",
                    borderColor: "var(--app-border)",
                  }}
                >
                  {Array.from({ length: 24 }, (_, i) => i).map((hour) => (
                    <option key={hour} value={hour}>
                      {hour}시
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label
                  className="block text-sm font-semibold mb-2"
                  style={{ color: "var(--app-text-muted)" }}
                >
                  끝 시간
                </label>
                <select
                  value={settings.endHour}
                  onChange={(e) =>
                    updateSettings("endHour", Number(e.target.value))
                  }
                  className="w-full rounded-xl border px-3 py-2"
                  style={{
                    background: "var(--app-surface)",
                    color: "var(--app-text)",
                    borderColor: "var(--app-border)",
                  }}
                >
                  {Array.from({ length: 24 }, (_, i) => i).map((hour) => (
                    <option key={hour} value={hour}>
                      {hour}시
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {settings.startHour >= settings.endHour && (
              <p className="mt-3 text-sm font-medium text-red-500">
                끝 시간은 시작 시간보다 뒤여야 합니다.
              </p>
            )}
          </div>

          <div>
            <h2
              className="text-lg font-bold mb-4"
              style={{ color: "var(--app-text)" }}
            >
              시간 표시 설정
            </h2>

            <div>
              <label
                className="block text-sm font-semibold mb-2"
                style={{ color: "var(--app-text-muted)" }}
              >
                시간 표시 형식
              </label>
              <select
                value={settings.timeFormat}
                onChange={(e) =>
                  updateSettings(
                    "timeFormat",
                    e.target.value as AppSettings["timeFormat"]
                  )
                }
                className="w-full rounded-xl border px-3 py-2"
                style={{
                  background: "var(--app-surface)",
                  color: "var(--app-text)",
                  borderColor: "var(--app-border)",
                }}
              >
                <option value="24h">24시간 형식 (06:00)</option>
                <option value="ampm">AM/PM 형식 (6 AM)</option>
                <option value="korean">한글 형식 (오전 6시)</option>
              </select>
            </div>
          </div>

          <div>
            <h2
              className="text-lg font-bold mb-4"
              style={{ color: "var(--app-text)" }}
            >
              화면 설정
            </h2>

            <div className="space-y-4">
              <ToggleSwitch
                checked={settings.autoDark}
                onChange={(value) => updateSettings("autoDark", value)}
                label="주/야간모드 자동"
              />

              {!settings.autoDark && (
                <ToggleSwitch
                  checked={settings.darkMode}
                  onChange={(value) => updateSettings("darkMode", value)}
                  label="야간모드"
                />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}