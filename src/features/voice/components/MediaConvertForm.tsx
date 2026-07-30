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
};

/** Aba "Trocar timbre": upload ou link, mantendo a narrativa original. */
export function MediaConvertForm({
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
}: Props) {
  return (
    <form ref={formRef} onSubmit={onSubmit} className="space-y-5">
      <Field
        label="Vídeo ou áudio de origem"
        hint="MP4, MOV, MKV, WAV, MP3 ou M4A — arquivos longos são fatiados automaticamente."
      >
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

      <Field
        label="Ou cole o link do YouTube / TikTok"
        hint="O vídeo é baixado no servidor e processado direto — sem precisar do arquivo."
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
        actionLabel="Trocar a voz deste vídeo"
        actionBusy={busy}
        onAction={onInspectorAction}
      />

      {picker}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-5">
        <Field label="Saída quando for vídeo">
          {(id) => (
            <SelectInput id={id} name="keep_video" defaultValue="1">
              <option value="1">Vídeo com a nova narração</option>
              <option value="0">Somente o áudio convertido</option>
            </SelectInput>
          )}
        </Field>
        <AudioFormatField />
      </div>

      <Field label="Preservar timing">
        {(id) => (
          <SelectInput id={id} name="preserve_timing" defaultValue="strict">
            <option value="strict">
              Estrito — mesma duração exata (sincroniza com o vídeo)
            </option>
            <option value="natural">Natural — deixa a prosódia respirar</option>
          </SelectInput>
        )}
      </Field>

      <VideoFormatSelect hint="Válido quando a saída mantém o vídeo — define a proporção final." />

      <MutationSelect
        defaultValue="auto"
        label="Esterilização"
        hint="Remove metadados/ID3 herdados e entrega um arquivo de hash inédito."
      />

      <JobSettingsGuard
        busy={busy}
        disabled={!hasFile && link.trim().length < 8}
        label="Trocar a voz do narrador"
        busyLabel="Trocando o narrador…"
      />

    </form>
  );
}
