import { Loader2, UploadCloud } from "lucide-react";
import { useId, useRef, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: (id: string) => ReactNode;
}) {
  const id = useId();
  return (
    <div className="space-y-1.5">
      <label
        htmlFor={id}
        className="block text-[13px] font-semibold tracking-tight text-foreground"
      >
        {label}
      </label>
      {children(id)}
      {hint ? <p className="text-xs leading-5 text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

const control =
  "w-full min-h-11 max-w-full rounded-xl border border-input bg-background/50 px-3.5 py-2.5 text-base sm:text-sm text-foreground placeholder:text-muted-foreground/70 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)] transition-[border-color,box-shadow,background-color] duration-200 hover:border-primary/40 focus:border-primary focus:bg-background/70 focus:outline-none focus:ring-2 focus:ring-ring/35 disabled:cursor-not-allowed disabled:opacity-60";

export function TextInput({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cn(control, className)} />;
}

export function TextArea({
  className,
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={cn(control, "min-h-32 font-mono", className)} />;
}

export function SelectInput({
  className,
  ...props
}: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={cn(control, className)} />;
}

export function FileDrop({
  id,
  name,
  accept,
  onSelect,
  hint,
  multiple = false,
}: {
  id: string;
  name: string;
  accept: string;
  hint: string;
  onSelect?: (file: File | null) => void;
  /** Aceita vários arquivos (ex.: mídias por cena do Estúdio de Vídeo IA). */
  multiple?: boolean;
}) {
  const ref = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  function applyFiles(files: FileList | null) {
    const file = files?.[0] ?? null;
    const count = files?.length ?? 0;
    setFileName(count > 1 ? `${count} arquivos selecionados` : (file?.name ?? null));
    onSelect?.(file);
  }

  return (
    <div>
      <input
        ref={ref}
        id={id}
        name={name}
        type="file"
        accept={accept}
        multiple={multiple}
        className="sr-only"
        onChange={(e) => applyFiles(e.target.files)}
      />
      <button
        type="button"
        onClick={() => ref.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const dropped = e.dataTransfer?.files;
          if (!dropped?.length || !ref.current) return;
          ref.current.files = dropped;
          applyFiles(dropped);
        }}
        className={cn(
          "group flex w-full flex-col items-center gap-2 rounded-xl border border-dashed px-3 py-6 text-center transition-all duration-200 sm:px-4 sm:py-8",
          dragging
            ? "border-primary bg-primary/10"
            : fileName
              ? "border-success/50 bg-success/5 hover:border-success"
              : "border-border bg-background/40 hover:border-primary/60 hover:bg-background/60",
        )}
      >
        <span
          className={cn(
            "grid size-11 place-items-center rounded-full transition-transform duration-200 group-hover:scale-105",
            fileName ? "bg-success/15" : "bg-primary/12",
          )}
        >
          <UploadCloud
            className={cn("size-5", fileName ? "text-success" : "text-primary")}
            aria-hidden="true"
          />
        </span>
        <span className="w-full break-words text-sm font-medium text-foreground">
          {fileName ??
            (multiple ? "Selecionar arquivos do computador" : "Selecionar arquivo do computador")}
        </span>
        <span className="text-xs leading-5 text-muted-foreground">
          {dragging ? "Solte para carregar" : hint}
        </span>
      </button>
    </div>
  );
}

export function SubmitButton({
  busy,
  disabled,
  children,
  variant = "primary",
}: {
  busy: boolean;
  disabled?: boolean;
  children: ReactNode;
  variant?: "primary" | "electric";
}) {
  return (
    <button
      type="submit"
      disabled={busy || disabled}
      className={cn(
        "inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-center text-sm font-semibold shadow-lg shadow-primary/20 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-xl hover:shadow-primary/30 active:translate-y-0 active:scale-[0.99] disabled:cursor-not-allowed disabled:translate-y-0 disabled:opacity-60 disabled:shadow-none",
        variant === "electric" ? "bg-electric text-electric-foreground" : "text-primary-foreground",
      )}
      style={variant === "primary" ? { backgroundImage: "var(--gradient-viral)" } : undefined}
    >
      {busy ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : null}
      {children}
    </button>
  );
}
