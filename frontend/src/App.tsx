import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Search, MessageSquare, ArrowRight, Loader2, ShieldAlert, FileText, X } from 'lucide-react';
import { CrypticBackground } from './components/CrypticBackground';
import { EvidenceCard } from './components/EvidenceCard';
import { api, sourcesToEvidence } from './api';
import type { AppMode, Evidence, EntitySearchResult, Triple } from './types';

export default function App() {
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

  // Document modal
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [documentText, setDocumentText] = useState<string | null>(null);
  const [documentLoading, setDocumentLoading] = useState(false);
  const [documentError, setDocumentError] = useState<string | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    if (hasSearched) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [answer, evidence, triples, entityResults]);

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

  const handleSearch = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!query.trim() || isSearching) return;

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
        const res = await api.chat(query);
        setAnswer(res.answer);
        setEvidence(sourcesToEvidence(res.sources));
        setTriples(res.triples ?? []);
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

  const renderAnswerWithCitations = (text: string) => {
    if (!text) return null;
    const parts = text.split(/(\[\d+\])/g);
    return parts.map((part, i) => {
      const match = part.match(/\[(\d+)\]/);
      if (match) {
        return (
          <span
            key={i}
            className="inline-flex items-center justify-center w-5 h-5 rounded bg-zinc-800 text-xs font-mono text-zinc-300 border border-zinc-600 mx-1 cursor-pointer hover:bg-zinc-700 transition-colors"
            title={`View Evidence ${match[1]}`}
          >
            {match[1]}
          </span>
        );
      }
      return <span key={i}>{part}</span>;
    });
  };

  return (
    <div className="relative min-h-screen bg-zinc-950 text-zinc-200 font-sans overflow-hidden flex flex-col">
      <CrypticBackground />

      {/* Header */}
      <header className="relative z-20 flex items-center justify-between p-6 border-b border-zinc-800/50 bg-zinc-950/50 backdrop-blur-sm">
        <div className="flex items-center space-x-3">
          <ShieldAlert className="w-6 h-6 text-zinc-400" />
          <h1 className="font-serif text-xl tracking-widest uppercase text-zinc-100 font-semibold">
            The Archive
          </h1>
        </div>

        <div className="flex bg-zinc-900/80 p-1 rounded-lg border border-zinc-800">
          <button
            onClick={() => setMode('chat')}
            className={`flex items-center px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
              mode === 'chat' ? 'bg-zinc-800 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <MessageSquare className="w-4 h-4 mr-2" />
            Synthesize
          </button>
          <button
            onClick={() => setMode('search')}
            className={`flex items-center px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
              mode === 'search' ? 'bg-zinc-800 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <Search className="w-4 h-4 mr-2" />
            Raw Search
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="relative z-10 flex-1 flex flex-col overflow-hidden">
        <AnimatePresence mode="wait">
          {!hasSearched ? (
            <motion.div
              key="home"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20, filter: 'blur(10px)' }}
              transition={{ duration: 0.5 }}
              className="flex-1 flex flex-col items-center justify-center p-6 max-w-3xl mx-auto w-full"
            >
              <h2 className="font-serif text-4xl md:text-5xl text-center mb-8 text-zinc-100 tracking-tight">
                Uncover the truth.
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
                        ? 'Ask a question about the records...'
                        : 'Search entity names...'
                    }
                    className="flex-1 bg-transparent border-none outline-none text-zinc-100 placeholder-zinc-600 py-4 px-2 text-lg"
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

              <div className="mt-8 flex gap-4 text-xs font-mono text-zinc-500">
                <span>SYSTEM: ONLINE</span>
                <span>|</span>
                <span>INDEX: 482,109 DOCS</span>
                <span>|</span>
                <span>CLEARANCE: LEVEL 4</span>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="results"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.4 }}
              className="flex-1 flex overflow-hidden"
            >
              {/* Left Column: Synthesis / Thread */}
              <div className="flex-1 min-w-0 flex flex-col border-r border-zinc-800/50 bg-zinc-950/80 backdrop-blur-md relative">
                <div className="flex-1 min-h-0 overflow-y-auto p-6 md:p-10 scrollbar-hide">
                  <div className="max-w-3xl mx-auto">
                    <div className="mb-10">
                      <h3 className="text-2xl font-serif text-zinc-100 mb-2">{activeQuery}</h3>
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
                <div className="p-6 bg-gradient-to-t from-zinc-950 via-zinc-950 to-transparent absolute bottom-0 left-0 right-0">
                  <form onSubmit={handleSearch} className="max-w-3xl mx-auto relative">
                    <div className="glass-panel rounded-xl flex items-center p-1.5 focus-within:border-zinc-600 focus-within:bg-zinc-900">
                      <input
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="Dig deeper..."
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

              {/* Right Column: Evidence / Entity Panel */}
              <div className="w-full md:w-[400px] lg:w-[480px] bg-zinc-950/90 backdrop-blur-xl flex flex-col border-l border-zinc-900 shadow-2xl z-20">
                <div className="p-4 border-b border-zinc-800/50 flex items-center justify-between bg-zinc-900/50">
                  <h3 className="font-mono text-xs font-semibold text-zinc-400 uppercase tracking-widest flex items-center">
                    <FileText className="w-3.5 h-3.5 mr-2" />
                    {mode === 'chat' ? 'Source Evidence' : 'Entity matches'}
                  </h3>
                  <span className="text-xs font-mono text-zinc-600">
                    {mode === 'chat' ? `${evidence.length} files` : `${entityResults.length} names`}
                  </span>
                </div>

                <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-hide">
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
      </main>

      {/* Document modal */}
      <AnimatePresence>
        {selectedDocId && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
            onClick={() => setSelectedDocId(null)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-zinc-900 border border-zinc-700 rounded-xl shadow-2xl max-w-3xl w-full max-h-[85vh] flex flex-col"
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
    </div>
  );
}
