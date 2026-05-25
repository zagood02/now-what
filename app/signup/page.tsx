"use client";

import { useState } from "react";

import {
  createId,
  readUsers,
  saveCurrentUser,
  saveUsers,
} from "@/lib/thirdStageStorage";

export default function SignupPage() {
  const [name, setName] = useState("");
  const [email, setEmail] =
    useState("");
  const [password, setPassword] =
    useState("");
  const [message, setMessage] =
    useState("");

  const handleSignup = (
    e: React.FormEvent<HTMLFormElement>
  ) => {
    e.preventDefault();

    if (
      !name.trim() ||
      !email.trim() ||
      !password
    ) {
      setMessage(
        "이름, 이메일, 비밀번호를 모두 입력하세요."
      );
      return;
    }

    const users = readUsers();

    if (
      users.some(
        (user) =>
          user.email === email.trim()
      )
    ) {
      setMessage(
        "이미 가입된 이메일입니다."
      );
      return;
    }

    const now =
      new Date().toISOString();

    const user = {
      id: createId("user"),
      name: name.trim(),
      email: email.trim(),
      password,
      created_at: now,
    };

    saveUsers([...users, user]);

    saveCurrentUser(user);

    setMessage(
      "회원가입 완료. 현재 사용자로 저장되었습니다."
    );
  };

  return (
    <div>
      <h1
        className="text-3xl font-bold mb-2"
        style={{
          color: "var(--app-text)",
        }}
      >
        회원가입
      </h1>

      <p
        className="mb-6"
        style={{
          color:
            "var(--app-text-muted)",
        }}
      >
        현재는 localStorage 기반
        임시 회원가입입니다.
      </p>

      <form
        onSubmit={handleSignup}
        className="max-w-xl rounded-2xl border p-5 shadow-sm space-y-4"
        style={{
          background:
            "var(--app-surface)",
          borderColor:
            "var(--app-border)",
        }}
      >
        <InputLabel label="이름">
          <input
            value={name}
            onChange={(e) =>
              setName(e.target.value)
            }
            className="form-input"
          />
        </InputLabel>

        <InputLabel label="이메일">
          <input
            value={email}
            onChange={(e) =>
              setEmail(e.target.value)
            }
            className="form-input"
          />
        </InputLabel>

        <InputLabel label="비밀번호">
          <input
            type="password"
            value={password}
            onChange={(e) =>
              setPassword(
                e.target.value
              )
            }
            className="form-input"
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
          회원가입
        </button>

        {message && (
          <p
            className="font-semibold"
            style={{
              color:
                "var(--app-text)",
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