import { createFileRoute } from "@tanstack/react-router";
import { useRef, useState } from "react";

import { DiscoveryPanel, type DiscoveryCard } from "@/components/DiscoveryPanel";
import { Field, FileDrop, SelectInput } from "@/components/form";
import { JobSettingsGuard } from "@/components/JobSettingsGuard";

import { MutationSelect } from "@/components/MutationSelect";
import { StatusPanel } from "@/features/jobs/components/StatusPanel";
import { ToolHistory } from "@/features/jobs/components/ToolHistory";
import { ToolShell } from "@/components/ToolShell";
import { useJobRunner } from "@/hooks/use-job-runner";
import { apiPostForm, type Job } from "@/lib/api";

export const Route = createFileRoute("/canva-cleaner")({
  head: () => ({
    meta: [
      { title: "Limpeza Canva — recodificação e limpeza pós-Canva" },
      {
        name: "description",
        content:
          "Remova metadados ISO/Canva, recodifique em H.264/AAC e gere um hash MD5 novo para vídeos exportados de editores online.",
      },
      { property: "og:title", content: "Limpeza Canva — limpeza pós-Canva" },
      {
        property: "og:description",
        content:
          "Esterilização de metadados e re-encode H.264/AAC para vídeos exportados do Canva.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: CanvaCleaner,
});

function CanvaCleaner() {
  const { job, error, busy, run, cancel, remove } = useJobRunner("canva");
  const [hasFile, setHasFile] = useState(false);
  const [pickedUrl, setPickedUrl] = useState<string | null>(null);
  const [card, setCard] = useState<DiscoveryCard | null>(null);
  const formRef = useRef<HTMLFormElement>(null);

  /** Nada roda direto: o vídeo da pesquisa entra no formulário para conferência. */
  function processCard(next: DiscoveryCard) {
    setCard(next);
    setPickedUrl(next.url);
  }

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    run(() => apiPostForm<Job>("/api/canva-cleaner/run", form));
  }

  return (
    <ToolShell
      badge="Ferramenta 5 · /api/canva-cleaner/run"
      title="Recodificação e Limpeza Pós-Canva"
      subtitle="Envie o vídeo exportado do Canva ou de outro editor: o pipeline remove os metadados ISO/Canva, recodifica em H.264/AAC, altera bitrate e aplica micro-mutações temporais gerando um hash MD5 inédito."
      left={
        <form ref={formRef} onSubmit={onSubmit} className="space-y-5">
          {card ? (
            <div className="rounded-xl border border-primary/40 bg-primary/5 p-3 text-xs">
              <p className="font-medium text-foreground">Vídeo da pesquisa selecionado</p>
              <p className="mt-1 truncate text-muted-foreground">{card.title}</p>
              <input type="hidden" name="url" value={card.url} />
              <input type="hidden" name="source_card" value={JSON.stringify(card)} />
              <button
                type="button"
                onClick={() => {
                  setCard(null);
                  setPickedUrl(null);
                }}
                className="mt-2 rounded-lg border border-border px-3 py-1 text-[11px] text-muted-foreground transition hover:text-foreground"
              >
                Remover seleção
              </button>
            </div>
          ) : null}

          <Field label="Vídeo exportado" hint="MP4, MOV ou WEBM — até 500 MB.">
            {(id) => (
              <FileDrop
                id={id}
                name="video"
                accept="video/mp4,video/quicktime,video/webm"
                hint="MP4 / MOV / WEBM"
                onSelect={(f) => setHasFile(Boolean(f))}
              />
            )}
          </Field>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-5">
            <Field label="Perfil de bitrate">
              {(id) => (
                <SelectInput id={id} name="bitrate" defaultValue="auto">
                  <option value="auto">Auto — ±12% aleatório</option>
                  <option value="4000k">4000 kbps</option>
                  <option value="6000k">6000 kbps</option>
                  <option value="8000k">8000 kbps</option>
                </SelectInput>
              )}
            </Field>
            <MutationSelect defaultValue="auto" label="Nível de esterilização" hint="" />
          </div>

          <p className="rounded-xl border border-border bg-background/40 p-3 text-xs text-muted-foreground">
            A remoção total de metadados (ISO, encoder, Canva, GPS, XMP) é sempre aplicada e não
            pode ser desligada — o arquivo final recebe identidade forjada e hash inédito.
          </p>
          <JobSettingsGuard
            busy={busy}
            disabled={!hasFile && !card}
            label="Executar limpeza"
            busyLabel="Limpando e recodificando…"
          />

        </form>
      }
      right={
        <StatusPanel
          job={job}
          error={error}
          busy={busy}
          emptyHint="Envie um vídeo para acompanhar a limpeza, o re-encode e os hashes MD5 antes/depois."
          onCancel={cancel}
          onDelete={remove}
        />
      }
      below={
        <div className="space-y-6">
          <DiscoveryPanel
            defaultPlatform="auto"
            actionLabel="Usar este vídeo"
            onAction={processCard}
            actionBusyUrl={busy ? pickedUrl : null}
          />
          <ToolHistory
            tool="canva"
            title="Histórico · Limpeza Canva"
            refreshKey={`${job?.job_id ?? ""}-${job?.status ?? ""}`}
          />
        </div>
      }
    />
  );
}
