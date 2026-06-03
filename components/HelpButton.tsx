"use client";

import React, { useState } from "react";

interface HelpButtonProps {
  title: string;
  children: React.ReactNode;
}

export default function HelpButton({ title, children }: HelpButtonProps) {
  const [showHelp, setShowHelp] = useState(false);

  return (
    <div className="relative inline-block">
      <button
        type="button"
        onClick={() => setShowHelp((prev) => !prev)}
        className="rounded-full border border-slate-300 bg-slate-100 px-3 py-2 text-sm font-bold text-slate-700 hover:bg-slate-200"
        aria-expanded={showHelp}
        aria-label="도움말 보기"
      >
        ?
      </button>

      {showHelp && (
        <div
          className="absolute top-full right-0 mt-2 z-50 w-72 rounded-2xl border border-slate-300 bg-white p-4 text-sm text-slate-700 shadow-lg"
          style={{
            background: "var(--app-surface)",
            color: "var(--app-text)",
            borderColor: "var(--app-border)",
          }}
        >
          <h2 className="font-bold mb-2">{title}</h2>
          {children}
        </div>
      )}
    </div>
  );
}
