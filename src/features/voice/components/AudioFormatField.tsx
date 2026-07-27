import { Field, SelectInput } from "@/components/form";

/** Aceite de mídia compartilhado pelas abas que recebem arquivo. */
export const MEDIA_ACCEPT =
  "video/mp4,video/quicktime,video/x-matroska,video/webm,audio/wav,audio/mpeg,audio/mp4,audio/x-m4a";

export const MEDIA_HINT = "MP4 / MOV / MKV / WAV / MP3 / M4A";

/** Seleção de formato de áudio — idêntica nas três abas. */
export function AudioFormatField({ label = "Formato do áudio" }: { label?: string }) {
  return (
    <Field label={label}>
      {(id) => (
        <SelectInput id={id} name="format" defaultValue="mp3">
          <option value="mp3">MP3 320 kbps</option>
          <option value="wav">WAV 48 kHz</option>
          <option value="aac">AAC 192 kbps</option>
        </SelectInput>
      )}
    </Field>
  );
}
