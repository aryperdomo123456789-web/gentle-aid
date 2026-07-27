import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

import { Field, FileDrop, SelectInput, SubmitButton } from "@/components/form";
import { MutationSelect } from "@/components/MutationSelect";
import { StatusPanel } from "@/components/StatusPanel";
import { ToolHistory } from "@/components/ToolHistory";
import { ToolShell } from "@/components/ToolShell";
import { useJobRunner } from "@/hooks/use-job-runner";
import { apiPostForm, type Job } from "@/lib/api";

export const Route = createFileRoute("/voice-conversion")({
  head: () => ({
    meta: [
      { title: "Conversão de Voz V2V — troca de timbre com timing original" },
      {
        name: "description",
        content:
          "Envie um áudio local e converta o timbre da voz mantendo o timing e a prosódia original da fala.",
      },
      { property: "og:title", content: "Conversão de Voz V2V" },
      {
        property: "og:description",
        content: "Troca de timbre voice-to-voice preservando o timing original da fala.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: VoiceConversion,
});

function VoiceConversion() {
  const { job, error, busy, run } = useJobRunner();
  const [hasFile, setHasFile] = useState(false);

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    run(() => apiPostForm<Job>("/api/voice/convert", form));
  }

  return (
    <ToolShell
      badge="Ferramenta 4 · /api/voice/convert"
      title="Conversão de Voz V2V"
      subtitle="Upload de áudio local e conversão de timbre mantendo integralmente o timing da fala — sem re-sincronizar o vídeo."
      left={
        <form onSubmit={onSubmit} className="space-y-5">
          <Field label="Áudio de origem" hint="WAV, MP3 ou M4A — até 100 MB.">
            {(id) => (
              <FileDrop
                id={id}
                name="audio"
                accept="audio/wav,audio/mpeg,audio/mp4,audio/x-m4a"
                hint="WAV / MP3 / M4A"
                onSelect={(f) => setHasFile(Boolean(f))}
              />
            )}
          </Field>

          <Field label="Timbre alvo">
            {(id) => (
              <SelectInput id={id} name="target_voice" defaultValue="masc_grave">
                <option value="masc_grave">Masculino grave</option>
                <option value="masc_jovem">Masculino jovem</option>
                <option value="fem_suave">Feminino suave</option>
                <option value="fem_energetica">Feminino energética</option>
                <option value="narrador">Narrador documentário</option>
              </SelectInput>
            )}
          </Field>

          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Formato de saída">
              {(id) => (
                <SelectInput id={id} name="format" defaultValue="wav">
                  <option value="wav">WAV 48 kHz</option>
                  <option value="mp3">MP3 320 kbps</option>
                  <option value="aac">AAC 192 kbps</option>
                </SelectInput>
              )}
            </Field>
            <Field label="Preservar timing">
              {(id) => (
                <SelectInput id={id} name="preserve_timing" defaultValue="strict">
                  <option value="strict">Estrito — mesma duração exata</option>
                  <option value="natural">Natural — leve ajuste de prosódia</option>
                </SelectInput>
              )}
            </Field>
          </div>

          <MutationSelect
            defaultValue="leve"
            label="Esterilização do áudio"
            hint="Remove metadados/ID3 herdados, reescreve o timbre e entrega um arquivo de hash inédito."
          />



          <SubmitButton busy={busy} disabled={!hasFile}>
            {busy ? "Convertendo timbre…" : "Converter voz"}
          </SubmitButton>
        </form>
      }
      right={
        <StatusPanel
          job={job}
          error={error}
          busy={busy}
          emptyHint="Envie um áudio para iniciar a conversão de timbre."
        />
      }
      below={<ToolHistory tool="voice" title="Histórico · Voz V2V" refreshKey={`${job?.job_id ?? ""}-${job?.status ?? ""}`} />}
    />
  );
}
