import { createFileRoute } from "@tanstack/react-router";

import { StatusPanel } from "@/features/jobs/components/StatusPanel";
import { ToolHistory } from "@/features/jobs/components/ToolHistory";
import { ToolShell } from "@/components/ToolShell";
import { Field, TextInput, SubmitButton } from "@/components/form";
import { useJobRunner } from "@/hooks/use-job-runner";
import { apiPostForm, type Job } from "@/lib/api";
import { useState } from "react";

export const Route = createFileRoute("/transcrever")({
  head: () => ({
    meta: [
      { title: "Transcrição de Vídeo — URL para texto" },
      {
        name: "description",
        content:
          "Cole um link de vídeo público e extraia a fala em texto pronto para copiar ou baixar em .txt.",
      },
      { property: "og:title", content: "Transcrição de Vídeo" },
      {
        property: "og:description",
        content: "Ferramenta de vídeo para texto usando o motor de transcrição já existente no servidor.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: TranscreverPage,
});

function TranscreverPage() {
  const { job, error, busy, run, cancel, remove } = useJobRunner("transcribe");
  const [url, setUrl] = useState("https://www.youtube.com/watch?v=lWEi1Mkdidw");

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    run(() => apiPostForm<Job>("/api/transcribe/run", form));
  }

  return (
    <ToolShell
      badge="Ferramenta 8 · /api/transcribe/run"
      title="Transcrição de Vídeo"
      subtitle="Cole o link de um vídeo público e gere a fala em texto, com arquivo .txt baixável ao final."
      left={
        <form onSubmit={onSubmit} className="space-y-5">
          <Field label="Link do vídeo" hint="YouTube ou outro link público de vídeo.">
            {(id) => (
              <TextInput
                id={id}
                name="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://www.youtube.com/watch?v=lWEi1Mkdidw"
                inputMode="url"
                required
              />
            )}
          </Field>

          <SubmitButton busy={busy}>Transcrever vídeo</SubmitButton>
        </form>
      }
      right={
        <StatusPanel
          job={job}
          error={error}
          busy={busy}
          emptyHint="Cole um link de vídeo e envie para acompanhar a transcrição em tempo real."
          onCancel={cancel}
          onDelete={remove}
        />
      }
      below={
        <ToolHistory
          tool="transcribe"
          title="Histórico · Transcrição"
          refreshKey={`${job?.job_id ?? ""}-${job?.status ?? ""}`}
        />
      }
    />
  );
}
