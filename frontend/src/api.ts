import type { ChatResponse, EntitySearchResponse, Evidence, GraphResponse, Source, StatsResponse } from './types';

export interface GetGraphParams {
  entity?: string;
  date_from?: string;
  date_to?: string;
  keywords?: string;
  limit?: number;
}

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Helper to simulate network delay for mocks
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** Map backend sources to Evidence[] for EvidenceCard */
export function sourcesToEvidence(sources: Source[]): Evidence[] {
  return sources.map((s) => ({
    doc_id: s.doc_id,
    snippet: s.one_sentence_summary ?? '',
    date: s.date_range_earliest ?? s.date_range_latest ?? '—',
    source_ref: s.category ?? s.doc_id,
  }));
}

// Mock data for fallback when backend is unreachable
const MOCK_EVIDENCE: Evidence[] = [
  {
    doc_id: 'EP-0492-B',
    date: '2006-08-14',
    source_ref: 'Flight Logs, pg. 42',
    snippet:
      "Passenger manifest indicates departure from Teterboro Airport en route to Palm Beach. Notable individuals listed include [REDACTED] and [REDACTED].",
    score: 0.92,
  },
  {
    doc_id: 'EP-1104-A',
    date: '2008-02-21',
    source_ref: 'Financial Records, Exhibit C',
    snippet:
      "Wire transfer of $250,000 authorized by J.E. to offshore account ending in 4491. Purpose listed as 'Consulting Services'.",
    score: 0.85,
  },
  {
    doc_id: 'EP-0881-C',
    date: '2005-11-03',
    source_ref: 'Visitor Logs, Zorro Ranch',
    snippet:
      'Entry logged at 14:30 MST. Vehicle plates match registered corporate fleet. Departure not recorded on same day.',
    score: 0.78,
  },
];

export const api = {
  /** GET /api/entities — preset list of all entities (names + counts) for graph dropdown */
  async getEntityPreset(): Promise<EntitySearchResponse> {
    try {
      const res = await fetch(`${API_BASE_URL}/api/entities`);
      if (!res.ok) throw new Error('Network response was not ok');
      const data = await res.json();
      return { results: Array.isArray(data) ? data : [] };
    } catch (error) {
      console.warn('Backend unreachable, using empty entity preset');
      await delay(400);
      return { results: [] };
    }
  },

  /** GET /api/search?q= — entity/actor search; returns canonical names + counts */
  async search(query: string): Promise<EntitySearchResponse> {
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/search?q=${encodeURIComponent(query.trim())}`
      );
      if (!res.ok) throw new Error('Network response was not ok');
      const data = await res.json();
      return { results: Array.isArray(data) ? data : [] };
    } catch (error) {
      console.warn('Backend unreachable, using empty entity search');
      await delay(400);
      return { results: [] };
    }
  },

  /** GET /api/chat?q= — RAG chat; returns answer, sources, triples. Requires accessToken (JWT). Optional sessionId to persist turn. */
  async chat(query: string, accessToken: string | null): Promise<ChatResponse> {
    if (!accessToken) {
      throw new Error('Sign in to ask a question.');
    }
    const params = new URLSearchParams({ q: query.trim() });
    const res = await fetch(`${API_BASE_URL}/api/chat?${params.toString()}`, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    });
    if (res.status === 401) {
      throw new Error('Session expired or invalid. Please sign in again.');
    }
    if (!res.ok) throw new Error('Network response was not ok');
    const data = await res.json();
    return {
      answer: data.answer ?? '',
      sources: Array.isArray(data.sources) ? data.sources : [],
      triples: Array.isArray(data.triples) ? data.triples : [],
    };
  },

  /** GET /api/document/{doc_id}/text — full document text for modal */
  async getDocumentText(doc_id: string): Promise<{ full_text: string }> {
    const res = await fetch(`${API_BASE_URL}/api/document/${encodeURIComponent(doc_id)}/text`);
    if (!res.ok) throw new Error(res.status === 404 ? 'Document not found' : 'Network response was not ok');
    return res.json();
  },

  /** GET /api/stats — document, triple, chunk, actor counts */
  async getStats(): Promise<StatsResponse> {
    const res = await fetch(`${API_BASE_URL}/api/stats`);
    if (!res.ok) throw new Error('Network response was not ok');
    return res.json();
  },

  /** GET /api/graph — nodes and edges for relationship graph */
  async getGraph(params: GetGraphParams = {}): Promise<GraphResponse> {
    const sp = new URLSearchParams();
    if (params.entity != null && params.entity !== '') sp.set('entity', params.entity);
    if (params.date_from != null && params.date_from !== '') sp.set('date_from', params.date_from);
    if (params.date_to != null && params.date_to !== '') sp.set('date_to', params.date_to);
    if (params.keywords != null && params.keywords !== '') sp.set('keywords', params.keywords);
    if (params.limit != null) sp.set('limit', String(params.limit));
    const qs = sp.toString();
    const url = `${API_BASE_URL}/api/graph${qs ? `?${qs}` : ''}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error('Network response was not ok');
    const data = await res.json();
    return {
      nodes: Array.isArray(data.nodes) ? data.nodes : [],
      edges: Array.isArray(data.edges) ? data.edges : [],
    };
  },
};
