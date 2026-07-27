import { useCallback, useEffect, useMemo, useState } from "react";

import { apiDelete, apiGet, apiPostJson, apiPutJson } from "@/lib/api";

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

type ApiManagedUser = {
  id: string;
  email: string;
  name: string;
  role: AuthRole;
  protected: boolean;
  created_at: string;
  updated_at: string;
  last_login_at: string | null;
};

export type ManagedUser = {
  id: string;
  email: string;
  name: string;
  role: AuthRole;
  protected: boolean;
  createdAt: string;
  updatedAt: string;
  lastLoginAt: string | null;
};

export type UserUpsertInput = {
  id?: string;
  name: string;
  email: string;
  password?: string;
  role?: AuthRole;
};

type AuthMeResponse = {
  user: AuthUser | null;
  login_at: string | null;
};

type AuthLoginResponse = {
  user: AuthUser;
  login_at: string | null;
};

type AuthUsersResponse = {
  users: ApiManagedUser[];
};

function toManagedUser(user: ApiManagedUser): ManagedUser {
  return {
    id: user.id,
    email: user.email,
    name: user.name,
    role: user.role,
    protected: user.protected,
    createdAt: user.created_at,
    updatedAt: user.updated_at,
    lastLoginAt: user.last_login_at,
  };
}

function authSessionFromMe(data: AuthMeResponse): AuthSession | null {
  if (!data.user || !data.login_at) return null;
  return { user: data.user, loginAt: data.login_at };
}

export function useAuthState() {
  const [ready, setReady] = useState(false);
  const [session, setSession] = useState<AuthSession | null>(null);
  const [users, setUsers] = useState<ManagedUser[]>([]);

  const loadUsers = useCallback(async (actor?: AuthUser | null) => {
    if (!actor) {
      setUsers([]);
      return [] as ManagedUser[];
    }

    if (actor.role !== "owner") {
      const solo = {
        id: actor.id,
        email: actor.email,
        name: actor.name,
        role: actor.role,
        protected: false,
        createdAt: "",
        updatedAt: "",
        lastLoginAt: null,
      } satisfies ManagedUser;
      setUsers([solo]);
      return [solo];
    }

    const data = await apiGet<AuthUsersResponse>("/api/auth/users");
    const mapped = data.users.map(toManagedUser);
    setUsers(mapped);
    return mapped;
  }, []);

  const refresh = useCallback(async () => {
    try {
      const me = await apiGet<AuthMeResponse>("/api/auth/me");
      const nextSession = authSessionFromMe(me);
      setSession(nextSession);
      await loadUsers(nextSession?.user ?? null);
    } catch {
      setSession(null);
      setUsers([]);
    } finally {
      setReady(true);
    }
  }, [loadUsers]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const api = useMemo(
    () => ({
      ready,
      session,
      user: session?.user ?? null,
      isOwner: session?.user?.role === "owner",
      users,
      async login(email: string, password: string) {
        const data = await apiPostJson<AuthLoginResponse>("/api/auth/login", { email, password });
        const nextSession: AuthSession = {
          user: data.user,
          loginAt: data.login_at ?? new Date().toISOString(),
        };
        setSession(nextSession);
        await loadUsers(nextSession.user);
        return nextSession;
      },
      async logout() {
        try {
          await apiPostJson<{ ok: boolean }>("/api/auth/logout", {});
        } catch {
          // Mesmo se a rede falhar, limpamos a UI local.
        } finally {
          setSession(null);
          setUsers([]);
        }
      },
      async refreshUsers() {
        const current = session?.user ?? (await apiGet<AuthMeResponse>("/api/auth/me")).user;
        return loadUsers(current ?? null);
      },
      async updateUser(input: UserUpsertInput) {
        if (!input.id) {
          throw new Error("Selecione um usuário para atualizar.");
        }
        const data = await apiPutJson<{ user: ApiManagedUser }>(`/api/auth/users/${input.id}`, {
          name: input.name,
          email: input.email,
          ...(input.password ? { password: input.password } : {}),
          ...(input.role ? { role: input.role } : {}),
        });
        const updated = toManagedUser(data.user);
        await refresh();
        return updated;
      },
      async createUser(input: UserUpsertInput) {
        const data = await apiPostJson<{ user: ApiManagedUser }>("/api/auth/users", {
          name: input.name,
          email: input.email,
          password: input.password,
          role: input.role ?? "common",
        });
        const created = toManagedUser(data.user);
        await refresh();
        return created;
      },
      async deleteUser(id: string) {
        await apiDelete<{ ok: boolean }>(`/api/auth/users/${id}`);
        await refresh();
      },
    }),
    [loadUsers, ready, session, users, refresh],
  );

  return api;
}
