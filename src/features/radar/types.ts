/** Modelos de dados do Radar Global (`/api/radar`). */

export type RadarSearch = {
  term: string;
  traffic: string;
  context?: string;
  search_url: string;
};

export type RadarVideo = {
  id: string;
  title: string;
  author: string;
  views: number;
  views_human: string;
  url: string;
  embed_url?: string | null;
  thumbnail?: string | null;
  is_short: boolean;
  source: string;
};

export type RadarWebResult = {
  title: string;
  url: string;
  snippet: string;
  provider: string;
};

export type RadarSource = {
  name: string;
  ok: boolean;
  items?: number;
  error?: string;
};

export type IntelligenceItem = {
  topic: string;
  score: number;
  confidence: number;
  horizon: string;
  because: string;
  signals: string[];
  sources: string[];
  formats: string[];
  search_url: string;
  region: string;
};

export type RadarData = {
  region: string;
  nicho: string;
  generated_at: string;
  searches: RadarSearch[];
  youtube_trending: RadarVideo[];
  niche_videos: RadarVideo[];
  tiktok: RadarVideo[];
  web: { results: RadarWebResult[]; chosen?: string | null; providers: RadarSource[] };
  intelligence: IntelligenceItem[];
  sources: RadarSource[];
};

export type ForecastItem = {
  nicho: string;
  horizonte: string;
  confianca: number;
  porque: string;
  angulos?: string[];
  hashtags?: string[];
  formato?: string;
  fonte?: string;
};

export type ForecastData = {
  engine: string;
  generated_at: string;
  forecast: ForecastItem[];
};

export type RadarSnapshot = {
  nicho: string;
  region: string;
  data: RadarData | null;
  forecast: ForecastData | null;
};
