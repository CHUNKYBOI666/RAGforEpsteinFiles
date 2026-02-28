export interface Evidence {
  doc_id: string;
  snippet: string;
  date: string;
  source_ref: string;
  score?: number;
}

/** Backend chat source: document metadata for source cards */
export interface Source {
  doc_id: string;
  one_sentence_summary: string | null;
  category: string | null;
  date_range_earliest: string | null;
  date_range_latest: string | null;
}

/** Backend chat triple: structured fact for timeline */
export interface Triple {
  actor: string;
  action: string;
  target: string;
  timestamp: string;
  location: string;
  doc_id: string;
}

export interface SearchResponse {
  results: Evidence[];
  total_found?: number;
}

/** Backend chat response (GET /api/chat) */
export interface ChatResponse {
  answer: string;
  sources: Source[];
  triples: Triple[];
}

/** Entity search result (GET /api/search) */
export interface EntitySearchResult {
  canonical_name: string;
  count: number;
}

export interface EntitySearchResponse {
  results: EntitySearchResult[];
}

export type AppMode = 'chat' | 'search';
