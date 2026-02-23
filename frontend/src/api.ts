import { ChatResponse, SearchResponse, Evidence } from './types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Helper to simulate network delay for mocks
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

// Mock data for fallback
const MOCK_EVIDENCE: Evidence[] = [
  {
    doc_id: "EP-0492-B",
    date: "2006-08-14",
    source_ref: "Flight Logs, pg. 42",
    snippet: "Passenger manifest indicates departure from Teterboro Airport en route to Palm Beach. Notable individuals listed include [REDACTED] and [REDACTED].",
    score: 0.92
  },
  {
    doc_id: "EP-1104-A",
    date: "2008-02-21",
    source_ref: "Financial Records, Exhibit C",
    snippet: "Wire transfer of $250,000 authorized by J.E. to offshore account ending in 4491. Purpose listed as 'Consulting Services'.",
    score: 0.85
  },
  {
    doc_id: "EP-0881-C",
    date: "2005-11-03",
    source_ref: "Visitor Logs, Zorro Ranch",
    snippet: "Entry logged at 14:30 MST. Vehicle plates match registered corporate fleet. Departure not recorded on same day.",
    score: 0.78
  }
];

export const api = {
  async search(query: string): Promise<SearchResponse> {
    try {
      const res = await fetch(`${API_BASE_URL}/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });
      if (!res.ok) throw new Error('Network response was not ok');
      return await res.json();
    } catch (error) {
      console.warn("Backend unreachable, using mock data for /search");
      await delay(800);
      return { results: MOCK_EVIDENCE, total_found: 34 };
    }
  },

  async chat(query: string): Promise<ChatResponse> {
    try {
      const res = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });
      if (!res.ok) throw new Error('Network response was not ok');
      return await res.json();
    } catch (error) {
      console.warn("Backend unreachable, using mock data for /chat");
      await delay(1500);
      return {
        answer: "Based on the available records, there is a documented pattern of travel between Teterboro and Palm Beach during that timeframe [1]. Financial records also indicate significant offshore wire transfers labeled as 'Consulting Services' [2]. Furthermore, visitor logs from the New Mexico property show extended stays by unidentified corporate vehicles [3].\n\nThis suggests a coordinated logistical network supporting these movements.",
        citations: MOCK_EVIDENCE
      };
    }
  }
};
