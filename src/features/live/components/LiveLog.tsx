import { useEffect, useRef } from "react";

/** Log ao vivo do supervisor de transmissão (mesmo padrão do rastro de jobs). */
export function LiveLog({ lines }: { lines: string[] }) {
  const ref = useRef<HTMLPreElement>(null);

  useEffect(() => {
    const node = ref.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [lines]);

  return (
    <div className="rounded-xl border border-border bg-background/60">
      <p className="border-b border-border px-3 py-2 text-[11px] uppercase tracking-wide text-muted-foreground">
        Log da transmissão
      </p>
      <pre
        ref={ref}
        className="max-h-72 overflow-auto whitespace-pre-wrap break-words p-3 font-mono text-[11px] leading-5 text-muted-foreground"
      >
        {lines.length ? lines.join("\n") : "Sem eventos ainda."}
      </pre>
    </div>
  );
}
