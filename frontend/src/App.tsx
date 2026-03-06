import React, { useState, useRef, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Search, MessageSquare, ArrowRight, Loader2, ShieldAlert, FileText, X, Network } from 'lucide-react';
import { Analytics } from '@vercel/analytics/react';
import { CitationPill } from './components/CitationPill';
import { EvidenceCard } from './components/EvidenceCard';
import { RelationshipGraph } from './components/RelationshipGraph';
import { api, sourcesToEvidence } from './api';
import { getDeviceId } from './lib/deviceId';
import { Analytics } from '@vercel/analytics/react';
import type { AppMode, ChatMessage, ChatSession, Evidence, EntitySearchResult, GraphEdge, GraphNode, StatsResponse, Triple } from './types';

const markdownComponents: React.ComponentProps<typeof ReactMarkdown>['components'] = {
  p: ({ children }) => <p className="mb-3 last:mb-0 text-zinc-300 leading-relaxed">{children}</p>,
  h1: ({ children }) => <h1 className="text-2xl font-serif font-semibold text-zinc-100 mt-6 mb-2 first:mt-0">{children}</h1>,
  h2: ({ children }) => <h2 className="text-xl font-serif font-semibold text-zinc-100 mt-5 mb-2 first:mt-0">{children}</h2>,
  h3: ({ children }) => <h3 className="text-lg font-serif font-semibold text-zinc-200 mt-4 mb-2 first:mt-0">{children}</h3>,
  strong: ({ children }) => <strong className="font-semibold text-zinc-200">{children}</strong>,
  ul: ({ children }) => <ul className="list-disc list-inside mb-3 space-y-1 text-zinc-300">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal list-inside mb-3 space-y-1 text-zinc-300">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  blockquote: ({ children }) => <blockquote className="border-l-2 border-zinc-600 pl-4 my-3 text-zinc-400 italic">{children}</blockquote>,
  code: ({ children }) => <code className="px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300 font-mono text-sm">{children}</code>,
};

const DATE_RANGE_MIN = 1980;
const DATE_RANGE_MAX = 2025;

const EPSTEIN_INTRO_DURATION_MS = 5000;
const INTRO_FADE_DURATION_MS = 2500;

