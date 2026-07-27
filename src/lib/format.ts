/** Formatação pt-BR compartilhada por todo o painel. */

const DATE_TIME = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "short",
  timeStyle: "short",
});

const BYTE_UNITS = ["B", "KB", "MB", "GB"] as const;

/** 1536 → "1.5 KB". Retorna "—" quando não há valor. */
export function formatBytes(bytes?: number | null): string {
  if (!bytes) return "—";
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < BYTE_UNITS.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value >= 10 || unit === 0 ? 0 : 1)} ${BYTE_UNITS[unit]}`;
}

/** Tamanho em megabytes com 2 casas — usado na ficha do job. */
export function formatMegabytes(bytes?: number | null): string | undefined {
  if (!bytes) return undefined;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

/** ISO → "27/07/2026 14:05". Devolve a string original se não for data válida. */
export function formatDateTime(iso?: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return DATE_TIME.format(date);
}

/** 1234567 → "1.234.567". */
export function formatNumber(value?: number | null): string {
  if (value === undefined || value === null || Number.isNaN(value)) return "—";
  return value.toLocaleString("pt-BR");
}
