import { useCallback, useEffect, useMemo, useState } from "react";

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

type StoredAuthUser = AuthUser & {
  password: string;
  protected?: boolean;
  createdAt: string;
  updatedAt: string;
  lastLoginAt: string | null;
};

export type ManagedUser = Omit<StoredAuthUser, "password">;

export type UserUpsertInput = {
  id?: string;
  name: string;
  email: string;
  password?: string;
  role?: AuthRole;
};

const AUTH_STORAGE_KEY = "viral.auth.session.v1";
const USERS_STORAGE_KEY = "viral.auth.users.v1";

const OWNER_EMAIL = "mago@dono.site";
const OWNER_PASSWORD = "123698745";
const DEMO_EMAIL = "usuario@viral.site";
const DEMO_PASSWORD = "123698745";

function nowIso() {
  return new Date().toISOString();
}

function createSeedUsers(): StoredAuthUser[] {
  const now = nowIso();
  return [
    {
      id: "u_owner_mago",
      email: OWNER_EMAIL,
      name: "Mago",
      role: "owner",
      password: OWNER_PASSWORD,
      protected: true,
      createdAt: now,
      updatedAt: now,
      lastLoginAt: null,
    },
    {
      id: "u_common_demo",
      email: DEMO_EMAIL,
      name: "Operador",
      role: "common",
      password: DEMO_PASSWORD,
      createdAt: now,
      updatedAt: now,
      lastLoginAt: null,
    },
  ];
}

function isStoredAuthUser(value: unknown): value is StoredAuthUser {
  return (
    !!value && typeof value === "object" && "id" in value && "email" in value && "password" in value
  );
}

function toPublicUser(user: StoredAuthUser): ManagedUser {
  const { password: _password, ...publicUser } = user;
  return publicUser;
}

function readUsers(): StoredAuthUser[] {
  if (typeof window === "undefined") return createSeedUsers();
  try {
    const raw = window.localStorage.getItem(USERS_STORAGE_KEY);
    if (!raw) {
      const seeded = createSeedUsers();
      window.localStorage.setItem(USERS_STORAGE_KEY, JSON.stringify(seeded));
      return seeded;
    }

    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) {
      const seeded = createSeedUsers();
      window.localStorage.setItem(USERS_STORAGE_KEY, JSON.stringify(seeded));
      return seeded;
    }

    const users = parsed.filter(isStoredAuthUser).map((user) => ({
      ...user,
      name: user.name?.trim() || user.email.split("@")[0] || "Usuário",
      role: user.role === "owner" ? "owner" : "common",
      protected: Boolean(user.protected),
      createdAt: user.createdAt || nowIso(),
      updatedAt: user.updatedAt || nowIso(),
      lastLoginAt: user.lastLoginAt ?? null,
    }));

    if (!users.some((user) => user.role === "owner")) {
      const seeded = createSeedUsers();
      window.localStorage.setItem(USERS_STORAGE_KEY, JSON.stringify(seeded));
      return seeded;
    }

    return users;
  } catch {
    const seeded = createSeedUsers();
    window.localStorage.setItem(USERS_STORAGE_KEY, JSON.stringify(seeded));
    return seeded;
  }
}

function writeUsers(users: StoredAuthUser[]) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(USERS_STORAGE_KEY, JSON.stringify(users));
}

