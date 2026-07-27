import { createFileRoute } from "@tanstack/react-router";

import { AccountConsole } from "@/components/AccountConsole";
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
  return (
    <div className="min-h-screen">
      <TopNav />
      <main className="mx-auto w-full max-w-[1600px] px-4 py-8 md:px-8">
        <AccountConsole />
      </main>
    </div>
  );
}
