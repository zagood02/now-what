"use client";

import React, { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { authAPI, getStoredAccessToken, setApiAccessToken, type User } from "@/lib/api";

const USER_STORAGE_KEY = "now_what_user";

type AuthContextType = {
  user: User | null;
  isLoading: boolean;
  login: (accessToken: string, user: User) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};

type AuthProviderProps = {
  children: ReactNode;
};

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const login = (accessToken: string, userData: User) => {
    setApiAccessToken(accessToken);
    setUser(userData);
    window.localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(userData));
  };

  const logout = () => {
    setApiAccessToken(null);
    setUser(null);
    window.localStorage.removeItem(USER_STORAGE_KEY);
  };

  useEffect(() => {
    const savedToken = getStoredAccessToken();

    const finalize = () => {
      setIsLoading(false);
    };

    const clearInvalidAuth = () => {
      logout();
      finalize();
    };

    const tryRefresh = async () => {
      try {
        const resp = await authAPI.refresh();
        const access = resp.data.access_token;
        setApiAccessToken(access);
        const me = await authAPI.me();
        setUser(me.data);
        window.localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(me.data));
      } catch {
        setUser(null);
        window.localStorage.removeItem(USER_STORAGE_KEY);
      } finally {
        finalize();
      }
    };

    const loadCurrentUser = async () => {
      setApiAccessToken(savedToken);

      try {
        const response = await authAPI.me();
        setUser(response.data);
        window.localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(response.data));
      } catch {
        try {
          await tryRefresh();
          return;
        } catch {
          // noop; clearInvalidAuth will run below
        }
        clearInvalidAuth();
        return;
      }

      finalize();
    };

    if (!savedToken) {
      window.localStorage.removeItem(USER_STORAGE_KEY);
      void tryRefresh();
      return;
    }

    void loadCurrentUser();
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};
