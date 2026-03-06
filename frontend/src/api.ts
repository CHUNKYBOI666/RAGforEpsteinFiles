import type { ChatMessage, ChatResponse, ChatSession, EntitySearchResponse, Evidence, GraphResponse, Source, StatsResponse } from './types';

export interface GetGraphParams {
  entity?: string;
  date_from?: string;
  date_to?: string;
  keywords?: string;
  limit?: number;
}

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

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

function deviceHeaders(deviceId: string): Record<string, string> {
  return { 'X-Device-Id': deviceId };
}

export const api = {
  /** GET /api/entities — preset list of all entities (names + counts) for graph dropdown */
  async getEntityPreset(): Promise<EntitySearchResponse> {
    try {
      const res = await fetch(`${API_BASE_URL}/api/entities`);
      if (!res.ok) throw new Error('Network response was not ok');
      const data = await res.json();
      return { results: Array.isArray(data) ? data : [] };
    } catch {
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
    } catch {
      console.warn('Backend unreachable, using empty entity search');
      await delay(400);
      return { results: [] };
    }
  },

  /** GET /api/chat?q= — RAG chat; returns answer, sources, triples. Requires deviceId (X-Device-Id). Optional sessionId to persist turn. */
  async chat(query: string, deviceId: string, sessionId?: string | null): Promise<ChatResponse> {
    const params = new URLSearchParams({ q: query.trim() });
    if (sessionId) params.set('session_id', sessionId);
    const res = await fetch(`${API_BASE_URL}/api/chat?${params.toString()}`, {
      headers: deviceHeaders(deviceId),
    });
    if (!res.ok) throw new Error('Network response was not ok');
    const data = await res.json();
    return {
      answer: data.answer ?? '',
      sources: Array.isArray(data.sources) ? data.sources : [],
      triples: Array.isArray(data.triples) ? data.triples : [],
    };
  },

  /** POST /api/sessions — create a new anonymous chat session. */
  async createSession(deviceId: string, title?: string): Promise<ChatSession> {
    const res = await fetch(`${API_BASE_URL}/api/sessions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...deviceHeaders(deviceId),
      },
      body: JSON.stringify(title != null ? { title } : {}),
    });
    if (!res.ok) throw new Error('Network response was not ok');
    return res.json();
  },

  /** GET /api/sessions — list anonymous sessions for this device. */
  async getSessions(deviceId: string): Promise<ChatSession[]> {
    const res = await fetch(`${API_BASE_URL}/api/sessions`, {
      headers: deviceHeaders(deviceId),
    });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  },

  /** GET /api/sessions/{id} — get one session and its messages. */
  async getSession(sessionId: string, deviceId: string): Promise<{ session: ChatSession; messages: ChatMessage[] }> {
    const res = await fetch(`${API_BASE_URL}/api/sessions/${encodeURIComponent(sessionId)}`, {
      headers: deviceHeaders(deviceId),
    });
    if (res.status === 404) throw new Error('Session not found.');
    if (!res.ok) throw new Error('Network response was not ok');
    return res.json();
  },

  /** DELETE /api/sessions/{id} — delete a session and its messages. */
  async deleteSession(sessionId: string, deviceId: string): Promise<void> {
    const res = await fetch(`${API_BASE_URL}/api/sessions/${encodeURIComponent(sessionId)}`, {
      method: 'DELETE',
      headers: deviceHeaders(deviceId),
    });
    if (res.status === 404) throw new Error('Session not found.');
    if (!res.ok) throw new Error('Network response was not ok');
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
