import type { RadarVideo } from "../types";

/** Modal de player para pré-visualizar o viral antes de clonar. */
export function WatchDialog({
  video,
  onClose,
}: {
  video: RadarVideo | null;
  onClose: () => void;
}) {
  if (!video) return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Assistir ${video.title}`}
      className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-background/90 p-2 backdrop-blur-sm sm:p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-5xl overflow-hidden rounded-3xl border border-border bg-surface shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 border-b border-border px-3 py-3 sm:px-4">
          <div className="min-w-0">
            <p className="break-words text-sm font-semibold sm:truncate">{video.title}</p>
            <p className="break-words text-xs text-muted-foreground sm:truncate">
              @{video.author} · {video.views_human} visualizações · {video.source}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-border px-3 py-1.5 text-xs font-medium hover:bg-background/60"
          >
            Fechar
          </button>
        </div>
        <div className="bg-black">
          <div className="aspect-video w-full">
            <iframe
              src={video.embed_url ?? video.url}
              title={video.title}
              className="h-full w-full"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
              referrerPolicy="strict-origin-when-cross-origin"
              allowFullScreen
            />
          </div>
        </div>
      </div>
    </div>
  );
}
