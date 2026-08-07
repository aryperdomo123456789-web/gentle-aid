export type ReleaseKey = {
  id: string;
  label: string;
  prefix: string;
  scopes: string[];
  created_at: string;
  created_by: string | null;
  expires_at: string;
  revoked_at: string | null;
  last_used_at: string | null;
  status: "active" | "expired" | "revoked";
  expires_in_days: number;
  raw_key?: string;
};

export type ReleaseKeysResponse = {
  keys: ReleaseKey[];
};

export type CreateReleaseKeyInput = {
  label: string;
  expires_in_days: number;
  scopes?: string[] | string;
};

