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

/** Chat session (saved conversation) from GET/POST /api/sessions */
export interface ChatSession {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

/** Single message in a session from GET /api/sessions/{id} */
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string | null;
  sources: Source[] | null;
  triples: Triple[] | null;
  created_at: string;
}

/** Entity search result (GET /api/search) */
export interface EntitySearchResult {
  canonical_name: string;
  count: number;
}

export interface EntitySearchResponse {
  results: EntitySearchResult[];
}

/** Graph node (entity) from GET /api/graph */
export interface GraphNode {
  id: string;
  label: string;
  count: number;
}

/** Graph edge (triple) from GET /api/graph */
export interface GraphEdge {
  source: string;
  target: string;
  action: string;
  doc_id: string;
  timestamp: string;
  location: string;
}

/** Backend graph response (GET /api/graph) */
export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

/** Stats from GET /api/stats */
export interface StatsResponse {
  document_count: number;
  triple_count: number;
  chunk_count: number;
  actor_count: number;
}

export type AppMode = 'chat' | 'search' | 'graph';
