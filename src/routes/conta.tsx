import { createFileRoute } from "@tanstack/react-router";
import { useNavigate } from "@tanstack/react-router";

import { AccountConsole } from "@/components/AccountConsole";
import { useAuth } from "@/components/AuthProvider";
import { TopNav } from "@/components/TopNav";

export const Route = createFileRoute("/conta")({
  head: () => ({
    meta: [
      { title: "Minha conta — Ecossistema Viral" },
      {
        name: "description",
        content: "Painel de credenciais e usuários do Ecossistema Viral.",
      },
    ],
  }),
  component: AccountPage,
});

function AccountPage() {
  const auth = useAuth();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen">
      <TopNav />
      <main className="mx-auto w-full max-w-[1600px] px-4 py-8 md:px-8">
        <AccountConsole
          onLogout={() => {
            auth.logout();
            void navigate({ to: "/login", replace: true });
          }}
        />
      </main>
    </div>
  );
}
