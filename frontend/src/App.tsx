import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Search, MessageSquare, ArrowRight, Loader2, ShieldAlert, FileText, X, Network, LogOut } from 'lucide-react';
import { AuthModal } from './components/AuthModal';
import { EvidenceCard } from './components/EvidenceCard';
import { RelationshipGraph } from './components/RelationshipGraph';
import { api, sourcesToEvidence } from './api';
import { useAuth } from './contexts/AuthContext';
import type { AppMode, Evidence, EntitySearchResult, GraphEdge, GraphNode, StatsResponse, Triple } from './types';

/* Markdown components: structure (headers, lists, bold) with dark theme */
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

/** Intro: show epsteinGIF for one loop, then fade to ascii background. Tune to match GIF single-loop length. */
const EPSTEIN_INTRO_DURATION_MS = 5000;
const INTRO_FADE_DURATION_MS = 2500;

export default function App() {
  const { user, accessToken, signInWithGoogle, signOut, loading: authLoading } = useAuth();
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [mode, setMode] = useState<AppMode>('chat');
  const [query, setQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  // Chat results
  const [activeQuery, setActiveQuery] = useState('');
  const [answer, setAnswer] = useState<string>('');
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [triples, setTriples] = useState<Triple[]>([]);

  // Search mode: entity list (canonical_name + count)
  const [entityResults, setEntityResults] = useState<EntitySearchResult[]>([]);

  // Graph mode: graph data, filters, selected node, stats
  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([]);
  const [graphLoading, setGraphLoading] = useState(false);
  const [graphEntity, setGraphEntity] = useState('');
  const [graphKeywords, setGraphKeywords] = useState('');
  const [graphYearMin, setGraphYearMin] = useState(DATE_RANGE_MIN);
  const [graphYearMax, setGraphYearMax] = useState(DATE_RANGE_MAX);
  const [selectedGraphNodeId, setSelectedGraphNodeId] = useState<string | null>(null);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  // Graph entity suggestions: preset list (loaded once) + filtered suggestions
  const [graphEntityPresetList, setGraphEntityPresetList] = useState<EntitySearchResult[]>([]);
  const [graphEntityPresetLoading, setGraphEntityPresetLoading] = useState(false);
  const [graphEntitySuggestions, setGraphEntitySuggestions] = useState<EntitySearchResult[]>([]);
  const [graphEntitySuggestionsOpen, setGraphEntitySuggestionsOpen] = useState(false);
  const graphEntityContainerRef = useRef<HTMLDivElement>(null);

  // Document modal
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [documentText, setDocumentText] = useState<string | null>(null);
  const [documentLoading, setDocumentLoading] = useState(false);
  const [documentError, setDocumentError] = useState<string | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const evidencePanelScrollRef = useRef<HTMLDivElement>(null);

  // Intro: epsteinGIF once, then fade to ascii background
  type IntroPhase = 'intro' | 'fading' | 'done';
  const [introPhase, setIntroPhase] = useState<IntroPhase>('intro');
  const introTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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

  // Fetch stats on mount (for hero doc count), with retries if backend is starting
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

  /* Reset evidence panel scroll to top when results change so first source is fully visible */
  useEffect(() => {
    evidencePanelScrollRef.current?.scrollTo(0, 0);
  }, [evidence, entityResults]);

  // Fetch document text when modal opens
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

  // Load preset entity list once when entering graph mode
  useEffect(() => {
    if (mode !== 'graph') return;
    setGraphEntityPresetLoading(true);
    api
      .getEntityPreset()
      .then((res) => setGraphEntityPresetList(res.results ?? []))
      .catch(() => setGraphEntityPresetList([]))
      .finally(() => setGraphEntityPresetLoading(false));
  }, [mode]);

  // Filter preset list on keystroke (instant); fallback to server search when preset has no match
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
    // Fallback: preset capped or no match — call server search once
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

  // Click outside or Escape to close graph entity suggestions
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

    if (!user) {
      setShowAuthModal(true);
      return;
    }

    setIsSearching(true);
    setHasSearched(true);
    setActiveQuery(query);
    setAnswer('');
    setEvidence([]);
    setTriples([]);
    setEntityResults([]);
    setSelectedDocId(null);

    try {
        if (mode === 'chat') {
        const res = await api.chat(query, accessToken);
        setAnswer(res.answer);
        setEvidence(sourcesToEvidence(res.sources));
        setTriples(res.triples ?? []);
      } else {
        const res = await api.search(query);
        setEntityResults(res.results ?? []);
      }
    } catch (error) {
      console.error('Error fetching data:', error);
      const msg = error instanceof Error ? error.message : '';
      setAnswer(msg?.includes('Sign in') ? msg : 'Error connecting to the archive. Please check your clearance and try again.');
    } finally {
      setIsSearching(false);
      setQuery('');
    }
  };

  const handleLoadGraph = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!user) {
      setShowAuthModal(true);
      return;
    }
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

  const renderAnswerWithCitations = (text: string) => {
    if (!text) return null;
    const parts = text.split(/(\[\d+\])/g);
    return parts.map((part, i) => {
      const match = part.match(/\[(\d+)\]/);
      if (match) {
        return (
          <span
            key={i}
            className="inline-flex items-center justify-center w-5 h-5 rounded bg-zinc-800 text-xs font-mono text-zinc-300 border border-zinc-600 mx-1 cursor-pointer hover:bg-zinc-700 transition-colors align-middle"
            title={`View Evidence ${match[1]}`}
          >
            {match[1]}
          </span>
        );
      }
      if (!part.trim()) return <span key={i} />;
      return (
        <div key={i} className="answer-markdown">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
            {part}
          </ReactMarkdown>
        </div>
      );
    });
  };

  return (
    <div className="relative h-screen min-h-0 bg-zinc-950 text-zinc-200 font-sans overflow-hidden flex flex-col">
      {/* Intro: epsteinGIF (one loop) then fade to ascii background */}
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

      {/* Header — fixed at top, responsive on mobile */}
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
          <div className="flex items-center gap-2 sm:hidden">
            {user ? (
              <button
                type="button"
                onClick={() => signOut()}
                className="flex items-center justify-center p-2.5 rounded-md text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 transition-colors min-h-[44px] min-w-[44px]"
                aria-label="Log out"
              >
                <LogOut className="w-5 h-5" />
              </button>
            ) : (
              <button
                type="button"
                onClick={() => setShowAuthModal(true)}
                className="px-4 py-2.5 rounded-md text-sm font-medium bg-zinc-800 text-zinc-300 hover:bg-zinc-700 transition-colors min-h-[44px]"
              >
                Sign in
              </button>
            )}
          </div>
        </div>

        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 sm:gap-4">
          {user && (
            <div className="hidden sm:flex items-center gap-3 text-sm">
              <span className="text-zinc-400 font-mono truncate max-w-[180px]" title={user.email ?? undefined}>
                {user.email}
              </span>
              <button
                type="button"
                onClick={() => signOut()}
                className="flex items-center gap-1.5 px-3 py-2 rounded-md text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 transition-colors min-h-[44px]"
              >
                <LogOut className="w-4 h-4" />
                Log out
              </button>
            </div>
          )}
          {!user && (
            <div className="hidden sm:block">
              <button
                type="button"
                onClick={() => setShowAuthModal(true)}
                className="px-4 py-2 rounded-md text-sm font-medium bg-zinc-800 text-zinc-300 hover:bg-zinc-700 transition-colors min-h-[44px]"
              >
                Sign in
              </button>
            </div>
          )}
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
              onClick={() => {
                if (!user) {
                  setShowAuthModal(true);
                  return;
                }
                setMode('search');
              }}
              className={`flex items-center shrink-0 px-3 sm:px-4 py-2 sm:py-1.5 rounded-md text-sm font-medium transition-all min-h-[44px] sm:min-h-0 ${
                mode === 'search' ? 'bg-zinc-800 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200'
              }`}
              aria-label="Raw Search mode"
            >
              <Search className="w-4 h-4 sm:mr-2" />
              <span className="hidden sm:inline">Raw Search</span>
            </button>
            <button
              onClick={() => {
                if (!user) {
                  setShowAuthModal(true);
                  return;
                }
                setMode('graph');
              }}
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

      {/* Main Content Area — min-h-0 so flex children can scroll */}
      <main className="relative z-10 flex-1 min-h-0 flex flex-col overflow-hidden">
        {mode === 'graph' ? (
          <div className="flex-1 flex flex-col md:flex-row min-h-0 overflow-hidden">
            {/* Graph canvas */}
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
            {/* Graph sidebar: stats, filters, selected node triples — stacks below graph on mobile */}
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
        <div className="flex flex-col md:flex-row flex-1 min-h-0 overflow-hidden">
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden min-w-0">
        <AnimatePresence mode="wait">
          {!hasSearched ? (
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

              {mode === 'chat' && !user && !authLoading && (
                <div className="mt-4 flex items-center justify-center gap-3 text-sm">
                  <button
                    type="button"
                    onClick={() => setShowAuthModal(true)}
                    className="px-4 py-2 rounded-lg bg-zinc-800 text-zinc-200 hover:bg-zinc-700 font-mono text-sm transition-colors"
                  >
                    Sign in
                  </button>
                </div>
              )}

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
              {/* Left Column: Synthesis / Thread — scrollable independently */}
              <div className="flex-1 min-w-0 min-h-0 flex flex-col border-r border-zinc-800/50 bg-zinc-950/80 backdrop-blur-md relative">
                <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden p-4 sm:p-6 md:p-10 pb-24 sm:pb-28 scrollbar-visible">
                  <div className="max-w-3xl mx-auto">
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
                                renderAnswerWithCitations(answer)
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
                    <div ref={messagesEndRef} className="h-20" />
                  </div>
                </div>

                {/* Pinned Input */}
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

              {/* Right Column: Evidence / Entity Panel — scrollable independently, stacks below chat on mobile */}
              <div className="w-full md:w-[400px] lg:w-[480px] min-h-[200px] md:min-h-0 shrink-0 flex flex-col bg-zinc-950/90 backdrop-blur-xl border-t md:border-t-0 md:border-l border-zinc-900 shadow-2xl z-20">
                <div className="shrink-0 p-4 border-b border-zinc-800/50 flex items-center justify-between bg-zinc-900/50">
                  <h3 className="font-mono text-xs font-semibold text-zinc-400 uppercase tracking-widest flex items-center">
                    <FileText className="w-3.5 h-3.5 mr-2" />
                    {mode === 'chat' ? 'Source Evidence' : 'Entity matches'}
                  </h3>
                  <span className="text-xs font-mono text-zinc-600">
                    {mode === 'chat' ? `${evidence.length} files` : `${entityResults.length} names`}
                  </span>
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
                    evidence.length > 0 ? (
                      evidence.map((item, idx) => (
                        <motion.div
                          key={`ev-${item.doc_id}-${idx}`}
                          initial={{ opacity: 0, x: 20 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: idx * 0.1 }}
                        >
                          <EvidenceCard
                            evidence={item}
                            index={idx}
                            onClick={setSelectedDocId}
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
        )}
      </main>

      {/* Document modal */}
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

      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        onSignInWithGoogle={signInWithGoogle}
      />
    </div>
  );
}
