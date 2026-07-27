import { useEffect, useMemo, useState } from "react";

export type AuthRole = "owner" | "common";

export type AuthUser = {
  id: string;
  email: string;
  name: string;
  role: AuthRole;
};

export type AuthSession = {
  user: AuthUser;
  loginAt: string;
};

const AUTH_STORAGE_KEY = "viral.auth.session.v1";
const OWNER_EMAIL = "mago@dono.site";
const OWNER_PASSWORD = "123698745";

const SEED_USERS: Array<AuthUser & { password: string }> = [
  {
    id: "u_owner_mago",
    email: OWNER_EMAIL,
    name: "Mago",
    role: "owner",
    password: OWNER_PASSWORD,
  },
];

export function loadAuthSession(): AuthSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AuthSession;
    if (!parsed?.user?.id || !parsed?.user?.email || !parsed?.user?.role) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function saveAuthSession(session: AuthSession | null) {
  if (typeof window === "undefined") return;
  if (!session) {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
    return;
  }
  window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
}

export function authenticate(email: string, password: string): AuthSession | null {
  const normalized = email.trim().toLowerCase();
  const match = SEED_USERS.find(
    (user) => user.email.toLowerCase() === normalized && user.password === password,
  );
  if (!match) return null;
  const { password: _password, ...user } = match;
  return {
    user,
    loginAt: new Date().toISOString(),
  };
}

export function useAuthState() {
  const [ready, setReady] = useState(false);
  const [session, setSession] = useState<AuthSession | null>(null);

  useEffect(() => {
    setSession(loadAuthSession());
    setReady(true);
  }, []);

  const api = useMemo(
    () => ({
      ready,
      session,
      user: session?.user ?? null,
      isOwner: session?.user?.role === "owner",
      login(email: string, password: string) {
        const next = authenticate(email, password);
        if (!next) return null;
        setSession(next);
        saveAuthSession(next);
        return next;
      },
      logout() {
        setSession(null);
        saveAuthSession(null);
      },
    }),
    [ready, session],
  );

  return api;
}
