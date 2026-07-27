/** Tipos da Central de APIs (cofre de chaves do servidor). */

export type TestAction = "replace_key" | "billing" | "scope" | "wait" | "network" | "check";

export type TestResult = {
  ok: boolean | null;
  status: number;
  message: string;
  action?: TestAction | null;
  remediation?: string | null;
  latency_ms?: number;
  at?: string;
};

export type ProviderSource = "cofre" | "env" | "vazio";

export type Provider = {
  id: string;
  name: string;
  category: string;
  env: string;
  docs: string;
  usage: string;
  prefix?: string | null;
  format_hint?: string | null;
  format_ok?: boolean | null;
  testable: boolean;

  configured: boolean;
  source: ProviderSource;
  project_active: boolean;
  project_label: string;
  masked: string;
  note: string;
  updated_at?: string | null;
  last_test?: TestResult | null;
};

export type ScanHit = {
  id: string;
  name: string;
  found: boolean;
  var?: string | null;
  origin?: string;
};

export type ScanReport = {
  roots: string[];
  files_scanned: number;
  files: string[];
  env_vars_seen: number;
  hits: ScanHit[];
};
