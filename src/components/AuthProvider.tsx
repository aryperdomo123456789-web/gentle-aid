import { createContext, useContext, type ReactNode } from "react";

import { useAuthState } from "@/lib/auth";

type AuthApi = ReturnType<typeof useAuthState>;

const AuthContext = createContext<AuthApi | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const auth = useAuthState();
  return <AuthContext.Provider value={auth}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth deve ser usado dentro de <AuthProvider>.");
  }
  return ctx;
}

export type { AuthSession } from "@/lib/auth";
