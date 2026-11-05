"use client";

import { createContext, useCallback, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { setAuthToken } from "@/lib/api-client";
import { authService } from "@/services/auth.service";

const TOKEN_KEY = "sentinelai:token";

export interface AuthUser {
  id: number;
  email: string;
}

export interface AuthContextValue {
  token: string | null;
  user: AuthUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);

  // Rehydrate the token from storage on first client render.
  useEffect(() => {
    const saved = window.localStorage.getItem(TOKEN_KEY);
    if (saved) {
      setAuthToken(saved);
      setToken(saved);
    }
    setHydrated(true);
  }, []);

  // Resolve the current user whenever we hold a token.
  const meQuery = useQuery({
    queryKey: ["auth", "me", token],
    queryFn: authService.me,
    enabled: hydrated && !!token,
    retry: false,
  });

  // A token that the backend rejects should be cleared.
  useEffect(() => {
    if (meQuery.isError) {
      window.localStorage.removeItem(TOKEN_KEY);
      setAuthToken(null);
      setToken(null);
    }
  }, [meQuery.isError]);

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await authService.login(email, password);
    window.localStorage.setItem(TOKEN_KEY, access_token);
    setAuthToken(access_token);
    setToken(access_token);
  }, []);

  const logout = useCallback(() => {
    window.localStorage.removeItem(TOKEN_KEY);
    setAuthToken(null);
    setToken(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      user: meQuery.data ?? null,
      isLoading: !hydrated || (!!token && meQuery.isLoading),
      isAuthenticated: !!token,
      login,
      logout,
    }),
    [token, meQuery.data, meQuery.isLoading, hydrated, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
