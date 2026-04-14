export type TimeFormat = "24h" | "ampm" | "korean";

export type AppSettings = {
  startHour: number;
  endHour: number;
  timeFormat: TimeFormat;
  autoDark: boolean;
  darkMode: boolean;
};

export const defaultSettings: AppSettings = {
  startHour: 6,
  endHour: 22,
  timeFormat: "24h",
  autoDark: true,
  darkMode: false,
};

export function readSettings(): AppSettings {
  if (typeof window === "undefined") {
    return defaultSettings;
  }

  try {
    const raw = localStorage.getItem("settings");
    if (!raw) return defaultSettings;

    const parsed = JSON.parse(raw);

    return {
      startHour:
        typeof parsed.startHour === "number"
          ? parsed.startHour
          : defaultSettings.startHour,
      endHour:
        typeof parsed.endHour === "number"
          ? parsed.endHour
          : defaultSettings.endHour,
      timeFormat:
        parsed.timeFormat === "24h" ||
        parsed.timeFormat === "ampm" ||
        parsed.timeFormat === "korean"
          ? parsed.timeFormat
          : defaultSettings.timeFormat,
      autoDark:
        typeof parsed.autoDark === "boolean"
          ? parsed.autoDark
          : defaultSettings.autoDark,
      darkMode:
        typeof parsed.darkMode === "boolean"
          ? parsed.darkMode
          : defaultSettings.darkMode,
    };
  } catch {
    return defaultSettings;
  }
}

export function saveSettings(settings: AppSettings) {
  if (typeof window === "undefined") return;
  localStorage.setItem("settings", JSON.stringify(settings));
}

export function shouldUseDarkMode(settings: AppSettings) {
  if (settings.autoDark) {
    const hour = new Date().getHours();
    return hour >= 18 || hour < 6;
  }

  return settings.darkMode;
}