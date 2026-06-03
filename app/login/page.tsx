"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/app/contexts/AuthContext";
import { authAPI, handleApiError } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const { user, isLoading, login, logout } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleLogin = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setMessage("");
    setIsSubmitting(true);

    try {
      const response = await authAPI.login({
        email: email.trim().toLowerCase(),
        password,
      });

      login(response.data.access_token, response.data.user);
      router.push("/");
    } catch (error) {
      setMessage(handleApiError(error));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  if (isLoading) {
    return <div>로딩 중...</div>;
  }

  if (user) {
    return (
      <div>
        <h1 className="text-3xl font-bold mb-4" style={{ color: "var(--app-text)" }}>
          마이페이지
        </h1>

        <section className="rounded-2xl border p-6 shadow-sm mb-6" style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}>
          <div className="text-lg font-bold" style={{ color: "var(--app-text)" }}>
            {user.name}
          </div>
          <div className="text-sm mt-2" style={{ color: "var(--app-text-muted)" }}>
            {user.email}
          </div>
          <div className="text-sm mt-1" style={{ color: "var(--app-text-muted)" }}>
            타임존: {user.timezone}
          </div>

          <button
            type="button"
            onClick={handleLogout}
            className="mt-6 rounded-xl px-4 py-3 font-bold"
            style={{ background: "var(--card-red-bg)", color: "var(--card-red-text)" }}
          >
            로그아웃
          </button>
        </section>

        <Link href="/" className="text-sm font-semibold underline" style={{ color: "var(--app-text)" }}>
          대시보드로 이동
        </Link>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2" style={{ color: "var(--app-text)" }}>
        로그인
      </h1>

      {/* <p className="mb-6" style={{ color: "var(--app-text-muted)" }}>
        {/* 실제 백엔드 인증을 사용합니다. */}
      {/* </p> */} 

      <form
        onSubmit={handleLogin}
        className="max-w-xl rounded-2xl border p-5 shadow-sm space-y-4"
        style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}
      >
        <InputLabel label="이메일">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="form-input"
            placeholder="이메일"
          />
        </InputLabel>

        <InputLabel label="비밀번호">
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="form-input"
            placeholder="비밀번호"
          />
        </InputLabel>

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full rounded-xl py-3 font-bold"
          style={{ background: "var(--primary-button-bg)", color: "var(--primary-button-text)" }}
        >
          {isSubmitting ? "로그인 중..." : "로그인"}
        </button>

        <p className="text-sm text-center" style={{ color: "var(--app-text-muted)" }}>
          계정이 없으신가요? <Link href="/signup" className="font-semibold underline">회원가입</Link>
        </p>

        {message && (
          <p className="font-semibold" style={{ color: "var(--app-text)" }}>
            {message}
          </p>
        )}
      </form>

      <style jsx global>{`
        .form-input {
          width: 100%;
          border-radius: 0.75rem;
          border: 1px solid var(--app-border);
          background: var(--app-bg);
          color: var(--app-text);
          padding: 0.75rem;
          outline: none;
        }
      `}</style>
    </div>
  );
}

function InputLabel({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <div className="text-sm font-bold mb-2" style={{ color: "var(--app-text)" }}>
        {label}
      </div>
      {children}
    </label>
  );
}
