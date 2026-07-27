import type { VoiceMode } from "../types";

const TABS: { value: VoiceMode; label: string }[] = [
  { value: "media", label: "Trocar timbre" },
  { value: "dub", label: "Dublagem IA" },
  { value: "text", label: "Texto → narração" },
  { value: "forge", label: "Criar voz" },
];

/** Alternância entre os modos do Estúdio de Voz. */
export function VoiceModeTabs({
  mode,
  onChange,
}: {
  mode: VoiceMode;
  onChange: (mode: VoiceMode) => void;
}) {
  return (
    <div className="flex gap-2 rounded-xl border border-border bg-background/40 p-1">
      {TABS.map(({ value, label }) => (
        <button
          key={value}
          type="button"
          onClick={() => onChange(value)}
          className={`flex-1 rounded-lg px-3 py-2 text-xs font-semibold transition-colors ${
            mode === value
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
