export interface Evidence {
  doc_id: string;
  snippet: string;
  date: string;
  source_ref: string;
  score?: number;
}

export interface SearchResponse {
  results: Evidence[];
  total_found?: number;
}

export interface ChatResponse {
  answer: string;
  citations: Evidence[];
}

export type AppMode = 'chat' | 'search';
