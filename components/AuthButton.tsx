"use client";

import Script from "next/script";
import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/app/contexts/AuthContext";
import { authAPI, handleApiError } from "@/lib/api";

type GoogleCredentialResponse = {
  credential?: string;
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
  }
}

export default function AuthButton() {
  const { user, isLoading, login, logout } = useAuth();
  const googleButtonRef = useRef<HTMLDivElement>(null);
  const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "";
  const [googleLoaded, setGoogleLoaded] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGoogleCredential = useCallback(
    async (response: GoogleCredentialResponse) => {
      if (!response.credential) {
        setError("Google login response is missing a credential.");
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

  if (isLoading) {
    return <div className="mt-8 text-sm opacity-70">Checking login...</div>;
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
            Logout
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
              Google setup required
            </button>
          )}
        </>
      )}

      {error && <p className="text-xs text-red-300">{error}</p>}
    </div>
  );
}
