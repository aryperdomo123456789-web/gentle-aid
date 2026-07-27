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
    <div className="space-y-2">
      <label htmlFor={id} className="block text-sm font-medium text-foreground">
        {label}
      </label>
      {children(id)}
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

const control =
  "w-full rounded-xl border border-input bg-background/60 px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-ring/40";

export function TextInput({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cn(control, className)} />;
}

export function TextArea({ className, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={cn(control, "min-h-32 font-mono", className)} />;
}

export function SelectInput({ className, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={cn(control, className)} />;
}

export function FileDrop({
  id,
  name,
  accept,
  onSelect,
  hint,
}: {
  id: string;
  name: string;
  accept: string;
  hint: string;
  onSelect?: (file: File | null) => void;
}) {
  const ref = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = useState<string | null>(null);

  return (
    <div>
      <input
        ref={ref}
        id={id}
        name={name}
        type="file"
        accept={accept}
        className="sr-only"
        onChange={(e) => {
          const file = e.target.files?.[0] ?? null;
          setFileName(file?.name ?? null);
          onSelect?.(file);
        }}
      />
      <button
        type="button"
        onClick={() => ref.current?.click()}
        className="flex w-full flex-col items-center gap-2 rounded-xl border border-dashed border-border bg-background/40 px-4 py-8 text-center transition-colors hover:border-primary/60"
      >
        <UploadCloud className="size-6 text-primary" aria-hidden="true" />
        <span className="text-sm font-medium text-foreground">
          {fileName ?? "Selecionar arquivo do computador"}
        </span>
        <span className="text-xs text-muted-foreground">{hint}</span>
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
      className={`inline-flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold transition-opacity disabled:cursor-not-allowed disabled:opacity-60 ${
        variant === "electric"
          ? "bg-electric text-electric-foreground hover:opacity-90"
          : "text-primary-foreground hover:opacity-90"
      }`}
      style={variant === "primary" ? { backgroundImage: "var(--gradient-viral)" } : undefined}
    >
      {busy ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : null}
      {children}
    </button>
  );
}
