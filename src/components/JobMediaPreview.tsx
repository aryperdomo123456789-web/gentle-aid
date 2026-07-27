import { Download, ExternalLink, Play } from "lucide-react";

import { downloadUrl, type Job } from "@/lib/api";

type SourceCard = {
  title?: string;
  desc?: string;
  thumbnail?: string | null;
  platform?: string;
  author?: string;
  nickname?: string;
  views_label?: string;
  likes_label?: string;
  comments_label?: string;
  shares_label?: string;
  duration_label?: string;
  published_label?: string;
  url?: string;
};

function getSourceCard(job: Job): SourceCard | null {
  const raw = job.meta?.source_card;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  return raw as SourceCard;
}

function getPlayableUrl(job: Job): string | null {
  if (job.download_url) return downloadUrl(job.download_url);
  const first = job.outputs?.[0]?.download_url;
  return first ? downloadUrl(first) : null;
}

function getSourcePlayableUrl(job: Job): string | null {
  const source = getSourceCard(job);
  if (!source) return null;
  if (source.embed_url) return source.embed_url;
  return source.url ?? null;
}

function getOrientation(job: Job): "portrait" | "landscape" | "square" | "unknown" {
  return job.sterilization?.source_orientation ?? "unknown";
}

function previewAspectClass(orientation: ReturnType<typeof getOrientation>): string {
  void orientation;
  return "aspect-square";
}

function isVideoAsset(url: string): boolean {
  return /\.(mp4|webm|mkv|mov)(?:$|\?)/i.test(url);
}

export function JobMediaPreview({ job }: { job: Job }) {
  const playable = getPlayableUrl(job);
  const sourcePlayable = getSourcePlayableUrl(job);
  const source = getSourceCard(job);
  const orientation = getOrientation(job);
  const playableIsVideo = playable ? isVideoAsset(playable) : false;
  const sourceIsVideo = sourcePlayable ? isVideoAsset(sourcePlayable) : false;

  return (
    <div className="space-y-4">
      <div
        className={`mx-auto overflow-hidden rounded-2xl border border-border bg-black/90 ${previewAspectClass(orientation)}`}
        style={{
          width: "min(92vw, 32rem)",
          height: "min(92vw, 32rem)",
        }}
      >
        {playable ? (
          playableIsVideo ? (
            <video
              controls
              src={playable}
              className="h-full w-full bg-black object-contain"
              playsInline
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center p-6">
              <audio controls src={playable} className="w-full" />
            </div>
          )
        ) : sourcePlayable ? (
          sourceIsVideo ? (
            <video
              controls
              src={sourcePlayable}
              className="h-full w-full bg-black object-contain"
              playsInline
            />
          ) : (
            <iframe
              title={`Prévia da origem de ${source?.author ?? job.job_id}`}
              src={sourcePlayable}
              className="h-full w-full rounded-xl"
              allow="accelerometer; autoplay; encrypted-media; picture-in-picture"
              allowFullScreen
            />
          )
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            Prévia indisponível
          </div>
        )}
      </div>

      {source ? (
        <section className="rounded-2xl border border-border bg-background/50 p-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                Fonte original
              </p>
              <h3 className="mt-1 truncate text-base font-semibold">
                {source.title ?? job.filename ?? job.job_id}
              </h3>
              <p className="mt-1 text-sm text-muted-foreground">
                {source.desc ?? "Sem descrição."}
              </p>
              <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                <span className="rounded-full border border-border bg-background/60 px-2.5 py-1 text-muted-foreground">
                  {orientation === "unknown"
                    ? "orientação: não detectada"
                    : `orientação: ${orientation}`}
                </span>
                {job.sterilization?.source_width && job.sterilization?.source_height ? (
                  <span className="rounded-full border border-border bg-background/60 px-2.5 py-1 text-muted-foreground">
                    {job.sterilization.source_width}x{job.sterilization.source_height}
                  </span>
                ) : null}
              </div>
            </div>
            {source.thumbnail ? (
              <img
                src={source.thumbnail}
                alt={source.title ?? "Miniatura do vídeo"}
                className={`rounded-lg object-cover ${
                  orientation === "portrait"
                    ? "h-28 w-20"
                    : orientation === "square"
                      ? "h-24 w-24"
                      : "h-24 w-40"
                }`}
              />
            ) : null}
          </div>

          <div className="mt-4 grid gap-2 text-xs sm:grid-cols-2">
            <Meta label="Plataforma" value={source.platform} />
            <Meta label="Autor" value={source.author ?? source.nickname} />
            <Meta label="Visualizações" value={source.views_label} />
            <Meta label="Curtidas" value={source.likes_label} />
            <Meta label="Comentários" value={source.comments_label} />
            <Meta label="Compartilhamentos" value={source.shares_label} />
            <Meta label="Duração" value={source.duration_label} />
            <Meta label="Data" value={source.published_label} />
          </div>

          {source.url ? (
            <a
              href={source.url}
              target="_blank"
              rel="noreferrer"
              className="mt-4 inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-4 py-2 text-xs font-semibold hover:border-primary/50"
            >
              <ExternalLink className="size-3.5" aria-hidden="true" />
              Abrir origem
            </a>
          ) : null}
        </section>
      ) : null}

      {playable ? (
        <div className="flex flex-wrap gap-2">
          <a
            href={playable}
            download={job.filename ?? undefined}
            className="inline-flex items-center gap-2 rounded-full bg-success px-4 py-2 text-xs font-semibold text-success-foreground"
          >
            <Download className="size-3.5" aria-hidden="true" />
            Baixar resultado
          </a>
          <a
            href={playable}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-4 py-2 text-xs font-semibold hover:border-primary/50"
          >
            <Play className="size-3.5" aria-hidden="true" />
            Abrir player
          </a>
        </div>
      ) : sourcePlayable ? (
        <div className="flex flex-wrap gap-2">
          <a
            href={sourcePlayable}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-4 py-2 text-xs font-semibold hover:border-primary/50"
          >
            <Play className="size-3.5" aria-hidden="true" />
            Assistir origem
          </a>
        </div>
      ) : null}
    </div>
  );
}

function Meta({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div className="rounded-lg border border-border bg-background/60 px-3 py-2">
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <div className="truncate font-medium">{value}</div>
    </div>
  );
}
