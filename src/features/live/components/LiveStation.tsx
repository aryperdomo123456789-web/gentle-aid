import { KeyRound, Radio, Square } from "lucide-react";
import { useState } from "react";

import { Field, FileDrop, SelectInput, TextInput } from "@/components/form";
import { JobSettingsGuard } from "@/components/JobSettingsGuard";
import { ToolShell } from "@/components/ToolShell";
import { Link } from "@tanstack/react-router";

import { LiveGuide, type LiveGuideStep } from "./LiveGuide";
import { LiveLog } from "./LiveLog";
import { PlaylistPicker } from "./PlaylistPicker";
import { StreamHealth } from "./StreamHealth";
import { useLiveStation } from "../use-live-station";
import type { LivePlatform } from "../types";

/**
 * Corpo compartilhado das duas páginas de live.
 *
 * As páginas `/live-youtube` e `/live-tiktok` usam o mesmo motor e mudam
 * apenas as cópias, os avisos e o preset padrão.
 */
export function LiveStation({
  platform,
  badge,
  title,
  subtitle,
  warning,
  keyHelp,
  guideTitle,
  steps,
}: {
  platform: LivePlatform;
  badge: string;
  title: string;
  subtitle: string;
  warning: string;
  keyHelp: string;
  guideTitle: string;
  steps: LiveGuideStep[];
}) {
  const station = useLiveStation(platform);
  const [selected, setSelected] = useState<string[]>([]);
  const [hasUpload, setHasUpload] = useState(false);

  const info = station.options?.platforms.find((item) => item.id === platform);
  const presets = station.options?.presets ?? [];
  const defaultPreset = info?.default_preset ?? presets[0]?.id ?? "";

  function toggle(path: string) {
    setSelected((current) =>
      current.includes(path) ? current.filter((item) => item !== path) : [...current, path],
    );
  }

  function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    form.set("platform", platform);
    form.set("paths", JSON.stringify(selected));
    void station.start(form);
  }

  const canStart = (selected.length > 0 || hasUpload) && !station.active;

  return (
    <ToolShell
      badge={badge}
      title={title}
      subtitle={subtitle}
      left={
        <form onSubmit={onSubmit} className="space-y-5">
          <p className="rounded-xl border border-warning/40 bg-warning/10 p-3 text-xs text-foreground">
            {warning}
          </p>

          <LiveGuide title={guideTitle} steps={steps} />


          <PlaylistPicker
            library={station.library}
            selected={selected}
            onToggle={toggle}
            onClear={() => setSelected([])}
            onRefresh={() => void station.refreshLibrary()}
            disabled={station.active}
          />

          <Field label="Ou envie um vídeo do PC" hint="MP4, MOV, MKV ou WEBM. Entra no fim da fila.">
            {(id) => (
              <FileDrop
                id={id}
                name="videos"
                accept="video/mp4,video/quicktime,video/x-matroska,video/webm"
                hint="MP4 / MOV / MKV / WEBM"
                multiple
                onSelect={(file) => setHasUpload(Boolean(file))}
              />
            )}
          </Field>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-5">
            <Field label="Preset de qualidade">
              {(id) => (
                <SelectInput id={id} name="preset" defaultValue={defaultPreset} key={defaultPreset}>
                  {presets.map((preset) => (
                    <option key={preset.id} value={preset.id}>
                      {preset.label} · {preset.bitrate} kbps
                    </option>
                  ))}
                </SelectInput>
              )}
            </Field>
            <Field label="Limite de reconexões" hint="0 = reconectar para sempre (recomendado).">
              {(id) => <TextInput id={id} name="max_retries" type="number" min={0} defaultValue={0} />}
            </Field>
          </div>

          <Field label="URL RTMP" hint={keyHelp}>
            {(id) => (
              <TextInput
                id={id}
                name="rtmp_url"
                placeholder={info?.default_url || "rtmp://servidor/live"}
                defaultValue={info?.default_url ?? ""}
                key={info?.default_url}
              />
            )}
          </Field>

          <Field
            label="Stream key"
            hint={
              info?.key_configured
                ? "Já existe uma chave salva na Central de APIs — deixe em branco para reutilizá-la."
                : "Cole a chave da plataforma. Salve na Central de APIs para não digitar toda vez."
            }
          >
            {(id) => (
              <TextInput
                id={id}
                name="stream_key"
                type="password"
                autoComplete="off"
                placeholder={info?.key_configured ? "•••••••• (usando a chave salva)" : "chave RTMP"}
              />
            )}
          </Field>

          <div className="rounded-xl border border-border bg-background/40 p-3">
            <p className="text-[13px] font-semibold text-foreground">Overlay dinâmico</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Mantém o frame em movimento — evita que a plataforma classifique a live como vídeo
              estático repetido.
            </p>
            <div className="mt-3 space-y-2 text-xs">
              <label className="flex items-center gap-2">
                <input type="checkbox" name="overlay_clock" defaultChecked className="size-4" />
                Relógio ao vivo (canto superior direito)
              </label>
              <label className="flex items-center gap-2">
                <input type="checkbox" name="overlay_counter" defaultChecked className="size-4" />
                Contador de tempo no ar (canto superior esquerdo)
              </label>
              <Field label="Texto fixo (opcional)">
                {(id) => (
                  <TextInput id={id} name="overlay_text" maxLength={120} placeholder="AO VIVO 24/7" />
                )}
              </Field>
            </div>
          </div>

          {station.error ? (
            <p className="rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
              {station.error}
            </p>
          ) : null}

          {station.active ? (
            <button
              type="button"
              onClick={() => void station.stop()}
              disabled={station.busy}
              className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl border border-destructive/50 bg-destructive/10 px-4 text-sm font-semibold text-destructive transition hover:bg-destructive/20 disabled:opacity-60"
            >
              <Square className="size-4" aria-hidden="true" />
              {station.busy ? "Encerrando…" : "Encerrar transmissão"}
            </button>
          ) : (
            <JobSettingsGuard
              busy={station.busy}
              disabled={!canStart}
              label="Entrar ao vivo"
              busyLabel="Conectando ao RTMP…"
            />
          )}

          <p className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <KeyRound className="size-3.5" aria-hidden="true" />
            <Link to="/apis" className="underline underline-offset-2 hover:text-foreground">
              Guardar a stream key na Central de APIs
            </Link>
          </p>
        </form>
      }
      right={
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Radio className="size-4 text-primary" aria-hidden="true" />
            <p className="text-sm font-semibold text-foreground">Saúde da transmissão</p>
          </div>
          <StreamHealth session={station.session} />
          <LiveLog lines={station.session?.log ?? []} />
        </div>
      }
    />
  );
}