export default function App() {
  const deviceId = useMemo(() => getDeviceId(), []);
  const [mode, setMode] = useState<AppMode>('chat');
  const [query, setQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const [activeQuery, setActiveQuery] = useState('');
  const [answer, setAnswer] = useState<string>('');
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [triples, setTriples] = useState<Triple[]>([]);

  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [selectedTurnIndex, setSelectedTurnIndex] = useState<number | null>(null);
  const [highlightedEvidenceIndex, setHighlightedEvidenceIndex] = useState<number | null>(null);

  const [entityResults, setEntityResults] = useState<EntitySearchResult[]>([]);

  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([]);
  const [graphLoading, setGraphLoading] = useState(false);
  const [graphEntity, setGraphEntity] = useState('');
  const [graphKeywords, setGraphKeywords] = useState('');
  const [graphYearMin, setGraphYearMin] = useState(DATE_RANGE_MIN);
  const [graphYearMax, setGraphYearMax] = useState(DATE_RANGE_MAX);
  const [selectedGraphNodeId, setSelectedGraphNodeId] = useState<string | null>(null);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [graphEntityPresetList, setGraphEntityPresetList] = useState<EntitySearchResult[]>([]);
  const [graphEntityPresetLoading, setGraphEntityPresetLoading] = useState(false);
  const [graphEntitySuggestions, setGraphEntitySuggestions] = useState<EntitySearchResult[]>([]);
  const [graphEntitySuggestionsOpen, setGraphEntitySuggestionsOpen] = useState(false);
  const graphEntityContainerRef = useRef<HTMLDivElement>(null);

  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [documentText, setDocumentText] = useState<string | null>(null);
  const [documentLoading, setDocumentLoading] = useState(false);
  const [documentError, setDocumentError] = useState<string | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const evidencePanelScrollRef = useRef<HTMLDivElement>(null);
  const activeEvidenceCardRef = useRef<HTMLDivElement | null>(null);

  type IntroPhase = 'intro' | 'fading' | 'done';
  const [introPhase, setIntroPhase] = useState<IntroPhase>('intro');
  const introTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const effectiveTurnIndex = useMemo(() => {
    if (chatMessages.length === 0) return null;
    if (selectedTurnIndex !== null && chatMessages[selectedTurnIndex]?.role === 'assistant') {
      return selectedTurnIndex;
    }
    for (let i = chatMessages.length - 1; i >= 0; i--) {
      if (chatMessages[i].role === 'assistant') return i;
    }
    return null;
  }, [chatMessages, selectedTurnIndex]);

  const panelEvidence = useMemo(() => {
    if (effectiveTurnIndex === null) return evidence;
    return sourcesToEvidence(chatMessages[effectiveTurnIndex]?.sources ?? []);
  }, [effectiveTurnIndex, chatMessages, evidence]);

  const panelQuery = useMemo(() => {
    if (effectiveTurnIndex === null) return null;
    const prevIdx = effectiveTurnIndex - 1;
    if (prevIdx >= 0 && chatMessages[prevIdx]?.role === 'user') {
      return chatMessages[prevIdx].content;
    }
    return null;
  }, [effectiveTurnIndex, chatMessages]);

  useEffect(() => {
    setHighlightedEvidenceIndex(null);
  }, [effectiveTurnIndex, panelEvidence.length]);

  useEffect(() => {
    if (highlightedEvidenceIndex == null) return;
    activeEvidenceCardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [highlightedEvidenceIndex]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    if (introPhase !== 'intro') return;
    introTimerRef.current = setTimeout(() => {
      setIntroPhase('fading');
      introTimerRef.current = setTimeout(() => {
        setIntroPhase('done');
        introTimerRef.current = null;
      }, INTRO_FADE_DURATION_MS);
    }, EPSTEIN_INTRO_DURATION_MS);
    return () => {
      if (introTimerRef.current) clearTimeout(introTimerRef.current);
    };
  }, [introPhase]);

  useEffect(() => {
    if (hasSearched) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [answer, evidence, triples, entityResults, hasSearched]);

  useEffect(() => {
    let cancelled = false;
    const fetchWithRetry = (attempt = 0, maxAttempts = 3) => {
      if (cancelled) return;
      api
        .getStats()
        .then((data) => {
          if (!cancelled) setStats(data);
        })
        .catch(() => {
          if (cancelled) return;
          if (attempt < maxAttempts - 1) {
            setTimeout(() => fetchWithRetry(attempt + 1, maxAttempts), 2000);
          } else {
            setStats(null);
          }
        });
    };
    fetchWithRetry();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (mode === 'graph') {
      api.getStats().then(setStats).catch(() => setStats(null));
    }
  }, [mode]);

  useEffect(() => {
    if (mode !== 'chat') return;
    setSessionsLoading(true);
    api
      .getSessions(deviceId)
      .then(setSessions)
      .catch(() => setSessions([]))
      .finally(() => setSessionsLoading(false));
  }, [mode, deviceId]);

  useEffect(() => {
    evidencePanelScrollRef.current?.scrollTo(0, 0);
  }, [panelEvidence, entityResults]);

  useEffect(() => {
    if (!selectedDocId) {
      setDocumentText(null);
      setDocumentError(null);
      return;
    }
    setDocumentLoading(true);
    setDocumentError(null);
    api
      .getDocumentText(selectedDocId)
      .then((res) => {
        setDocumentText(res.full_text ?? '');
        setDocumentError(null);
      })
      .catch((err) => {
        setDocumentText(null);
        setDocumentError(err?.message ?? 'Failed to load document');
      })
      .finally(() => setDocumentLoading(false));
  }, [selectedDocId]);

  useEffect(() => {
    if (mode !== 'graph') return;
    setGraphEntityPresetLoading(true);
    api
      .getEntityPreset()
      .then((res) => setGraphEntityPresetList(res.results ?? []))
      .catch(() => setGraphEntityPresetList([]))
      .finally(() => setGraphEntityPresetLoading(false));
  }, [mode]);

  useEffect(() => {
    const trimmed = graphEntity.trim().toLowerCase();
    if (trimmed.length < 1) {
      setGraphEntitySuggestions([]);
      setGraphEntitySuggestionsOpen(false);
      return;
    }
    if (graphEntityPresetLoading) {
      setGraphEntitySuggestions([]);
      setGraphEntitySuggestionsOpen(true);
      return;
    }
    const fromPreset = graphEntityPresetList.filter((r) =>
      (r.canonical_name ?? '').toLowerCase().includes(trimmed)
    );
    if (fromPreset.length > 0) {
      setGraphEntitySuggestions(fromPreset);
      setGraphEntitySuggestionsOpen(true);
      return;
    }
    if (trimmed.length >= 2) {
      api.search(graphEntity.trim()).then((res) => {
        const list = res.results ?? [];
        setGraphEntitySuggestions(list);
        setGraphEntitySuggestionsOpen(true);
      });
    } else {
      setGraphEntitySuggestions([]);
      setGraphEntitySuggestionsOpen(false);
    }
  }, [graphEntity, graphEntityPresetList]);

  useEffect(() => {
    if (!graphEntitySuggestionsOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (graphEntityContainerRef.current?.contains(e.target as Node)) return;
      setGraphEntitySuggestionsOpen(false);
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setGraphEntitySuggestionsOpen(false);
    };
    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleKey);
    };
  }, [graphEntitySuggestionsOpen]);

  const handleSearch = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (mode === 'graph') return;
    if (!query.trim() || isSearching) return;

    setIsSearching(true);
    setHasSearched(true);
    const question = query.trim();
    setActiveQuery(question);
    setAnswer('');
    setEvidence([]);
    setTriples([]);
    setEntityResults([]);
    setSelectedDocId(null);

    try {
      if (mode === 'chat') {
        let sessionId = currentSessionId;
        if (!sessionId) {
          const newSession = await api.createSession(deviceId, 'New chat');
          sessionId = newSession.id;
          setCurrentSessionId(sessionId);
          setSessions((prev) => [newSession, ...prev]);
        }
        const res = await api.chat(question, deviceId, sessionId);
        setAnswer(res.answer);
        setEvidence(sourcesToEvidence(res.sources));
        setTriples(res.triples ?? []);
        const newAssistantIdx = chatMessages.length + 1;
        setChatMessages((prev) => [
          ...prev,
          { role: 'user', content: question, sources: null, triples: null, created_at: new Date().toISOString() },
          {
            role: 'assistant',
            content: res.answer,
            sources: res.sources ?? [],
            triples: res.triples ?? [],
            created_at: new Date().toISOString(),
          },
        ]);
        setSelectedTurnIndex(newAssistantIdx);
        if (sessionId && chatMessages.length === 0) {
          setSessions((prev) =>
            prev.map((s) =>
              s.id === sessionId
                ? { ...s, title: question.length > 50 ? question.slice(0, 50) + '\u2026' : question }
                : s
            )
          );
        }
      } else {
        const res = await api.search(query);
        setEntityResults(res.results ?? []);
      }
    } catch (error) {
      console.error('Error fetching data:', error);
      setAnswer('Error connecting to the archive. Please check your clearance and try again.');
    } finally {
      setIsSearching(false);
      setQuery('');
    }
  };

  const handleNewChat = () => {
    setCurrentSessionId(null);
    setChatMessages([]);
    setSelectedTurnIndex(null);
    setHasSearched(false);
    setAnswer('');
    setEvidence([]);
    setTriples([]);
    setActiveQuery('');
    setQuery('');
    setSelectedDocId(null);
    setMode('chat');
    inputRef.current?.focus();
  };

  const handleSelectSession = async (sessionId: string) => {
    setCurrentSessionId(sessionId);
    try {
      const { messages } = await api.getSession(sessionId, deviceId);
      setChatMessages(messages);
      setHasSearched(messages.length > 0);
      let lastAssistantIdx: number | null = null;
      for (let i = messages.length - 1; i >= 0; i--) {
        if (messages[i].role === 'assistant') { lastAssistantIdx = i; break; }
      }
      setSelectedTurnIndex(lastAssistantIdx);
      const lastAssistant = lastAssistantIdx !== null ? messages[lastAssistantIdx] : null;
      if (lastAssistant?.sources) {
        setEvidence(sourcesToEvidence(lastAssistant.sources));
      } else {
        setEvidence([]);
      }
      if (lastAssistant?.triples) {
        setTriples(lastAssistant.triples);
      } else {
        setTriples([]);
      }
      const lastUser = [...messages].reverse().find((m) => m.role === 'user');
      setActiveQuery(lastUser?.content ?? '');
      setAnswer(lastAssistant?.content ?? '');
    } catch {
      setChatMessages([]);
      setSelectedTurnIndex(null);
      setHasSearched(false);
      setEvidence([]);
      setTriples([]);
      setActiveQuery('');
      setAnswer('');
    }
    setQuery('');
  };

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.deleteSession(sessionId, deviceId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      if (currentSessionId === sessionId) {
        handleNewChat();
      }
    } catch (err) {
      console.error('Failed to delete session', err);
    }
  };

  const handleLoadGraph = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (graphLoading) return;
    setGraphLoading(true);
    setSelectedGraphNodeId(null);
    try {
      const res = await api.getGraph({
        entity: graphEntity.trim() || undefined,
        keywords: graphKeywords.trim() || undefined,
        date_from: String(graphYearMin),
        date_to: String(graphYearMax),
        limit: 500,
      });
      setGraphNodes(res.nodes);
      setGraphEdges(res.edges);
    } catch (err) {
      console.error('Error loading graph:', err);
      setGraphNodes([]);
      setGraphEdges([]);
    } finally {
      setGraphLoading(false);
    }
  };

  type CitationRenderOptions = {
    evidence: Evidence[];
    onCitationClick?: (index: number) => void;
    messageIndex?: number;
    isSelectedTurn?: boolean;
    highlightedEvidenceIndex: number | null;
  };

  const renderAnswerWithCitations = (text: string, options?: CitationRenderOptions) => {
    if (!text) return null;
    const evidence = options?.evidence ?? [];
    const onCitationClick = options?.onCitationClick;
    const isSelectedTurn = options?.isSelectedTurn ?? true;
    const highlightedEvidenceIndex = options?.highlightedEvidenceIndex ?? null;

    const parts = text.split(/(\[\d+\])/g);
    const inlineMarkdownComponents: React.ComponentProps<typeof ReactMarkdown>['components'] = {
      ...markdownComponents,
      p: ({ children }) => <span className="inline">{children}</span>,
    };

    return (
      <span className="citation-flow">
        {parts.map((part, i) => {
          const match = part.match(/\[(\d+)\]/);
          if (match) {
            const num = parseInt(match[1], 10);
            const evidenceIndex = num - 1;
            const ev = evidence[evidenceIndex];
            const label = ev ? (ev.source_ref || ev.doc_id) : `Source ${num}`;
            return (
              <CitationPill
                key={i}
                index={evidenceIndex}
                label={label}
                citationNumber={num}
                onClick={onCitationClick ? () => onCitationClick(evidenceIndex) : undefined}
                isHighlighted={isSelectedTurn && highlightedEvidenceIndex === evidenceIndex}
              />
            );
          }
          if (!part.trim()) return <span key={i} />;
          return (
            <span key={i} className="inline align-baseline">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={inlineMarkdownComponents}>
                {part}
              </ReactMarkdown>
            </span>
          );
        })}
      </span>
    );
  };

  return (
    <div className="relative h-screen min-h-0 bg-zinc-950 text-zinc-200 font-sans overflow-hidden flex flex-col">
      {(introPhase === 'intro' || introPhase === 'fading') && (
        <motion.div
          className="fixed inset-0 z-0 pointer-events-none bg-center bg-no-repeat bg-cover"
          style={{ backgroundImage: "url('/epsteinGIF.gif')" }}
          initial={{ opacity: 1 }}
          animate={{ opacity: introPhase === 'fading' ? 0 : 1 }}
          transition={{ duration: INTRO_FADE_DURATION_MS / 1000 }}
          aria-hidden
        />
      )}
      <motion.div
        className="fixed inset-0 z-0 pointer-events-none bg-center bg-no-repeat bg-cover"
        style={{ backgroundImage: "url('/ascii-animation.gif')" }}
        initial={false}
        animate={{ opacity: introPhase === 'intro' ? 0 : 1 }}
        transition={{ duration: INTRO_FADE_DURATION_MS / 1000 }}
        aria-hidden
      />
      <div className="fixed inset-0 z-0 pointer-events-none bg-zinc-950/60" aria-hidden />

      <header className="sticky top-0 z-20 shrink-0 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 sm:gap-0 p-4 sm:p-6 border-b border-zinc-800/50 bg-zinc-950/50 backdrop-blur-sm">
        <div className="flex items-center justify-between sm:justify-start min-w-0">
          <button
            type="button"
            onClick={() => {
              if (introTimerRef.current) {
                clearTimeout(introTimerRef.current);
                introTimerRef.current = null;
              }
              setHasSearched(false);
              setAnswer('');
              setEvidence([]);
              setTriples([]);
              setActiveQuery('');
              setQuery('');
              setEntityResults([]);
              setSelectedDocId(null);
              setSelectedTurnIndex(null);
              setHighlightedEvidenceIndex(null);
              setIntroPhase('intro');
              setMode('chat');
              window.scrollTo({ top: 0, behavior: 'smooth' });
            }}
            className="flex items-center space-x-2 sm:space-x-3 rounded-md text-zinc-100 hover:text-white hover:bg-zinc-800/50 transition-colors focus:outline-none focus:ring-2 focus:ring-zinc-600 focus:ring-offset-2 focus:ring-offset-zinc-950 -m-2 p-2 min-h-[44px] min-w-[44px] sm:min-w-0"
            aria-label="Go to home and restart"
          >
            <ShieldAlert className="w-5 h-5 sm:w-6 sm:h-6 text-zinc-400 shrink-0" aria-hidden />
            <h1 className="font-serif text-base sm:text-xl tracking-widest uppercase font-semibold truncate">
              The Archive
            </h1>
          </button>
        </div>

        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 sm:gap-4">
          <div className="flex bg-zinc-900/80 p-1 rounded-lg border border-zinc-800 overflow-x-auto scrollbar-hide">
            <button
              onClick={() => setMode('chat')}
              className={`flex items-center shrink-0 px-3 sm:px-4 py-2 sm:py-1.5 rounded-md text-sm font-medium transition-all min-h-[44px] sm:min-h-0 ${
                mode === 'chat' ? 'bg-zinc-800 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200'
              }`}
              aria-label="Synthesize mode"
            >
              <MessageSquare className="w-4 h-4 sm:mr-2" />
              <span className="hidden sm:inline">Synthesize</span>
            </button>
            <button
              onClick={() => setMode('search')}
              className={`flex items-center shrink-0 px-3 sm:px-4 py-2 sm:py-1.5 rounded-md text-sm font-medium transition-all min-h-[44px] sm:min-h-0 ${
                mode === 'search' ? 'bg-zinc-800 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200'
              }`}
              aria-label="Raw Search mode"
            >
              <Search className="w-4 h-4 sm:mr-2" />
              <span className="hidden sm:inline">Raw Search</span>
            </button>
            <button
              onClick={() => setMode('graph')}
              className={`flex items-center shrink-0 px-3 sm:px-4 py-2 sm:py-1.5 rounded-md text-sm font-medium transition-all min-h-[44px] sm:min-h-0 ${
                mode === 'graph' ? 'bg-zinc-800 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200'
              }`}
              aria-label="Network graph mode"
            >
              <Network className="w-4 h-4 sm:mr-2" />
              <span className="hidden sm:inline">Network</span>
            </button>
          </div>
        </div>
      </header>

      <main className="relative z-10 flex-1 min-h-0 flex flex-col overflow-hidden">
        {mode === 'graph' ? (
          <div className="flex-1 flex flex-col md:flex-row min-h-0 overflow-hidden">
            <div className="flex-1 min-w-0 min-h-[300px] md:min-h-0 relative bg-zinc-950/80 border-b md:border-b-0 md:border-r border-zinc-800/50">
              {graphLoading ? (
                <div className="absolute inset-0 flex items-center justify-center text-zinc-400 font-mono text-sm">
                  <Loader2 className="w-5 h-5 animate-spin mr-2" />
                  Loading graph...
                </div>
              ) : graphNodes.length === 0 ? (
                <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-zinc-500">
                  <p className="font-mono text-sm mb-4">Search for an entity to explore connections.</p>
                  <p className="text-xs text-zinc-600">Use the sidebar to set filters and click Go to load the graph.</p>
                </div>
              ) : (
                <RelationshipGraph
                  nodes={graphNodes}
                  edges={graphEdges}
                  selectedNodeId={selectedGraphNodeId}
                  onNodeClick={setSelectedGraphNodeId}
                  onDocClick={setSelectedDocId}
                  width={undefined}
                  height={undefined}
                />
              )}
              {graphNodes.length > 0 && (
                <p className="absolute bottom-3 left-1/2 -translate-x-1/2 text-xs font-mono text-zinc-500">
                  Click nodes to explore relationships.
                </p>
              )}
            </div>
            <div className="w-full md:w-[400px] lg:w-[420px] min-h-0 shrink-0 flex flex-col bg-zinc-950/90 backdrop-blur-xl border-t md:border-t-0 md:border-l border-zinc-900 shadow-2xl z-20 overflow-hidden">
              <div className="shrink-0 p-4 border-b border-zinc-800/50 bg-zinc-900/50 space-y-4">
                <h3 className="font-mono text-xs font-semibold text-zinc-400 uppercase tracking-widest">
                  Graph settings
                </h3>
                {stats && (
                  <div className="grid grid-cols-2 gap-2 text-xs font-mono text-zinc-500">
                    <span>Documents</span>
                    <span className="text-zinc-400">{stats.document_count.toLocaleString()}</span>
                    <span>Relationships</span>
                    <span className="text-zinc-400">{stats.triple_count.toLocaleString()}</span>
                    <span>Events</span>
                    <span className="text-zinc-400">{stats.triple_count.toLocaleString()}</span>
                  </div>
                )}
                <form onSubmit={handleLoadGraph} className="space-y-3">
                  <div ref={graphEntityContainerRef} className="relative">
                    <input
                      type="text"
                      value={graphEntity}
                      onChange={(e) => setGraphEntity(e.target.value)}
                      placeholder="e.g., Jeffrey Epstein"
                      className="w-full rounded-lg bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 outline-none focus:border-zinc-600"
                    />
                    {graphEntitySuggestionsOpen && (graphEntitySuggestions.length > 0 || graphEntityPresetLoading) && (
                      <ul
                        className="absolute left-0 right-0 top-full z-30 mt-1 max-h-48 overflow-y-auto rounded-lg border border-zinc-800 bg-zinc-900 py-1 shadow-xl"
                        onMouseDown={(e) => e.preventDefault()}
                      >
                        {graphEntityPresetLoading ? (
                          <li className="px-3 py-3 text-sm text-zinc-500 font-mono">
                            Loading suggestions...
                          </li>
                        ) : graphEntitySuggestions.length > 0 ? (
                          graphEntitySuggestions.map((r) => (
                            <li key={r.canonical_name}>
                              <button
                                type="button"
                                onMouseDown={(e) => {
                                  e.preventDefault();
                                  setGraphEntity(r.canonical_name ?? '');
                                  setGraphEntitySuggestionsOpen(false);
                                }}
                                className="w-full px-3 py-2 text-left text-sm text-zinc-200 hover:bg-zinc-800 font-mono flex justify-between items-center"
                              >
                                <span>{r.canonical_name}</span>
                                <span className="text-zinc-500 text-xs">{r.count} relationships</span>
                              </button>
                            </li>
                          ))
                        ) : (
                          <li className="px-3 py-3 text-sm text-zinc-500 font-mono">No matches.</li>
                        )}
                      </ul>
                    )}
                  </div>
                  <input
                    type="text"
                    value={graphKeywords}
                    onChange={(e) => setGraphKeywords(e.target.value)}
                    placeholder="e.g., massage, aircraft, island"
                    className="w-full rounded-lg bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 outline-none focus:border-zinc-600"
                  />
                  <div className="space-y-2">
                    <p className="text-xs font-mono text-zinc-500">
                      Date range: {graphYearMin} – {graphYearMax}
                    </p>
                    <div className="grid grid-cols-2 gap-2">
                      <label className="text-xs text-zinc-500 font-mono">From</label>
                      <label className="text-xs text-zinc-500 font-mono">To</label>
                      <input
                        type="range"
                        min={DATE_RANGE_MIN}
                        max={DATE_RANGE_MAX}
                        value={graphYearMin}
                        onChange={(e) => {
                          const v = Number(e.target.value);
                          setGraphYearMin(v);
                          if (v > graphYearMax) setGraphYearMax(v);
                        }}
                        className="w-full h-2 rounded-lg appearance-none bg-zinc-800 accent-zinc-500 cursor-pointer"
                      />
                      <input
                        type="range"
                        min={DATE_RANGE_MIN}
                        max={DATE_RANGE_MAX}
                        value={graphYearMax}
                        onChange={(e) => {
                          const v = Number(e.target.value);
                          setGraphYearMax(v);
                          if (v < graphYearMin) setGraphYearMin(v);
                        }}
                        className="w-full h-2 rounded-lg appearance-none bg-zinc-800 accent-zinc-500 cursor-pointer"
                      />
                    </div>
                  </div>
                  <button
                    type="submit"
                    disabled={graphLoading}
                    className="w-full py-2 rounded-lg bg-zinc-800 text-zinc-300 hover:bg-zinc-700 disabled:opacity-50 font-mono text-sm"
                  >
                    {graphLoading ? 'Loading...' : 'Go'}
                  </button>
                </form>
              </div>
              <div className="flex-1 min-h-0 overflow-y-auto p-4">
                <h4 className="font-mono text-xs font-semibold text-zinc-400 uppercase tracking-widest mb-3">
                  {selectedGraphNodeId ? 'Structured facts' : 'Select a node'}
                </h4>
                {selectedGraphNodeId && (
                  <ul className="space-y-3">
                    {graphEdges
                      .filter((e) => e.source === selectedGraphNodeId || e.target === selectedGraphNodeId)
                      .map((edge, i) => (
                        <li
                          key={`${edge.source}-${edge.target}-${edge.action}-${i}`}
                          className="text-sm text-zinc-400 font-mono border-l-2 border-zinc-700 pl-3 py-1"
                        >
                          <span className="text-zinc-300">{edge.source}</span>
                          {' — '}
                          {edge.action}
                          {edge.target && (
                            <>
                              {' → '}
                              <span className="text-zinc-300">{edge.target}</span>
                            </>
                          )}
                          {edge.timestamp && (
                            <span className="text-zinc-500 ml-2">({edge.timestamp})</span>
                          )}
                          {edge.location && (
                            <span className="text-zinc-500 ml-2">@ {edge.location}</span>
                          )}
                          {edge.doc_id && (
                            <button
                              type="button"
                              onClick={() => setSelectedDocId(edge.doc_id)}
                              className="ml-2 text-xs text-zinc-500 hover:text-zinc-300 underline"
                            >
                              View doc
                            </button>
                          )}
                        </li>
                      ))}
                  </ul>
                )}
                {selectedGraphNodeId && graphEdges.filter((e) => e.source === selectedGraphNodeId || e.target === selectedGraphNodeId).length === 0 && (
                  <p className="text-zinc-500 text-sm">No triples in this view for this node.</p>
                )}
              </div>
            </div>
          </div>
        ) : (
        <div className="flex flex-1 min-h-0 overflow-hidden">
          {mode === 'chat' && (
            <div className="hidden sm:flex w-56 lg:w-64 shrink-0 flex-col border-r border-zinc-800/50 bg-zinc-950/95 overflow-hidden">
              <div className="shrink-0 p-3 border-b border-zinc-800/50">
                <button
                  type="button"
                  onClick={handleNewChat}
                  className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-zinc-800 text-zinc-200 hover:bg-zinc-700 font-mono text-sm transition-colors"
                >
                  <MessageSquare className="w-4 h-4" />
                  New chat
                </button>
              </div>
              <div className="flex-1 min-h-0 overflow-y-auto p-2">
                {sessionsLoading ? (
                  <div className="flex items-center justify-center py-4 text-zinc-500 font-mono text-xs">
                    Loading...
                  </div>
                ) : sessions.length === 0 ? (
                  <p className="text-zinc-500 font-mono text-xs px-2 py-4">No past chats</p>
                ) : (
                  <ul className="space-y-1">
                    {sessions.map((s) => (
                      <li key={s.id}>
                        <div
                          role="button"
                          tabIndex={0}
                          onClick={() => handleSelectSession(s.id)}
                          onKeyDown={(e) => e.key === 'Enter' && handleSelectSession(s.id)}
                          className={`group flex items-start gap-2 rounded-lg px-3 py-2.5 text-left cursor-pointer transition-colors ${
                            currentSessionId === s.id ? 'bg-zinc-800 text-zinc-100' : 'hover:bg-zinc-800/60 text-zinc-300'
                          }`}
                        >
                          <span className="flex-1 min-w-0 truncate text-sm font-mono" title={s.title ?? undefined}>
                            {s.title || 'New chat'}
                          </span>
                          <button
                            type="button"
                            onClick={(e) => handleDeleteSession(s.id, e)}
                            className="shrink-0 p-1 rounded text-zinc-500 hover:text-zinc-300 hover:bg-zinc-700 opacity-0 group-hover:opacity-100 transition-opacity"
                            aria-label="Delete chat"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}
        <div className="flex flex-col md:flex-row flex-1 min-h-0 overflow-hidden min-w-0">
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden min-w-0">
        <AnimatePresence mode="wait">
          {((mode === 'chat' && chatMessages.length === 0) || (mode !== 'chat' && !hasSearched)) ? (
            <motion.div
              key="home"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20, filter: 'blur(10px)' }}
              transition={{ duration: 0.5 }}
              className="flex-1 flex flex-col items-center justify-center p-4 sm:p-6 max-w-3xl mx-auto w-full"
            >
              <h2 className="font-serif text-2xl sm:text-4xl md:text-5xl text-center mb-6 sm:mb-8 text-zinc-100 tracking-tight px-2">
                Search The Epstein Files
              </h2>

              <form onSubmit={handleSearch} className="w-full relative group">
                <div className="absolute inset-0 bg-zinc-800/20 blur-xl rounded-full group-hover:bg-zinc-700/30 transition-all duration-500"></div>
                <div className="relative glass-panel rounded-2xl flex items-center p-2 transition-all duration-300 focus-within:border-zinc-500 focus-within:bg-zinc-900/80">
                  <div className="pl-4 pr-2 text-zinc-500">
                    {mode === 'chat' ? <MessageSquare className="w-5 h-5" /> : <Search className="w-5 h-5" />}
                  </div>
                  <input
                    ref={inputRef}
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder={
                      mode === 'chat'
                        ? 'e.g. Who was involved with the island? Answers cite source documents.'
                        : 'e.g. Type a person or entity name to find relationships'
                    }
                    className="flex-1 bg-transparent border-none outline-none text-zinc-100 placeholder-zinc-600 py-4 px-2 text-base sm:text-lg min-w-0"
                  />
                  <button
                    type="submit"
                    disabled={!query.trim() || isSearching}
                    className="p-3 rounded-xl bg-zinc-800 text-zinc-300 hover:bg-zinc-700 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {isSearching ? <Loader2 className="w-5 h-5 animate-spin" /> : <ArrowRight className="w-5 h-5" />}
                  </button>
                </div>
              </form>

              <div className="mt-8 text-xs font-mono text-zinc-500">
                <span>
                  INDEX: {stats?.document_count != null ? stats.document_count.toLocaleString() : '—'} DOCS
                </span>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="results"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.4 }}
              className="flex-1 flex min-h-0 overflow-hidden"
            >
              <div className="flex-1 min-w-0 min-h-0 flex flex-col border-r border-zinc-800/50 bg-zinc-950/80 backdrop-blur-md relative">
                <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden p-4 sm:p-6 md:p-10 pb-24 sm:pb-28 scrollbar-visible">
                  <div className="max-w-3xl mx-auto">
                    {mode === 'chat' && chatMessages.length > 0 ? (
                      <>
                        <div className="space-y-8 mb-8">
                          {chatMessages.map((msg, idx) => (
                            <div key={idx} className={msg.role === 'user' ? 'flex justify-end' : ''}>
                              {msg.role === 'user' ? (
                                <div
                                  role="button"
                                  tabIndex={0}
                                  onClick={() => { if (chatMessages[idx + 1]?.role === 'assistant') setSelectedTurnIndex(idx + 1); }}
                                  onKeyDown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && chatMessages[idx + 1]?.role === 'assistant') { e.preventDefault(); setSelectedTurnIndex(idx + 1); } }}
                                  className={`rounded-xl px-4 py-3 max-w-[85%] cursor-pointer transition-colors ${
                                    effectiveTurnIndex === idx + 1 ? 'bg-zinc-700 ring-1 ring-zinc-500' : 'bg-zinc-800 hover:bg-zinc-700/60'
                                  }`}
                                  aria-label="View sources for this question"
                                >
                                  <p className="text-zinc-200 font-mono text-sm">{msg.content}</p>
                                </div>
                              ) : (
                                <div
                                  role="button"
                                  tabIndex={0}
                                  onClick={() => setSelectedTurnIndex(idx)}
                                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelectedTurnIndex(idx); } }}
                                  className={`prose prose-invert prose-zinc max-w-none cursor-pointer transition-all pl-3 -ml-3 border-l-2 ${
                                    effectiveTurnIndex === idx ? 'border-zinc-500' : 'border-transparent hover:border-zinc-700'
                                  }`}
                                  aria-label="View sources for this answer"
                                >
                                  <div className="text-lg leading-relaxed text-zinc-300">
                                    {msg.content ? (
                                      renderAnswerWithCitations(msg.content, {
                                        evidence: sourcesToEvidence(msg.sources ?? []),
                                        onCitationClick: (index) => {
                                          setSelectedTurnIndex(idx);
                                          setHighlightedEvidenceIndex(index);
                                        },
                                        isSelectedTurn: effectiveTurnIndex === idx,
                                        highlightedEvidenceIndex,
                                      })
                                    ) : (
                                      <span className="text-zinc-500 italic">No answer generated.</span>
                                    )}
                                  </div>
                                  {msg.triples && msg.triples.length > 0 && (
                                    <div className="mt-6 pt-4 border-t border-zinc-800">
                                      <h4 className="font-mono text-xs font-semibold text-zinc-400 uppercase tracking-widest mb-2">
                                        Structured facts
                                      </h4>
                                      <ul className="space-y-2">
                                        {msg.triples.map((t, i) => (
                                          <li key={i} className="text-sm text-zinc-400 font-mono border-l-2 border-zinc-700 pl-3 py-0.5">
                                            <span className="text-zinc-300">{t.actor}</span>
                                            {' — '}
                                            {t.action}
                                            {t.target && (
                                              <>
                                                {' → '}
                                                <span className="text-zinc-300">{t.target}</span>
                                              </>
                                            )}
                                            {t.timestamp && (
                                              <span className="text-zinc-500 ml-2">({t.timestamp})</span>
                                            )}
                                          </li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                        {isSearching && (
                          <div className="flex items-center space-x-3 text-zinc-400 font-mono text-sm animate-pulse mb-6">
                            <Loader2 className="w-4 h-4 animate-spin" />
                            <span>Accessing secure archives...</span>
                          </div>
                        )}
                      </>
                    ) : (
                      <>
                        <div className="mb-8 sm:mb-10">
                          <h3 className="text-lg sm:text-2xl font-serif text-zinc-100 mb-2 break-words">{activeQuery}</h3>
                          <div className="h-px w-full bg-gradient-to-r from-zinc-800 to-transparent"></div>
                        </div>

                        {isSearching ? (
                          <div className="flex items-center space-x-3 text-zinc-400 font-mono text-sm animate-pulse">
                            <Loader2 className="w-4 h-4 animate-spin" />
                            <span>Accessing secure archives...</span>
                          </div>
                        ) : (
                          <motion.div
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="prose prose-invert prose-zinc max-w-none"
                          >
                            {mode === 'chat' ? (
                              <>
                                <div className="text-lg leading-relaxed text-zinc-300">
                                  {answer ? (
                                    renderAnswerWithCitations(answer, {
                                      evidence,
                                      onCitationClick: (index) => setHighlightedEvidenceIndex(index),
                                      isSelectedTurn: true,
                                      highlightedEvidenceIndex,
                                    })
                                  ) : (
                                    <span className="text-zinc-500 italic">
                                      No answer was generated. See the source evidence below.
                                    </span>
                                  )}
                                </div>
                                {triples.length > 0 && (
                                  <div className="mt-10 pt-6 border-t border-zinc-800">
                                    <h4 className="font-mono text-xs font-semibold text-zinc-400 uppercase tracking-widest mb-3">
                                      Structured facts
                                    </h4>
                                    <ul className="space-y-3">
                                      {triples.map((t, i) => (
                                        <li
                                          key={i}
                                          className="text-sm text-zinc-400 font-mono border-l-2 border-zinc-700 pl-3 py-1"
                                        >
                                          <span className="text-zinc-300">{t.actor}</span>
                                          {' — '}
                                          {t.action}
                                          {t.target && (
                                            <>
                                              {' → '}
                                              <span className="text-zinc-300">{t.target}</span>
                                            </>
                                          )}
                                          {t.timestamp && (
                                            <span className="text-zinc-500 ml-2">({t.timestamp})</span>
                                          )}
                                          {t.location && (
                                            <span className="text-zinc-500 ml-2">@ {t.location}</span>
                                          )}
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                              </>
                            ) : (
                              <div className="text-zinc-400 font-mono text-sm">
                                Found {entityResults.length} entity match
                                {entityResults.length !== 1 ? 'es' : ''}. Review the panel.
                              </div>
                            )}
                          </motion.div>
                        )}
                      </>
                    )}
                    <div ref={messagesEndRef} className="h-20" />
                  </div>
                </div>

                <div className="p-4 sm:p-6 pb-safe bg-gradient-to-t from-zinc-950 via-zinc-950 to-transparent absolute bottom-0 left-0 right-0">
                  <form onSubmit={handleSearch} className="max-w-3xl mx-auto relative">
                    <div className="glass-panel rounded-xl flex items-center p-1.5 focus-within:border-zinc-600 focus-within:bg-zinc-900">
                      <input
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder={
                          mode === 'chat'
                            ? 'Ask a follow-up or new question...'
                            : 'e.g. Type a person or entity name to find relationships'
                        }
                        className="flex-1 bg-transparent border-none outline-none text-zinc-200 placeholder-zinc-600 py-3 px-4"
                      />
                      <button
                        type="submit"
                        disabled={!query.trim() || isSearching}
                        className="p-2.5 rounded-lg bg-zinc-800 text-zinc-300 hover:bg-zinc-700 disabled:opacity-50 transition-colors"
                      >
                        {isSearching ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
                      </button>
                    </div>
                  </form>
                </div>
              </div>

              <div className="w-full md:w-[400px] lg:w-[480px] min-h-[200px] md:min-h-0 shrink-0 flex flex-col bg-zinc-950/90 backdrop-blur-xl border-t md:border-t-0 md:border-l border-zinc-900 shadow-2xl z-20">
                <div className="shrink-0 p-4 border-b border-zinc-800/50 bg-zinc-900/50">
                  <div className="flex items-center justify-between">
                    <h3 className="font-mono text-xs font-semibold text-zinc-400 uppercase tracking-widest flex items-center">
                      <FileText className="w-3.5 h-3.5 mr-2" />
                      {mode === 'chat' ? 'Source Evidence' : 'Entity matches'}
                    </h3>
                    <span className="text-xs font-mono text-zinc-600">
                      {mode === 'chat' ? `${panelEvidence.length} files` : `${entityResults.length} names`}
                    </span>
                  </div>
                  {mode === 'chat' && panelQuery && (
                    <p className="mt-1.5 text-xs font-mono text-zinc-500 truncate" title={panelQuery}>
                      {panelQuery}
                    </p>
                  )}
                </div>

                <div
                  ref={evidencePanelScrollRef}
                  className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden p-4 space-y-4 scrollbar-visible"
                >
                  {isSearching ? (
                    <div className="space-y-4">
                      {[1, 2, 3].map((i) => (
                        <div
                          key={i}
                          className="h-32 rounded-lg bg-zinc-900/50 animate-pulse border border-zinc-800/30"
                       ></div>
                      ))}
                    </div>
                  ) : mode === 'chat' ? (
                    panelEvidence.length > 0 ? (
                      panelEvidence.map((item, idx) => (
                        <motion.div
                          key={`ev-${effectiveTurnIndex}-${item.doc_id}-${idx}`}
                          ref={idx === highlightedEvidenceIndex ? activeEvidenceCardRef : undefined}
                          initial={{ opacity: 0, x: 20 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: idx * 0.1 }}
                        >
                          <EvidenceCard
                            evidence={item}
                            index={idx}
                            isActive={highlightedEvidenceIndex === idx}
                            onClick={(doc_id) => {
                              setHighlightedEvidenceIndex(null);
                              setSelectedDocId(doc_id);
                            }}
                          />
                        </motion.div>
                      ))
                    ) : (
                      <div className="h-full flex flex-col items-center justify-center text-zinc-600 font-mono text-sm">
                        <FileText className="w-8 h-8 mb-3 opacity-20" />
                        <p>No evidence loaded.</p>
                      </div>
                    )
                  ) : entityResults.length > 0 ? (
                    <ul className="space-y-2">
                      {entityResults.map((r, i) => (
                        <li
                          key={`${r.canonical_name}-${i}`}
                          className="flex items-center justify-between p-3 rounded-lg bg-zinc-900/40 border border-zinc-800/50"
                        >
                          <span className="font-mono text-sm text-zinc-300">{r.canonical_name}</span>
                          <span className="text-xs font-mono text-zinc-500">{r.count} relations</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="h-full flex flex-col items-center justify-center text-zinc-600 font-mono text-sm">
                      <Search className="w-8 h-8 mb-3 opacity-20" />
                      <p>No entity matches.</p>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        </div>
        </div>
        </div>
        )}
      </main>

      <AnimatePresence>
        {selectedDocId && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/70 backdrop-blur-sm overscroll-contain"
            onClick={() => setSelectedDocId(null)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-zinc-900 border border-zinc-700 rounded-xl shadow-2xl max-w-3xl w-full max-h-[90vh] sm:max-h-[85vh] flex flex-col m-4 sm:m-0"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between p-4 border-b border-zinc-800">
                <span className="font-mono text-sm text-zinc-300 truncate">{selectedDocId}</span>
                <button
                  onClick={() => setSelectedDocId(null)}
                  className="p-2 rounded-lg text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 transition-colors"
                  aria-label="Close"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="flex-1 min-h-0 overflow-y-auto p-6 text-sm text-zinc-300 whitespace-pre-wrap font-serif">
                {documentLoading && (
                  <div className="flex items-center gap-2 text-zinc-500">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Loading document...
                  </div>
                )}
                {documentError && !documentLoading && (
                  <p className="text-red-400">{documentError}</p>
                )}
                {documentText !== null && !documentLoading && !documentError && (
                  <p className="leading-relaxed">{documentText || '(No text)'}</p>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
      <Analytics />
    </div>
  );
}
