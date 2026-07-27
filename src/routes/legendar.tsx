import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

import { Field, FileDrop, SelectInput, SubmitButton, TextArea } from "@/components/form";
import { MutationSelect } from "@/components/MutationSelect";
import { StatusPanel } from "@/components/StatusPanel";
import { ToolShell } from "@/components/ToolShell";
import { useJobRunner } from "@/hooks/use-job-runner";
import { apiPostForm, type Job } from "@/lib/api";

export const Route = createFileRoute("/legendar")({
  head: () => ({
    meta: [
      { title: "Legendar Vídeos — legendas dinâmicas estilizadas" },
      {
        name: "description",
        content:
          "Queime legendas dinâmicas e estilizadas em vídeos verticais com FFmpeg: presets de estilo, posição e transcrição automática.",
      },
      { property: "og:title", content: "Legendar Vídeos — legendas dinâmicas" },
      {
        property: "og:description",
        content: "Legendas queimadas com presets virais para Reels, Shorts e TikTok.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Legendar,
});

function Legendar() {
  const { job, error, busy, run } = useJobRunner();
  const [hasFile, setHasFile] = useState(false);

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    run(() => apiPostForm<Job>("/api/legendar/run", form));
  }

  return (
    <ToolShell
      badge="Ferramenta 3 · /api/legendar/run"
      title="Legendar Vídeos"
      subtitle="Aplique legendas dinâmicas e estilizadas nos vídeos gerados pelo ecossistema. As legendas são queimadas no stream de vídeo via filtro subtitles do FFmpeg."
      left={
        <form onSubmit={onSubmit} className="space-y-5">
          <Field label="Vídeo de entrada" hint="MP4, MOV ou MKV — até 500 MB.">
            {(id) => (
              <FileDrop
                id={id}
                name="video"
                accept="video/mp4,video/quicktime,video/x-matroska"
                hint="MP4 / MOV / MKV"
                onSelect={(f) => setHasFile(Boolean(f))}
              />
            )}
          </Field>

          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Estilo">
              {(id) => (
                <SelectInput id={id} name="style" defaultValue="viral">
                  <option value="viral">Viral — caixa alta, contorno grosso</option>
                  <option value="karaoke">Karaokê — destaque palavra a palavra</option>
                  <option value="clean">Clean — sans branca discreta</option>
                  <option value="neon">Neon — roxo com glow</option>
                </SelectInput>
              )}
            </Field>
            <Field label="Posição">
              {(id) => (
                <SelectInput id={id} name="position" defaultValue="center">
                  <option value="bottom">Inferior</option>
                  <option value="center">Centro</option>
                  <option value="top">Superior</option>
                </SelectInput>
              )}
            </Field>
          </div>

          <Field
            label="Transcrição (opcional)"
            hint="Deixe vazio para transcrição automática no servidor. Aceita texto simples ou SRT."
          >
            {(id) => <TextArea id={id} name="srt" placeholder="1\n00:00:00,000 --> 00:00:02,000\nSeu texto" />}
          </Field>

          <SubmitButton busy={busy} disabled={!hasFile}>
            {busy ? "Renderizando legendas…" : "Gerar vídeo legendado"}
          </SubmitButton>
        </form>
      }
      right={
        <StatusPanel
          job={job}
          error={error}
          busy={busy}
          emptyHint="Envie um vídeo para acompanhar a renderização das legendas."
        />
      }
    />
  );
}
