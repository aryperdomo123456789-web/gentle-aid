import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

import { Field, FileDrop, SelectInput, SubmitButton } from "@/components/form";
import { MutationSelect } from "@/components/MutationSelect";
import { StatusPanel } from "@/components/StatusPanel";
import { ToolHistory } from "@/components/ToolHistory";
import { ToolShell } from "@/components/ToolShell";
import { useJobRunner } from "@/hooks/use-job-runner";
import { apiPostForm, type Job } from "@/lib/api";

export const Route = createFileRoute("/canva-cleaner")({
  head: () => ({
    meta: [
      { title: "Canva Cleaner — recodificação e limpeza pós-Canva" },
      {
        name: "description",
        content:
          "Remova metadados ISO/Canva, recodifique em H.264/AAC e gere um hash MD5 novo para vídeos exportados de editores online.",
      },
      { property: "og:title", content: "Canva Cleaner — limpeza pós-Canva" },
      {
        property: "og:description",
        content: "Esterilização de metadados e re-encode H.264/AAC para vídeos exportados do Canva.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: CanvaCleaner,
});

function CanvaCleaner() {
  const { job, error, busy, run } = useJobRunner();
  const [hasFile, setHasFile] = useState(false);

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
        <form onSubmit={onSubmit} className="space-y-5">
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

          <div className="grid gap-5 sm:grid-cols-2">
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
            <MutationSelect defaultValue="media" label="Nível de esterilização" hint="" />
          </div>

          <p className="rounded-xl border border-border bg-background/40 p-3 text-xs text-muted-foreground">
            A remoção total de metadados (ISO, encoder, Canva, GPS, XMP) é sempre aplicada e não pode
            ser desligada — o arquivo final recebe identidade forjada e hash inédito.
          </p>


          <SubmitButton busy={busy} disabled={!hasFile}>
            {busy ? "Limpando e recodificando…" : "Executar limpeza"}
          </SubmitButton>
        </form>
      }
      right={
        <StatusPanel
          job={job}
          error={error}
          busy={busy}
          emptyHint="Envie um vídeo para acompanhar a limpeza, o re-encode e os hashes MD5 antes/depois."
        />
      }
      below={<ToolHistory tool="canva" title="Histórico · Canva Cleaner" refreshKey={`${job?.job_id ?? ""}-${job?.status ?? ""}`} />}
    />
  );
}
