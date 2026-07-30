import { Field, SelectInput } from "@/components/form";

/**
 * Formato final do vídeo — disponível em toda ferramenta que baixa/recodifica.
 * O valor viaja como `video_format` (JSON ou multipart) e é resolvido pelo
 * motor de esterilização no backend.
 */
export const VIDEO_FORMATS = [
  { value: "original", label: "Original — mantém a proporção da fonte" },
  { value: "9:16", label: "9:16 vertical — TikTok, Reels, Shorts (1080x1920)" },
  { value: "4:5", label: "4:5 retrato — feed do Instagram (1080x1350)" },
  { value: "1:1", label: "1:1 quadrado — feed clássico (1080x1080)" },
  { value: "16:9", label: "16:9 horizontal — YouTube, TV (1920x1080)" },
  { value: "4:3", label: "4:3 clássico — nostálgico (1440x1080)" },
] as const;

export const FORMAT_FITS = [
  { value: "cover", label: "Preencher — corta as sobras, sem barras" },
  { value: "contain", label: "Encaixar — mostra tudo com barras pretas" },
] as const;

type Props = {
  name?: string;
  fitName?: string;
  defaultValue?: string;
  defaultFit?: string;
  /** Modo controlado — quando informado, `defaultValue` é ignorado. */
  value?: string;
  onChange?: (value: string) => void;
  fit?: string;
  onFitChange?: (value: string) => void;
  label?: string;
  hint?: string;
  /** Esconde o seletor de encaixe (útil em formulários compactos). */
  showFit?: boolean;
};

export function VideoFormatSelect({
  name = "video_format",
  fitName = "format_fit",
  defaultValue = "original",
  defaultFit = "cover",
  value,
  onChange,
  fit,
  onFitChange,
  label = "Formato final do vídeo",
  hint = "Escolha a proporção de entrega. O reenquadramento acontece na mesma passada do FFmpeg, antes da esterilização.",
  showFit = true,
}: Props) {
  const controlled = value !== undefined;
  const fitControlled = fit !== undefined;
  const currentFormat = controlled ? value : undefined;

  return (
    <div className="space-y-4">
      <Field label={label} hint={hint}>
        {(id) => (
          <SelectInput
            id={id}
            name={name}
            {...(controlled
              ? {
                  value,
                  onChange: (e: React.ChangeEvent<HTMLSelectElement>) => onChange?.(e.target.value),
                }
              : { defaultValue })}
          >
            {VIDEO_FORMATS.map((format) => (
              <option key={format.value} value={format.value}>
                {format.label}
              </option>
            ))}
          </SelectInput>
        )}
      </Field>

      {showFit && currentFormat !== "original" ? (
        <Field
          label="Encaixe do quadro"
          hint="Preencher entrega a tela cheia (recomendado para viral); encaixar preserva o enquadramento original."
        >
          {(id) => (
            <SelectInput
              id={id}
              name={fitName}
              {...(fitControlled
                ? {
                    value: fit,
                    onChange: (e: React.ChangeEvent<HTMLSelectElement>) =>
                      onFitChange?.(e.target.value),
                  }
                : { defaultValue: defaultFit })}
            >
              {FORMAT_FITS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </SelectInput>
          )}
        </Field>
      ) : null}
    </div>
  );
}
