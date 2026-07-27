import type { ScanReport } from "../types";

/** Diagnóstico da varredura de chaves no servidor legado. */
export function ScanReportPanel({ report, onClose }: { report: ScanReport; onClose: () => void }) {
  return (
    <section className="panel mb-6 p-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="font-display text-base font-semibold">Diagnóstico da varredura</h2>
        <button
          type="button"
          onClick={onClose}
          className="rounded-full border border-border bg-surface/60 px-3 py-1 text-xs"
        >
          Fechar
        </button>
      </div>
      <p className="text-xs text-muted-foreground">
        {report.files_scanned} arquivo(s) lidos · {report.env_vars_seen} variáveis de ambiente ·
        diretórios: <span className="font-mono">{report.roots.join(", ")}</span>
      </p>
      <ul className="mt-3 grid gap-1 text-xs sm:grid-cols-2">
        {report.hits.map((hit) => (
          <li
            key={hit.id}
            className="flex items-center justify-between gap-2 rounded-lg border border-border bg-background/40 px-3 py-1.5"
          >
            <span>{hit.name}</span>
            <span className={hit.found ? "text-success" : "text-muted-foreground"}>
              {hit.found ? `achou · ${hit.var}` : "não encontrada"}
            </span>
          </li>
        ))}
      </ul>
      {report.files.length ? (
        <details className="mt-3">
          <summary className="cursor-pointer text-xs text-muted-foreground">
            Ver arquivos varridos ({report.files.length})
          </summary>
          <ul className="mt-2 max-h-56 space-y-0.5 overflow-auto font-mono text-[11px] text-muted-foreground">
            {report.files.map((file) => (
              <li key={file}>{file}</li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  );
}
