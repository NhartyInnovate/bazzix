import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useRouter } from "@tanstack/react-router";

import { api, getToken, setToken, type User } from "./api";

type AuthState = {
  user: User | null;
  status: "loading" | "authenticated" | "unauthenticated";
  login: (email: string, password: string) => Promise<void>;
  register: (input: {
    first_name: string;
    last_name: string;
    email: string;
    password: string;
  }) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthState["status"]>("loading");

  const loadUser = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setStatus("unauthenticated");
      return;
    }
    try {
      const me = await api.me();
      setUser(me);
      setStatus("authenticated");
    } catch {
      setToken(null);
      setUser(null);
      setStatus("unauthenticated");
    }
  }, []);

  useEffect(() => {
    void loadUser();
    const onExpire = () => {
      setUser(null);
      setStatus("unauthenticated");
      router.navigate({ to: "/login" });
    };
    window.addEventListener("bazzix:session-expired", onExpire);
    return () => window.removeEventListener("bazzix:session-expired", onExpire);
  }, [loadUser, router]);

  const login = useCallback(async (email: string, password: string) => {
    await api.login(email, password);
    const me = await api.me();
    setUser(me);
    setStatus("authenticated");
  }, []);

  const register = useCallback<AuthState["register"]>(async (input) => {
    await api.register(input);
    await api.login(input.email, input.password);
    const me = await api.me();
    setUser(me);
    setStatus("authenticated");
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    setStatus("unauthenticated");
    router.navigate({ to: "/login" });
  }, [router]);

  const value = useMemo<AuthState>(
    () => ({ user, status, login, register, logout, refresh: loadUser }),
    [user, status, login, register, logout, loadUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
