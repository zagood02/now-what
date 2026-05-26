"use client";

import { useState } from "react";
import {
  readUsers,
  saveCurrentUser,
} from "@/lib/thirdStageStorage";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");

  const handleLogin = (
    e: React.FormEvent<HTMLFormElement>
  ) => {
    e.preventDefault();

    const user = readUsers().find(
      (item) =>
        item.email === email.trim() &&
        item.password === password
    );

    if (!user) {
      setMessage(
        "이메일 또는 비밀번호가 맞지 않습니다."
      );
      return;
    }

    saveCurrentUser(user);

    setMessage(
      `${user.name}님 로그인 완료`
    );
  };

  return (
    <div>
      <h1
        className="text-3xl font-bold mb-2"
        style={{ color: "var(--app-text)" }}
      >
        로그인
      </h1>

      <p
        className="mb-6"
        style={{
          color: "var(--app-text-muted)",
        }}
      >
        사용자별로 일정, 할일,
        AI 계획 데이터를 분리하기 위한
        임시 로그인 페이지입니다.
      </p>

      <form
        onSubmit={handleLogin}
        className="max-w-xl rounded-2xl border p-5 shadow-sm space-y-4"
        style={{
          background: "var(--app-surface)",
          borderColor: "var(--app-border)",
        }}
      >
        <InputLabel label="이메일">
          <input
            value={email}
            onChange={(e) =>
              setEmail(e.target.value)
            }
            className="form-input"
            placeholder="test@example.com"
          />
        </InputLabel>

        <InputLabel label="비밀번호">
          <input
            type="password"
            value={password}
            onChange={(e) =>
              setPassword(e.target.value)
            }
            className="form-input"
            placeholder="비밀번호"
          />
        </InputLabel>

        <button
          className="w-full rounded-xl py-3 font-bold"
          style={{
            background:
              "var(--primary-button-bg)",
            color:
              "var(--primary-button-text)",
          }}
        >
          로그인
        </button>

        {message && (
          <p
            className="font-semibold"
            style={{
              color: "var(--app-text)",
            }}
          >
            {message}
          </p>
        )}
      </form>

      <style jsx global>{`
        .form-input {
          width: 100%;
          border-radius: 0.75rem;
          border: 1px solid
            var(--app-border);
          background: var(--app-bg);
          color: var(--app-text);
          padding: 0.75rem;
          outline: none;
        }
      `}</style>
    </div>
  );
}

function InputLabel({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <div
        className="text-sm font-bold mb-2"
        style={{
          color: "var(--app-text)",
        }}
      >
        {label}
      </div>

      {children}
    </label>
  );
}