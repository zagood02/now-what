"use client";

import "./globals.css";
import Link from "next/link";
import { useState } from "react";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);

  return (
    <html lang="ko">
      <body>
        <div className="flex min-h-screen" style={{ background: "var(--app-bg)" }}>
          {open && (
            <button
              type="button"
              aria-label="메뉴 닫기"
              className="fixed inset-0 z-40 md:hidden"
              onClick={() => setOpen(false)}
              style={{ background: "rgba(0,0,0,0.4)" }}
            />
          )}

          <aside
            className={`fixed top-0 left-0 z-50 h-full w-64 p-4 transform transition-transform duration-200 md:static md:translate-x-0 ${
              open ? "translate-x-0" : "-translate-x-full"
            }`}
            style={{
              background: "var(--app-surface)",
              borderRight: "1px solid var(--app-border)",
            }}
          >
            <h2 className="text-xl font-bold mb-6" style={{ color: "var(--app-text)" }}>
              그래서 이제 뭐함?
            </h2>

            <nav className="flex flex-col gap-2">
              <NavItem href="/" label="대시보드" onClick={() => setOpen(false)} />
              <NavItem href="/schedule" label="시간표" onClick={() => setOpen(false)} />
              <NavItem href="/manage" label="일정관리" onClick={() => setOpen(false)} />
              <NavItem href="/settings" label="설정" onClick={() => setOpen(false)} />
            </nav>
          </aside>

          <div className="flex-1 flex flex-col min-w-0">
            <header
              className="flex items-center justify-between px-4 py-3 border-b md:hidden"
              style={{
                background: "var(--app-surface)",
                borderColor: "var(--app-border)",
              }}
            >
              <button
                type="button"
                onClick={() => setOpen((prev) => !prev)}
                className="px-3 py-2 rounded-lg font-bold"
                style={{
                  background: "var(--primary-button-bg)",
                  color: "var(--primary-button-text)",
                }}
              >
                ☰
              </button>

              <span className="font-bold" style={{ color: "var(--app-text)" }}>
                그래서 이제 뭐함?
              </span>

              <div className="w-10" />
            </header>

            <main className="flex-1 p-4 md:p-6" style={{ background: "var(--app-bg)" }}>
              {children}
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}

function NavItem({
  href,
  label,
  onClick,
}: {
  href: string;
  label: string;
  onClick?: () => void;
}) {
  return (
    <Link
      href={href}
      onClick={onClick}
      className="px-3 py-2 rounded-lg font-semibold hover:opacity-80"
      style={{
        background: "var(--app-bg)",
        color: "var(--app-text)",
        border: "1px solid var(--app-border)",
      }}
    >
      {label}
    </Link>
  );
}