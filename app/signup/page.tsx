"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/app/contexts/AuthContext";
import { authAPI, handleApiError, userAPI } from "@/lib/api";

export default function SignupPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSignup = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setMessage("");
    setIsSubmitting(true);

    try {
      await userAPI.register({
        name: name.trim(),
        email: email.trim().toLowerCase(),
        password,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Seoul",
      });

      const loginResponse = await authAPI.login({
        email: email.trim().toLowerCase(),
        password,
      });

      login(loginResponse.data.access_token, loginResponse.data.user);
      router.push("/");
    } catch (error) {
      setMessage(handleApiError(error));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2" style={{ color: "var(--app-text)" }}>
        회원가입
      </h1>

      <p className="mb-6" style={{ color: "var(--app-text-muted)" }}>
        백엔드에 사용자 정보를 저장하고 로그인합니다.
      </p>

      <form
        onSubmit={handleSignup}
        className="max-w-xl rounded-2xl border p-5 shadow-sm space-y-4"
        style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}
      >
        <InputLabel label="이름">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="form-input"
            placeholder="이름"
          />
        </InputLabel>

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
          {isSubmitting ? "가입 중..." : "회원가입"}
        </button>

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
