import { KeyRound, LockKeyhole, PencilLine, Search, Shield, Trash2, Users } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";

import { Field, SubmitButton, TextInput } from "@/components/form";
import type { ManagedUser } from "@/lib/auth";
import { useAuth } from "@/components/AuthProvider";

export function AccountConsole({ onLogout }: { onLogout: () => void }) {
  const auth = useAuth();
  const [selectedId, setSelectedId] = useState(auth.user?.id ?? "");
  const [query, setQuery] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const filteredUsers = useMemo(() => {
    const term = query.trim().toLowerCase();
    return auth.users.filter((user) => {
      if (!term) return true;
      return (
        user.name.toLowerCase().includes(term) ||
        user.email.toLowerCase().includes(term) ||
        user.id.toLowerCase().includes(term)
      );
    });
  }, [auth.users, query]);

  const selectedUser =
    auth.users.find((user) => user.id === selectedId) ?? auth.user ?? auth.users[0] ?? null;

  useEffect(() => {
    if (!selectedUser) return;
    setSelectedId(selectedUser.id);
    setName(selectedUser.name);
    setEmail(selectedUser.email);
    setPassword("");
    setConfirm("");
    setNotice(null);
  }, [selectedUser]);

  async function handleSave(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selectedUser) return;
    if (password || confirm) {
      if (password.length < 6) {
        setNotice("A nova senha precisa ter pelo menos 6 caracteres.");
        return;
      }
      if (password !== confirm) {
        setNotice("As senhas não conferem.");
        return;
      }
    }

    setBusy(true);
    setNotice(null);
    try {
      auth.updateUser({
        id: selectedUser.id,
        name: name.trim() || selectedUser.name,
        email: email.trim() || selectedUser.email,
        ...(password ? { password } : {}),
      });
      setPassword("");
      setConfirm("");
      setNotice("Credenciais atualizadas com sucesso.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Falha ao atualizar credenciais.");
    } finally {
      setBusy(false);
    }
  }

  function handleDelete(user: ManagedUser) {
    const ok = window.confirm(
      `Tem certeza que quer apagar "${user.name}" (${user.email})? Essa ação remove a conta do painel.`,
    );
    if (!ok) return;
    try {
      auth.deleteUser(user.id);
      setNotice("Usuário removido.");
      setSelectedId(auth.user?.id ?? "");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Falha ao remover usuário.");
    }
  }

  return (
    <section className="grid w-full gap-6 lg:grid-cols-[1.02fr_0.98fr]">
      <div className="panel space-y-6 px-6 py-7 md:px-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <span className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-medium">
              <Shield className="size-3.5" />
              Sessão ativa
            </span>
            <h1 className="mt-4 text-3xl font-bold tracking-tight text-foreground">
              {auth.isOwner ? "Console do dono" : "Minha conta"}
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
              Aqui você troca usuário e senha da conta ativa. Se for dono, também pode filtrar e
              gerenciar todas as contas cadastradas.
            </p>
          </div>

          <button
            type="button"
            onClick={onLogout}
            className="inline-flex items-center gap-2 rounded-full border border-destructive/40 bg-destructive/10 px-4 py-2 text-sm font-semibold text-destructive transition-colors hover:border-destructive/70 hover:bg-destructive/15"
          >
            <KeyRound className="size-4" aria-hidden="true" />
            Sair
          </button>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <SummaryTile label="Usuário ativo" value={auth.user?.email ?? "-"} />
          <SummaryTile label="Perfil" value={auth.user?.role === "owner" ? "Dono" : "Usuário"} />
          <SummaryTile
            label="Último login"
            value={auth.session?.loginAt ? formatDate(auth.session.loginAt) : "agora"}
          />
        </div>

        <form
          onSubmit={handleSave}
          className="space-y-4 rounded-3xl border border-border/80 bg-surface/70 p-5"
        >
          <div className="flex items-center gap-3">
            <span className="flex size-11 items-center justify-center rounded-2xl bg-primary/15 text-primary">
              <PencilLine className="size-5" aria-hidden="true" />
            </span>
            <div>
              <p className="text-sm font-semibold text-foreground">Editar credenciais</p>
              <p className="text-xs text-muted-foreground">
                {selectedUser?.protected
                  ? "Conta protegida do dono original. Email travado, senha editável."
                  : "Troque nome, email e senha do usuário selecionado."}
              </p>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Nome">
              {(id) => (
                <TextInput
                  id={id}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Nome de exibição"
                />
              )}
            </Field>

            <Field label="Email">
              {(id) => (
                <TextInput
                  id={id}
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="usuario@viral.site"
                  disabled={Boolean(selectedUser?.protected)}
                />
              )}
            </Field>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Nova senha">
              {(id) => (
                <TextInput
                  id={id}
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Deixe em branco para manter"
                  autoComplete="new-password"
                />
              )}
            </Field>

            <Field label="Confirmar senha">
              {(id) => (
                <TextInput
                  id={id}
                  type="password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  placeholder="Repita a nova senha"
                  autoComplete="new-password"
                />
              )}
            </Field>
          </div>

          {notice ? (
            <p className="rounded-xl border border-border bg-background/60 p-3 text-sm text-foreground">
              {notice}
            </p>
          ) : null}

          <SubmitButton busy={busy}>{busy ? "Salvando…" : "Salvar credenciais"}</SubmitButton>
        </form>

        <div className="rounded-3xl border border-border/80 bg-background/50 p-5">
          <div className="flex items-center gap-3">
            <span className="flex size-11 items-center justify-center rounded-2xl bg-electric/15 text-electric">
              <LockKeyhole className="size-5" aria-hidden="true" />
            </span>
            <div>
              <p className="text-sm font-semibold text-foreground">Status do acesso</p>
              <p className="text-xs text-muted-foreground">
                {selectedUser?.role === "owner"
                  ? "O dono pode ver e editar todos os usuários."
                  : "A conta atual só enxerga e edita o próprio acesso."}
              </p>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Chip>Usuários cadastrados: {auth.users.length}</Chip>
            <Chip>Conta ativa: {selectedUser?.name ?? "-"}</Chip>
            <Chip>ID: {selectedUser?.id ?? "-"}</Chip>
          </div>
        </div>
      </div>

      <div className="panel space-y-5 px-6 py-7 md:px-8">
        <div className="flex items-center justify-between gap-3">
          <div>
            <span className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-medium">
              <Users className="size-3.5" />
              Diretório de usuários
            </span>
            <h2 className="mt-4 text-2xl font-bold tracking-tight text-foreground">
              {auth.isOwner ? "Filtrar e editar contas" : "Conta atual"}
            </h2>
          </div>

          {auth.isOwner ? (
            <div className="min-w-[220px]">
              <Field label="Buscar">
                {(id) => (
                  <TextInput
                    id={id}
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="nome, email ou ID"
                  />
                )}
              </Field>
            </div>
          ) : null}
        </div>

        {auth.isOwner ? (
          <div className="space-y-3">
            {filteredUsers.map((user) => (
              <div
                key={user.id}
                className={`w-full rounded-2xl border px-4 py-4 text-left transition-colors ${
                  selectedId === user.id
                    ? "border-primary/60 bg-primary/10"
                    : "border-border/80 bg-background/40 hover:border-primary/30"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-semibold text-foreground">{user.name}</p>
                      <Tag tone={user.role === "owner" ? "owner" : "common"}>
                        {user.role === "owner" ? "Dono" : "Usuário"}
                      </Tag>
                      {user.protected ? <Tag tone="protected">Protegido</Tag> : null}
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">{user.email}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      ID {user.id} · criado {formatDate(user.createdAt)} · último login{" "}
                      {user.lastLoginAt ? formatDate(user.lastLoginAt) : "nunca"}
                    </p>
                  </div>

                  <span className="inline-flex items-center gap-1 rounded-full border border-border bg-background/60 px-3 py-1 text-xs text-muted-foreground">
                    <Search className="size-3.5" aria-hidden="true" />
                    {selectedId === user.id ? "Selecionado" : "Visualizar"}
                  </span>
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="inline-flex items-center gap-2 rounded-full border border-border bg-background/60 px-3 py-1.5 text-xs font-medium text-foreground hover:border-primary/40"
                    onClick={() => setSelectedId(user.id)}
                  >
                    <PencilLine className="size-3.5" aria-hidden="true" />
                    Abrir no formulário
                  </button>
                  <button
                    type="button"
                    className="inline-flex items-center gap-2 rounded-full border border-destructive/40 bg-destructive/10 px-3 py-1.5 text-xs font-medium text-destructive hover:border-destructive/70"
                    onClick={() => handleDelete(user)}
                    disabled={Boolean(user.protected)}
                    title={user.protected ? "Conta protegida" : "Apagar usuário"}
                  >
                    <Trash2 className="size-3.5" aria-hidden="true" />
                    Apagar
                  </button>
                </div>
              </div>
            ))}

            {filteredUsers.length === 0 ? (
              <div className="rounded-2xl border border-border bg-background/50 p-5 text-sm text-muted-foreground">
                Nenhum usuário encontrado com esse filtro.
              </div>
            ) : null}
          </div>
        ) : (
          <div className="rounded-3xl border border-border/80 bg-background/50 p-5">
            <div className="flex items-center gap-3">
              <span className="flex size-11 items-center justify-center rounded-2xl bg-electric/15 text-electric">
                <Shield className="size-5" aria-hidden="true" />
              </span>
              <div>
                <p className="text-sm font-semibold text-foreground">Conta individual ativa</p>
                <p className="text-xs text-muted-foreground">
                  Aqui só aparece o seu acesso. Se você precisar do filtro geral, entre como dono.
                </p>
              </div>
            </div>
            <div className="mt-4 grid gap-2 text-sm text-muted-foreground">
              <p>
                Nome: <span className="font-mono text-foreground">{selectedUser?.name ?? "-"}</span>
              </p>
              <p>
                Email:{" "}
                <span className="font-mono text-foreground">{selectedUser?.email ?? "-"}</span>
              </p>
              <p>
                ID: <span className="font-mono text-foreground">{selectedUser?.id ?? "-"}</span>
              </p>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function SummaryTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-3xl border border-border/80 bg-background/50 p-4">
      <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">{label}</p>
      <p className="mt-2 break-words text-sm font-semibold text-foreground">{value}</p>
    </div>
  );
}

function Chip({ children }: { children: string }) {
  return (
    <span className="inline-flex items-center rounded-full border border-border bg-background/60 px-3 py-1.5 text-xs text-muted-foreground">
      {children}
    </span>
  );
}

function Tag({ tone, children }: { tone: "owner" | "common" | "protected"; children: string }) {
  const styles: Record<"owner" | "common" | "protected", string> = {
    owner: "border-primary/30 bg-primary/10 text-primary",
    common: "border-border bg-background/60 text-muted-foreground",
    protected: "border-success/30 bg-success/10 text-success",
  };

  return (
    <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] ${styles[tone]}`}>
      {children}
    </span>
  );
}

function formatDate(value?: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}
