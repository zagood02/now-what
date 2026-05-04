"use client";

import Script from "next/script";
import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/app/contexts/AuthContext";
import { authAPI, handleApiError } from "@/lib/api";

type GoogleCredentialResponse = {
  credential?: string;
};

type KakaoAuthResponse = {
  access_token?: string;
};

type KakaoSdk = {
  isInitialized: () => boolean;
  init: (appKey: string) => void;
  Auth: {
    login: (options: {
      success: (response: KakaoAuthResponse) => void;
      fail: (error: unknown) => void;
    }) => void;
  };
};

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (options: {
            client_id: string;
            callback: (response: GoogleCredentialResponse) => void;
          }) => void;
          renderButton: (
            parent: HTMLElement,
            options: { theme: string; size: string; width: number }
          ) => void;
        };
      };
    };
    Kakao?: KakaoSdk;
  }
}

export default function AuthButton() {
  const { user, isLoading, login, logout } = useAuth();
  const googleButtonRef = useRef<HTMLDivElement>(null);
  const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "";
  const kakaoJavaScriptKey = process.env.NEXT_PUBLIC_KAKAO_JAVASCRIPT_KEY || "";
  const [googleLoaded, setGoogleLoaded] = useState(false);
  const [kakaoLoaded, setKakaoLoaded] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGoogleCredential = useCallback(
    async (response: GoogleCredentialResponse) => {
      if (!response.credential) {
        setError("Google 로그인 응답을 확인할 수 없습니다.");
        return;
      }

      try {
        setIsSubmitting(true);
        setError(null);
        const result = await authAPI.loginWithGoogle(response.credential);
        login(result.data.access_token, result.data.user);
      } catch (err) {
        setError(handleApiError(err));
      } finally {
        setIsSubmitting(false);
      }
    },
    [login]
  );

  useEffect(() => {
    if (!googleClientId || !googleLoaded || !window.google || !googleButtonRef.current) {
      return;
    }

    googleButtonRef.current.innerHTML = "";
    window.google.accounts.id.initialize({
      client_id: googleClientId,
      callback: handleGoogleCredential,
    });
    window.google.accounts.id.renderButton(googleButtonRef.current, {
      theme: "outline",
      size: "medium",
      width: 190,
    });
  }, [googleClientId, googleLoaded, handleGoogleCredential]);

  useEffect(() => {
    if (!kakaoJavaScriptKey || !kakaoLoaded || !window.Kakao || window.Kakao.isInitialized()) {
      return;
    }

    window.Kakao.init(kakaoJavaScriptKey);
  }, [kakaoJavaScriptKey, kakaoLoaded]);

  const handleKakaoLogin = () => {
    if (!window.Kakao || !window.Kakao.isInitialized()) {
      setError("Kakao 로그인을 초기화할 수 없습니다.");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    window.Kakao.Auth.login({
      success: async (response) => {
        if (!response.access_token) {
          setError("Kakao 로그인 응답을 확인할 수 없습니다.");
          setIsSubmitting(false);
          return;
        }

        try {
          const result = await authAPI.loginWithKakao(response.access_token);
          login(result.data.access_token, result.data.user);
        } catch (err) {
          setError(handleApiError(err));
        } finally {
          setIsSubmitting(false);
        }
      },
      fail: (err) => {
        console.error("Kakao login failed:", err);
        setError("Kakao 로그인이 취소되었거나 실패했습니다.");
        setIsSubmitting(false);
      },
    });
  };

  if (isLoading) {
    return <div className="mt-8 text-sm opacity-70">로그인 확인 중...</div>;
  }

  return (
    <div className="mt-8 space-y-3">
      {googleClientId && (
        <Script
          src="https://accounts.google.com/gsi/client"
          strategy="afterInteractive"
          onLoad={() => setGoogleLoaded(true)}
        />
      )}
      {kakaoJavaScriptKey && (
        <Script
          src="https://t1.kakaocdn.net/kakao_js_sdk/2.7.4/kakao.min.js"
          strategy="afterInteractive"
          onLoad={() => setKakaoLoaded(true)}
        />
      )}

      {user ? (
        <>
          <div className="text-sm">
            <div className="font-semibold truncate">{user.name}</div>
            <div className="opacity-70 truncate">{user.email}</div>
          </div>
          <button
            type="button"
            onClick={logout}
            className="w-full rounded-md border px-3 py-2 text-sm font-semibold transition hover:opacity-80"
            style={{
              borderColor: "rgba(255,255,255,0.25)",
              color: "var(--sidebar-text)",
            }}
          >
            로그아웃
          </button>
        </>
      ) : (
        <>
          {googleClientId ? (
            <div className={isSubmitting ? "pointer-events-none opacity-60" : ""} ref={googleButtonRef} />
          ) : (
            <button
              type="button"
              disabled
              className="w-full rounded-md border px-3 py-2 text-sm opacity-60"
              style={{ borderColor: "rgba(255,255,255,0.25)" }}
            >
              Google 설정 필요
            </button>
          )}

          <button
            type="button"
            onClick={handleKakaoLogin}
            disabled={!kakaoJavaScriptKey || !kakaoLoaded || isSubmitting}
            className="w-full rounded-md px-3 py-2 text-sm font-semibold text-black transition disabled:cursor-not-allowed disabled:opacity-60"
            style={{ background: "#fee500" }}
          >
            Kakao 로그인
          </button>
        </>
      )}

      {error && <p className="text-xs text-red-300">{error}</p>}
    </div>
  );
}