function readSession(): AuthSession | null {
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

function writeSession(session: AuthSession | null) {
  if (typeof window === "undefined") return;
  if (!session) {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
    return;
  }
  window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
}

function updateSessionWithUsers(
  session: AuthSession | null,
  users: StoredAuthUser[],
): AuthSession | null {
  if (!session) return null;
  const current = users.find((user) => user.id === session.user.id);
  if (!current) return null;
  return {
    user: toPublicUser(current),
    loginAt: session.loginAt,
  };
}

function normalizeUsers(users: StoredAuthUser[]): StoredAuthUser[] {
  if (!users.some((user) => user.role === "owner")) {
    return createSeedUsers();
  }
  return users;
}

function authenticateFromUsers(users: StoredAuthUser[], email: string, password: string) {
  const normalizedEmail = email.trim().toLowerCase();
  const match = users.find(
    (user) => user.email.toLowerCase() === normalizedEmail && user.password === password,
  );
  if (!match) return null;

  const loginAt = nowIso();
  const nextUsers = users.map((user) =>
    user.id === match.id ? { ...user, updatedAt: loginAt, lastLoginAt: loginAt } : user,
  );

  return {
    session: {
      user: toPublicUser({ ...match, updatedAt: loginAt, lastLoginAt: loginAt }),
      loginAt,
    } satisfies AuthSession,
    users: nextUsers,
  };
}

function canEditTarget(session: AuthSession | null, targetId: string) {
  return session?.user.role === "owner" || session?.user.id === targetId;
}

function upsertUserRecord(
  users: StoredAuthUser[],
  input: UserUpsertInput,
  session: AuthSession | null,
) {
  const normalizedEmail = input.email.trim().toLowerCase();
  const current = input.id ? users.find((user) => user.id === input.id) : null;
  const now = nowIso();

  if (current && !canEditTarget(session, current.id)) {
    throw new Error("Sem permissão para editar outros usuários.");
  }
  if (!current && session?.user.role !== "owner") {
    throw new Error("Sem permissão para criar usuários.");
  }
  if (!current && !input.password) {
    throw new Error("A senha é obrigatória para criar um usuário.");
  }

  const duplicate = users.find(
    (user) => user.email.toLowerCase() === normalizedEmail && user.id !== input.id,
  );
  if (duplicate) {
    throw new Error("Este email já está em uso.");
  }

  if (current?.protected) {
    if (normalizedEmail !== current.email.toLowerCase()) {
      throw new Error("O email do dono original é protegido.");
    }
  }

  if (current) {
    const nextUsers = users.map((user) =>
      user.id !== current.id
        ? user
        : {
            ...user,
            name: input.name.trim() || user.name,
            email: current.protected ? user.email : normalizedEmail,
            role: current.protected ? user.role : (input.role ?? user.role),
            password: input.password ? input.password : user.password,
            updatedAt: now,
          },
    );

    return { users: nextUsers, user: nextUsers.find((user) => user.id === current.id) ?? current };
  }

  const created: StoredAuthUser = {
    id:
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? `u_${crypto.randomUUID().replace(/-/g, "")}`
        : `u_${Math.random().toString(36).slice(2, 10)}${Date.now().toString(36)}`,
    email: normalizedEmail,
    name: input.name.trim() || normalizedEmail.split("@")[0] || "Usuário",
    role: input.role ?? "common",
    password: input.password ?? "",
    protected: false,
    createdAt: now,
    updatedAt: now,
    lastLoginAt: null,
  };

  return { users: [...users, created], user: created };
}

function deleteUserRecord(users: StoredAuthUser[], id: string, session: AuthSession | null) {
  const target = users.find((user) => user.id === id);
  if (!target) throw new Error("Usuário não encontrado.");
  if (!canEditTarget(session, id)) throw new Error("Sem permissão para excluir usuários.");
  if (target.protected) throw new Error("O dono original não pode ser excluído.");
  if (session?.user.id === id) throw new Error("Você não pode excluir a própria conta logada.");

  return users.filter((user) => user.id !== id);
}

export function loadAuthSession(): AuthSession | null {
  return readSession();
}

export function saveAuthSession(session: AuthSession | null) {
  writeSession(session);
}

export function authenticate(email: string, password: string): AuthSession | null {
  const result = authenticateFromUsers(readUsers(), email, password);
  if (!result) return null;
  writeUsers(result.users);
  writeSession(result.session);
  return result.session;
}

export function listManagedUsers(): ManagedUser[] {
  return readUsers().map(toPublicUser);
}

export function useAuthState() {
  const [ready, setReady] = useState(false);
  const [session, setSession] = useState<AuthSession | null>(null);
  const [users, setUsers] = useState<StoredAuthUser[]>([]);

  const sync = useCallback(() => {
    const currentUsers = normalizeUsers(readUsers());
    const currentSession = updateSessionWithUsers(readSession(), currentUsers);
    setUsers(currentUsers);
    setSession(currentSession);
    if (currentSession !== readSession()) {
      writeSession(currentSession);
    }
    writeUsers(currentUsers);
  }, []);

  useEffect(() => {
    sync();
    setReady(true);
  }, [sync]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const onStorage = () => sync();
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [sync]);

  const api = useMemo(
    () => ({
      ready,
      session,
      user: session?.user ?? null,
      isOwner: session?.user?.role === "owner",
      users: users.map(toPublicUser),
      login(email: string, password: string) {
        const result = authenticateFromUsers(users, email, password);
        if (!result) return null;
        const nextUsers = normalizeUsers(result.users);
        setUsers(nextUsers);
        setSession(result.session);
        writeUsers(nextUsers);
        writeSession(result.session);
        return result.session;
      },
      logout() {
        setSession(null);
        writeSession(null);
      },
      refreshUsers() {
        const nextUsers = normalizeUsers(readUsers());
        setUsers(nextUsers);
        return nextUsers.map(toPublicUser);
      },
      updateUser(input: UserUpsertInput) {
        const result = upsertUserRecord(users, input, session);
        const nextUsers = normalizeUsers(result.users);
        setUsers(nextUsers);
        const nextSession = updateSessionWithUsers(session, nextUsers);
        setSession(nextSession);
        writeUsers(nextUsers);
        writeSession(nextSession);
        return toPublicUser(result.user);
      },
      createUser(input: UserUpsertInput) {
        const result = upsertUserRecord(users, { ...input, id: undefined }, session);
        const nextUsers = normalizeUsers(result.users);
        setUsers(nextUsers);
        const nextSession = updateSessionWithUsers(session, nextUsers);
        setSession(nextSession);
        writeUsers(nextUsers);
        writeSession(nextSession);
        return toPublicUser(result.user);
      },
      deleteUser(id: string) {
        const nextUsers = normalizeUsers(deleteUserRecord(users, id, session));
        setUsers(nextUsers);
        const nextSession = updateSessionWithUsers(session, nextUsers);
        setSession(nextSession);
        writeUsers(nextUsers);
        writeSession(nextSession);
      },
    }),
    [ready, session, users],
  );

  return api;
}
