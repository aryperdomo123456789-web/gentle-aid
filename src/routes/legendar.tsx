import { createFileRoute } from "@tanstack/react-router";
import { ChevronLeft } from "lucide-react";

import { CaptionStage } from "@/features/captions/components/CaptionStage";
import { EditorTimeline } from "@/features/captions/components/EditorTimeline";
import { StageToolbar } from "@/features/captions/components/StageToolbar";
import { StudioRail } from "@/features/captions/components/StudioRail";
import { StudioSidePanel } from "@/features/captions/components/StudioSidePanel";
import { StudioTopBar } from "@/features/captions/components/StudioTopBar";
import { useCaptionStudio } from "@/features/captions/use-caption-studio";

export const Route = createFileRoute("/legendar")({
  head: () => ({
    meta: [
      { title: "Estúdio de Legendas Virais — editor visual estilo Canva" },
      {
        name: "description",
        content:
          "Editor visual de legendas com painel lateral, palco com prévia ao vivo, linha do tempo por bloco e render final esterilizado no aaPanel.",
      },
      { property: "og:title", content: "Estúdio de Legendas Virais" },
      {
        property: "og:description",
        content:
          "Fluxo idêntico ao Canva: menu lateral de ferramentas, palco central, timeline embaixo e exportação legendada.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Legendar,
});

function Legendar() {
  const studio = useCaptionStudio();
  const { style, panel, card, clock } = studio;

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-background">
      <StudioTopBar studio={studio} />

      <div className="relative flex min-h-0 flex-1 flex-col md:flex-row">
        <StudioRail active={panel} onSelect={studio.setPanel} />

        <div className="relative flex min-h-0 flex-1 md:contents">
          {panel ? (
            <StudioSidePanel studio={studio} panel={panel} />
          ) : (
            <button
              type="button"
              onClick={() => studio.setPanel("estilos")}
              className="hidden w-4 shrink-0 items-center justify-center border-r border-border bg-card text-muted-foreground transition hover:text-foreground md:flex"
              aria-label="Abrir painel"
            >
              <ChevronLeft className="size-3 rotate-180" />
            </button>
          )}

          <div className="flex min-w-0 flex-1 flex-col">
            <StageToolbar studio={studio} />

            <div className="flex min-h-0 flex-1 items-center justify-center overflow-hidden bg-muted/30 p-3 sm:p-6">
              <CaptionStage
                className="flex h-full min-h-0 w-full items-center justify-center"
                src={studio.previewUrl}
                poster={card?.thumbnail ?? null}
                style={style}
                preset={studio.preset}
                transcript={studio.transcript}
                onYChange={(y) => studio.patch({ yPct: y })}
                onTick={studio.onTick}
                onReady={studio.onReady}
                onDetectAspect={studio.setDetected}
                hideControls
              />
            </div>

            <EditorTimeline
              duration={clock.duration}
              time={clock.time}
              playing={clock.playing}
              blocks={studio.blocks}
              uppercase={style.uppercase}
              sourceLabel={studio.sourceLabel}
              poster={card?.thumbnail ?? null}
              zoom={studio.zoom}
              onZoom={studio.setZoom}
              onSeek={(t) => studio.stageApi.current?.seek(t)}
              onToggle={() => studio.stageApi.current?.toggle()}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
