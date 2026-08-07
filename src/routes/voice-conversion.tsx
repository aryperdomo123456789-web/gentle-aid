import { createFileRoute } from "@tanstack/react-router";

import { DiscoveryPanel } from "@/components/DiscoveryPanel";
import { ToolShell } from "@/components/ToolShell";
import { VoiceForgePanel } from "@/components/VoiceForgePanel";
import { VoicePicker } from "@/components/VoicePicker";
import { StatusPanel } from "@/features/jobs/components/StatusPanel";
import { ToolHistory } from "@/features/jobs/components/ToolHistory";
import { DubForm } from "@/features/voice/components/DubForm";
import { MediaConvertForm } from "@/features/voice/components/MediaConvertForm";
import { TextToSpeechForm } from "@/features/voice/components/TextToSpeechForm";
import { VoiceModeTabs } from "@/features/voice/components/VoiceModeTabs";
import { VOICE_ENDPOINT } from "@/features/voice/api";
import { useVoiceStudio } from "@/features/voice/use-voice-studio";

export const Route = createFileRoute("/voice-conversion")({
  head: () => ({
    meta: [
      { title: "Estúdio de Voz — troca de narrador e narração realista" },
      {
        name: "description",
        content:
          "Troque a voz do narrador de vídeos e áudios de 10 segundos a 3 horas sem mudar a narrativa, ou transforme texto em narração realista.",
      },
      { property: "og:title", content: "Estúdio de Voz" },
      {
        property: "og:description",
        content:
          "Speech-to-speech e text-to-speech com vozes realistas, timing preservado e áudio esterilizado.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: VoiceStudio,
});

function VoiceStudio() {
  const studio = useVoiceStudio();
  const { job, error, busy, mode, voices, personas, elevenReady, forgeReady, testScript } = studio;

  const mediaPicker = (
    <VoicePicker
      value={studio.mediaVoice}
      onChange={studio.setMediaVoice}
      realisticVoices={voices}
      personas={personas}
      localVoices={studio.catalog?.local_voices}
      elevenReady={elevenReady}
      forgeReady={forgeReady}
      allowLocal
      testScript={testScript}
      onSyncPersonas={studio.syncPersonas}
    />
  );

  const dubPicker = (
    <VoicePicker
      value={studio.dubVoice}
      onChange={studio.setDubVoice}
      realisticVoices={voices}
      personas={personas}
      elevenReady={elevenReady}
      forgeReady={forgeReady}
      allowLocal={false}
      testScript={testScript}
      onSyncPersonas={studio.syncPersonas}
    />
  );

  const ttsPicker = (
    <VoicePicker
      value={studio.ttsVoice}
      onChange={studio.setTtsVoice}
      realisticVoices={voices}
      personas={personas}
      elevenReady={elevenReady}
      forgeReady={forgeReady}
      allowLocal={false}
      testScript={testScript}
      onSyncPersonas={studio.syncPersonas}
    />
  );

  return (
    <ToolShell
      badge="Ferramenta 4 · Estúdio de Voz"
      title="Estúdio de Clonagem e Conversão de Voz"
      subtitle="Sim, o sistema clona sua voz! Envie um áudio de 1 a 10 minutos para criar um perfil personalizado, ou use links do YouTube/TikTok e roteiros para gerar narrações realistas com a sua persona única."
      left={
        <div className="space-y-5">
          <VoiceModeTabs mode={mode} onChange={studio.setMode} />

          {!elevenReady && mode !== "forge" ? (
            <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
              Chave ElevenLabs ausente. Cadastre o provedor <strong>ElevenLabs</strong> em{" "}
              <code>/apis</code> para liberar as vozes realistas. Enquanto isso, use a aba{" "}
              <strong>Criar voz</strong> — o Voice Forge gera uma voz exclusiva sua sem nenhum
              custo.
            </p>
          ) : null}

          {mode === "forge" ? (
            <VoiceForgePanel onChanged={studio.setPersonas} />
          ) : mode === "media" ? (
            <MediaConvertForm
              formRef={studio.mediaForm}
              onSubmit={studio.submit(VOICE_ENDPOINT.convert)}
              link={studio.mediaLink}
              onLinkChange={studio.setMediaLink}
              onInspected={studio.setMediaCard}
              onInspectorAction={studio.processCard}
              hasFile={studio.hasFile}
              onFileChange={studio.setHasFile}
              busy={busy}
              picker={mediaPicker}
            />
          ) : mode === "dub" ? (
            <DubForm
              formRef={studio.dubForm}
              onSubmit={studio.submit(VOICE_ENDPOINT.dub)}
              link={studio.dubLink}
              onLinkChange={studio.setDubLink}
              onInspected={studio.setDubCard}
              onInspectorAction={studio.processCard}
              hasFile={studio.dubFile}
              onFileChange={studio.setDubFile}
              busy={busy}
              picker={dubPicker}
              dubReady={studio.dubReady}
              translateReady={studio.dubTranslateReady}
              languages={studio.dubLanguages}

            />
          ) : mode === "text" ? (
            <TextToSpeechForm
              onSubmit={studio.submit(VOICE_ENDPOINT.tts)}
              maxChars={studio.maxChars}
              busy={busy}
              disabled={studio.ttsVoice.engine === "elevenlabs" ? !elevenReady : !forgeReady}
              picker={ttsPicker}
            />
          ) : null}
        </div>
      }
      right={
        <StatusPanel
          job={job}
          error={error}
          busy={busy}
          emptyHint="Cole o link do YouTube/TikTok, envie um arquivo ou escreva um roteiro para começar."
          onCancel={studio.cancel}
          onDelete={studio.remove}
        />
      }
      below={
        <div className="space-y-6">
          <DiscoveryPanel
            defaultPlatform="auto"
            actionLabel={mode === "dub" ? "Dublar este vídeo" : "Trocar a voz deste vídeo"}
            onAction={studio.processCard}
            actionBusyUrl={busy ? studio.pickedUrl : null}
          />
          <ToolHistory
            tool="voice"
            title="Histórico · Estúdio de Voz"
            refreshKey={`${job?.job_id ?? ""}-${job?.status ?? ""}`}
          />
        </div>
      }
    />
  );
}
