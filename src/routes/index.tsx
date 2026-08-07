import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";

import { DiscoveryPanel, type DiscoveryCard } from "@/components/DiscoveryPanel";
import { Field, SelectInput, TextArea, TextInput } from "@/components/form";
import { JobSettingsGuard } from "@/components/JobSettingsGuard";

import { MUTATION_LEVELS } from "@/components/MutationSelect";
import { VideoFormatSelect } from "@/components/VideoFormatSelect";
import { StatusPanel } from "@/features/jobs/components/StatusPanel";
import { ToolHistory } from "@/features/jobs/components/ToolHistory";
import { ToolShell } from "@/components/ToolShell";
import { useJobRunner } from "@/hooks/use-job-runner";
import { apiPostJson, type Job } from "@/lib/api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Ecossistema Viral — Desvio e download do YouTube" },
      {
        name: "description",
        content:
          "Baixe Shorts e vídeos longos do YouTube em lote, esterilize metadados e aplique mutação estrutural com FFmpeg para bypass de algoritmo.",
      },
      { property: "og:title", content: "Ecossistema Viral — Desvio e download do YouTube" },
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
  const { job, error, busy, run, cancel, remove } = useJobRunner("youtube");
  const [links, setLinks] = useState("");
  const [nicho, setNicho] = useState(NICHOS[0]);
  const [keyword, setKeyword] = useState("");
  const [intensity, setIntensity] = useState("auto");
  const [videoFormat, setVideoFormat] = useState("original");
  const [formatFit, setFormatFit] = useState("cover");
  const [pickedUrl, setPickedUrl] = useState<string | null>(null);
  const [pickedCard, setPickedCard] = useState<DiscoveryCard | null>(null);

  /** Nada roda direto: o vídeo escolhido só entra na lista para conferência. */
  function processCard(card: DiscoveryCard) {
    setPickedUrl(card.url);
    setPickedCard(card);
    setLinks(card.url);
    if (!keyword.trim()) setKeyword(card.title.slice(0, 60));
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
        video_format: videoFormat,
        format_fit: formatFit,
        ...(pickedCard && urls.includes(pickedCard.url) ? { source_card: pickedCard } : {}),
      }),
    );
  }

  return (
    <ToolShell
      badge="Ferramenta 1 · /api/youtube/bypass"
      title="Download e desvio universal do YouTube"
      subtitle={
        <div className="space-y-4">
          <p>
            Cole links de Shorts ou vídeos longos, escolha o nicho e dispare o bypass em lote:
            download, re-encode H.264/AAC, remoção de metadados e micro-mutações temporais.
          </p>
          <Link
            to="/voice-conversion"
            className="group relative flex w-full flex-col overflow-hidden rounded-2xl border border-primary/30 bg-primary/5 p-4 transition-all hover:border-primary/60 hover:bg-primary/10"
          >
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-lg shadow-primary/20">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                  <line x1="12" x2="12" y1="19" y2="22" />
                </svg>
              </div>
              <div className="flex-1 min-w-0 text-left">
                <h4 className="text-sm font-bold text-foreground">Novo: Estúdio de Clonagem de Voz</h4>
                <p className="text-[11px] text-muted-foreground line-clamp-2">
                  Dúvida: "Consigo enviar áudio de 1 a 10 minutos para clonar?" Sim! Crie sua própria persona única e narre vídeos automaticamente com IA.
                </p>
              </div>
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-background/50 text-muted-foreground group-hover:bg-primary group-hover:text-primary-foreground">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M5 12h14" />
                  <path d="m12 5 7 7-7 7" />
                </svg>
              </div>
            </div>
          </Link>
        </div>
      }
      left={
        <form onSubmit={onSubmit} className="space-y-5">
          <Field
            label="Links do YouTube"
            hint={`${urls.length} link(s) detectado(s). Um por linha, ou separados por vírgula.`}
          >
            {(id) => (
              <TextArea
                id={id}
                name="urls"
                value={links}
                onChange={(e) => setLinks(e.target.value)}
                placeholder={"https://youtube.com/shorts/xxxx\nhttps://youtu.be/yyyy"}
                required
              />
            )}
          </Field>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-5">
            <Field label="Nicho">
              {(id) => (
                <SelectInput id={id} name="nicho" value={nicho} onChange={(e) => setNicho(e.target.value)}>
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
                  name="keyword"
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
              <SelectInput id={id} name="intensity" value={intensity} onChange={(e) => setIntensity(e.target.value)}>
                {MUTATION_LEVELS.map((level) => (
                  <option key={level.value} value={level.value}>
                    {level.label}
                  </option>
                ))}
              </SelectInput>
            )}
          </Field>

          <VideoFormatSelect
            value={videoFormat}
            onChange={setVideoFormat}
            fit={formatFit}
            onFitChange={setFormatFit}
            hint="Entregue no formato certo para cada rede: vertical para Shorts/Reels, horizontal para YouTube."
          />

          <JobSettingsGuard
            busy={busy}
            disabled={urls.length === 0}
            label="Disparar bypass em lote"
            busyLabel="Processando lote…"
          />

        </form>
      }
      right={
        <StatusPanel
          job={job}
          error={error}
          busy={busy}
          emptyHint="Nenhum job em execução. Envie um lote para acompanhar o log do FFmpeg em tempo real."
          onCancel={cancel}
          onDelete={remove}
        />
      }
      below={
        <div className="space-y-6">
          <DiscoveryPanel
            defaultPlatform="youtube"
            actionLabel="Usar este vídeo"
            onAction={processCard}
            actionBusyUrl={busy ? pickedUrl : null}
          />
          <ToolHistory
            tool="youtube"
            title="Histórico · Desvio YouTube"
            refreshKey={`${job?.job_id ?? ""}-${job?.status ?? ""}`}
          />
        </div>
      }
    />
  );
}
