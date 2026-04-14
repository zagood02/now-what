"use client";

import { useEffect } from "react";
import { readSettings, shouldUseDarkMode } from "@/lib/settings";

function applyThemeClass() {
  const settings = readSettings();
  const isDark = shouldUseDarkMode(settings);
  const root = document.documentElement;

  root.classList.remove("theme-light", "theme-dark");
  root.classList.add(isDark ? "theme-dark" : "theme-light");
}

export default function ThemeInitializer() {
  useEffect(() => {
    applyThemeClass();

    const interval = window.setInterval(() => {
      applyThemeClass();
    }, 60 * 1000);

    const handleThemeRefresh = () => {
      applyThemeClass();
    };

    window.addEventListener("theme-refresh", handleThemeRefresh as EventListener);

    return () => {
      clearInterval(interval);
      window.removeEventListener(
        "theme-refresh",
        handleThemeRefresh as EventListener
      );
    };
  }, []);

  return null;
}

export { applyThemeClass };