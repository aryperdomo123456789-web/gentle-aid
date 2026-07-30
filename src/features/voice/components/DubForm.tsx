import type { ReactNode, RefObject } from "react";

import type { DiscoveryCard } from "@/components/DiscoveryPanel";
import { Field, FileDrop, SelectInput, TextInput } from "@/components/form";
import { JobSettingsGuard } from "@/components/JobSettingsGuard";

import { LinkInspector, type InspectedCard } from "@/components/LinkInspector";
import { MutationSelect } from "@/components/MutationSelect";
import { VideoFormatSelect } from "@/components/VideoFormatSelect";
import { AudioFormatField, MEDIA_ACCEPT, MEDIA_HINT } from "./AudioFormatField";

type Props = {
  formRef: RefObject<HTMLFormElement | null>;
  onSubmit: (e: React.FormEvent<HTMLFormElement>) => void;
  link: string;
  onLinkChange: (value: string) => void;
  onInspected: (card: InspectedCard | null) => void;
  onInspectorAction: (card: DiscoveryCard) => void;
  hasFile: boolean;
  onFileChange: (has: boolean) => void;
  busy: boolean;
  picker: ReactNode;
  dubReady: boolean;
  translateReady?: boolean;
  languages: Record<string, string>;

};

/** Aba "Dublagem IA": escuta o vídeo original e refaz a narração sincronizada. */
export function DubForm({
  formRef,
  onSubmit,
  link,
  onLinkChange,
  onInspected,
  onInspectorAction,
  hasFile,
  onFileChange,
  busy,
  picker,
  dubReady,
  translateReady = true,
  languages,
}: Props) {
  return (
    <form ref={formRef} onSubmit={onSubmit} className="space-y-5">
      {!dubReady ? (
        <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
          A dublagem precisa <strong>ouvir</strong> o vídeo. Cadastre a chave <strong>Groq</strong>{" "}
          (ou Whisper) em <code>/apis</code> para liberar a transcrição com timestamps.
        </p>
      ) : null}

      {dubReady && !translateReady ? (
        <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
          Sem chave de LLM cadastrada só dá para redublar no <strong>mesmo idioma</strong>. Cadastre
          DeepSeek, Groq, Mistral ou OpenRouter em <code>/apis</code> para traduzir para outro idioma.
        </p>
      ) : null}


      <Field
        label="Link do YouTube ou TikTok"
        hint="O servidor baixa o vídeo, escuta a narração e refaz o áudio com a sua voz — sincronizado no mesmo timing."
      >
        {(id) => (
          <TextInput
            id={id}
            name="url"
            inputMode="url"
            placeholder="https://www.youtube.com/watch?v=… ou https://www.tiktok.com/@perfil/video/…"
            value={link}
            onChange={(e) => onLinkChange(e.target.value)}
          />
        )}
      </Field>

      <LinkInspector
        url={link}
        onInspected={onInspected}
        actionLabel="Dublar este vídeo"
        actionBusy={busy}
        onAction={onInspectorAction}
      />

      <Field label="Ou envie o arquivo" hint="MP4 / MOV / MKV / WAV / MP3 / M4A — de 10 segundos a 3 horas.">
        {(id) => (
          <FileDrop
            id={id}
            name="media"
            accept={MEDIA_ACCEPT}
            hint={MEDIA_HINT}
            onSelect={(f) => onFileChange(Boolean(f))}
          />
        )}
      </Field>

      {picker}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-5">
        <Field label="Idioma da dublagem">
          {(id) => (
            <SelectInput id={id} name="target_lang" defaultValue="auto">
              {Object.entries(languages).map(([code, label]) => (
                <option key={code} value={code}>
                  {label}
                </option>
              ))}
            </SelectInput>
          )}
        </Field>
        <Field label="Áudio original ao fundo">
          {(id) => (
            <SelectInput id={id} name="keep_ambience" defaultValue="0.12">
              <option value="0">Remover — só a nova narração</option>
              <option value="0.12">Leve — música e ambiência discretas</option>
              <option value="0.3">Médio — mantém a trilha audível</option>
            </SelectInput>
          )}
        </Field>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-5">
        <Field label="Saída">
          {(id) => (
            <SelectInput id={id} name="keep_video" defaultValue="1">
              <option value="1">Vídeo dublado</option>
              <option value="0">Somente o áudio dublado</option>
            </SelectInput>
          )}
        </Field>
        <AudioFormatField />
      </div>

      <VideoFormatSelect hint="Só afeta a entrega em vídeo: escolha a proporção final da dublagem." />

      <MutationSelect
        defaultValue="auto"
        label="Esterilização"
        hint="O vídeo dublado sai virgem: sem metadados herdados e com hash inédito."
      />

      <JobSettingsGuard
        busy={busy}
        disabled={(!hasFile && link.trim().length < 8) || !dubReady}
        label="Dublar com a minha voz"
        busyLabel="Dublando com IA…"
      />

    </form>
  );
}
