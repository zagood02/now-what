"use client";

import "./globals.css";
import Link from "next/link";
import { useEffect, useLayoutEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  isGuestSessionActive,
  readCurrentUser,
  type AppUser,
} from "@/lib/thirdStageStorage";
import { applyThemeClass } from "@/components/ThemeInitializer";

const protectedRoutes = ["/", "/schedule", "/manage", "/todo", "/ai-plan", "/settings"];

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();

  const [open, setOpen] = useState(false);
  const [currentUser, setCurrentUser] = useState<AppUser | null>(null);
  const [guestActive, setGuestActive] = useState(false);
  const [authReady, setAuthReady] = useState(false);
  const [blockedModalOpen, setBlockedModalOpen] = useState(false);

  const refreshAuthState = () => {
    setCurrentUser(readCurrentUser());
    setGuestActive(isGuestSessionActive());
    setAuthReady(true);
  };

  const isLoggedIn = Boolean(currentUser) || guestActive;

  const isProtectedPath = (path: string) => {
    return protectedRoutes.some((route) => path === route || path.startsWith(`${route}/`));
  };

  useLayoutEffect(() => {
    applyThemeClass();
  }, []);

  useEffect(() => {
    refreshAuthState();

    const handleAuthChanged = () => {
      refreshAuthState();
    };

    const handleThemeChanged = () => {
      applyThemeClass();
    };

    const handleStorage = () => {
      applyThemeClass();
      refreshAuthState();
    };

    window.addEventListener("auth-state-changed", handleAuthChanged);
    window.addEventListener("storage", handleStorage);
    window.addEventListener("theme-refresh", handleThemeChanged);
    window.addEventListener("theme-state-changed", handleThemeChanged);

    return () => {
      window.removeEventListener("auth-state-changed", handleAuthChanged);
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener("theme-refresh", handleThemeChanged);
      window.removeEventListener("theme-state-changed", handleThemeChanged);
    };
  }, []);

  useEffect(() => {
    if (authReady && !isLoggedIn && isProtectedPath(pathname)) {
      setBlockedModalOpen(true);
    }
  }, [pathname, isLoggedIn, authReady]);

  const handleBlockedConfirm = () => {
    setBlockedModalOpen(false);

    if (!isLoggedIn && pathname !== "/login") {
      router.push("/login");
    }
  };

  const handleProtectedMove = (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
    if (!isLoggedIn && isProtectedPath(href)) {
      e.preventDefault();
      setOpen(false);
      setBlockedModalOpen(true);
    }
  };

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
              <NavItem href="/" label="대시보드" onClick={() => setOpen(false)} onProtectedMove={handleProtectedMove} />
              <NavItem href="/schedule" label="시간표" onClick={() => setOpen(false)} onProtectedMove={handleProtectedMove} />
              <NavItem href="/manage" label="일정관리" onClick={() => setOpen(false)} onProtectedMove={handleProtectedMove} />
              <NavItem href="/todo" label="할일" onClick={() => setOpen(false)} onProtectedMove={handleProtectedMove} />
              <NavItem href="/ai-plan" label="AI 계획 생성" onClick={() => setOpen(false)} onProtectedMove={handleProtectedMove} />
              <NavItem href="/settings" label="설정" onClick={() => setOpen(false)} onProtectedMove={handleProtectedMove} />
              <NavItem href="/login" label={isLoggedIn ? "마이페이지" : "로그인"} onClick={() => setOpen(false)} />
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

        {blockedModalOpen && (
          <div
            className="fixed inset-0 flex items-center justify-center p-4"
            style={{
              zIndex: 100,
              background: "rgba(0,0,0,0.45)",
            }}
          >
            <div
              className="w-full max-w-sm rounded-2xl border p-6 shadow-xl text-center"
              style={{
                background: "var(--app-surface)",
                borderColor: "var(--app-border)",
              }}
            >
              <h2 className="text-xl font-bold mb-3" style={{ color: "var(--app-text)" }}>
                로그인 후 이용해 주세요
              </h2>

              <button
                type="button"
                onClick={handleBlockedConfirm}
                className="mt-4 w-full rounded-xl py-3 font-bold"
                style={{
                  background: "var(--primary-button-bg)",
                  color: "var(--primary-button-text)",
                }}
              >
                확인
              </button>
            </div>
          </div>
        )}
      </body>
    </html>
  );
}

function NavItem({
  href,
  label,
  onClick,
  onProtectedMove,
}: {
  href: string;
  label: string;
  onClick?: () => void;
  onProtectedMove?: (e: React.MouseEvent<HTMLAnchorElement>, href: string) => void;
}) {
  return (
    <Link
      href={href}
      onClick={(e) => {
        onProtectedMove?.(e, href);
        onClick?.();
      }}
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
