import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

import { DiscoveryPanel, type DiscoveryCard } from "@/components/DiscoveryPanel";
import { Field, SelectInput, SubmitButton, TextArea, TextInput } from "@/components/form";
import { MUTATION_LEVELS } from "@/components/MutationSelect";
import { StatusPanel } from "@/components/StatusPanel";
import { ToolHistory } from "@/components/ToolHistory";
import { ToolShell } from "@/components/ToolShell";
import { useJobRunner } from "@/hooks/use-job-runner";
import { apiPostJson, type Job } from "@/lib/api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Ecossistema Viral — Download e Bypass de YouTube" },
      {
        name: "description",
        content:
          "Baixe Shorts e vídeos longos do YouTube em lote, esterilize metadados e aplique mutação estrutural com FFmpeg para bypass de algoritmo.",
      },
      { property: "og:title", content: "Ecossistema Viral — Download e Bypass de YouTube" },
      {
        property: "og:description",
        content:
          "Download em lote, limpeza de metadados e mutação FFmpeg para TikTok, Reels e Shorts.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: YoutubeBypass,
});

const NICHOS = [
  "Motivacional",
  "Humor",
  "Finanças",
  "Fitness",
  "Curiosidades",
  "Gaming",
  "Notícias",
  "Outro",
];

function YoutubeBypass() {
  const { job, error, busy, run } = useJobRunner();
  const [links, setLinks] = useState("");
  const [nicho, setNicho] = useState(NICHOS[0]);
  const [keyword, setKeyword] = useState("");
  const [intensity, setIntensity] = useState("media");
  const [pickedUrl, setPickedUrl] = useState<string | null>(null);

  function processCard(card: DiscoveryCard) {
    setPickedUrl(card.url);
    run(() =>
      apiPostJson<Job>("/api/youtube/bypass", {
        urls: [card.url],
        nicho,
        keyword: keyword.trim() || card.title.slice(0, 60),
        intensity,
        source_card: card,
      }),
    );
  }

  const urls = links
    .split(/\s|,|;/)
    .map((l) => l.trim())
    .filter(Boolean);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (urls.length === 0) return;
    run(() =>
      apiPostJson<Job>("/api/youtube/bypass", {
        urls,
        nicho,
        keyword: keyword.trim(),
        intensity,
      }),
    );
  }

  return (
    <ToolShell
      badge="Ferramenta 1 · /api/youtube/bypass"
      title="Download e Bypass Universal de YouTube"
      subtitle="Cole links de Shorts ou vídeos longos, escolha o nicho e dispare o bypass em lote: download, re-encode H.264/AAC, remoção de metadados e micro-mutações temporais."
      left={
        <form onSubmit={onSubmit} className="space-y-5">
          <Field
            label="Links do YouTube"
            hint={`${urls.length} link(s) detectado(s). Um por linha, ou separados por vírgula.`}
          >
            {(id) => (
              <TextArea
                id={id}
                value={links}
                onChange={(e) => setLinks(e.target.value)}
                placeholder={"https://youtube.com/shorts/xxxx\nhttps://youtu.be/yyyy"}
                required
              />
            )}
          </Field>

          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Nicho">
              {(id) => (
                <SelectInput id={id} value={nicho} onChange={(e) => setNicho(e.target.value)}>
                  {NICHOS.map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </SelectInput>
              )}
            </Field>

            <Field label="Palavra-chave">
              {(id) => (
                <TextInput
                  id={id}
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  placeholder="ex.: renda extra"
                  maxLength={80}
                />
              )}
            </Field>
          </div>

          <Field
            label="Nível de esterilização"
            hint="Todo vídeo sai virgem (metadados destruídos + hash inédito). O nível controla a intensidade da mutação estrutural."
          >
            {(id) => (
              <SelectInput id={id} value={intensity} onChange={(e) => setIntensity(e.target.value)}>
                {MUTATION_LEVELS.map((level) => (
                  <option key={level.value} value={level.value}>
                    {level.label}
                  </option>
                ))}
              </SelectInput>
            )}
          </Field>

          <SubmitButton busy={busy}>
            {busy ? "Processando lote…" : "Disparar bypass em lote"}
          </SubmitButton>
        </form>
      }
      right={
        <StatusPanel
          job={job}
          error={error}
          busy={busy}
          emptyHint="Nenhum job em execução. Envie um lote para acompanhar o log do FFmpeg em tempo real."
        />
      }
      below={
        <div className="space-y-6">
          <DiscoveryPanel
            defaultPlatform="youtube"
            actionLabel="Baixar + esterilizar"
            onAction={processCard}
            actionBusyUrl={busy ? pickedUrl : null}
          />
          <ToolHistory
            tool="youtube"
            title="Histórico · YouTube Bypass"
            refreshKey={`${job?.job_id ?? ""}-${job?.status ?? ""}`}
          />
        </div>
      }
    />
  );
}
