import React from 'react';
import { Evidence } from '../types';
import { FileText, Calendar, Link as LinkIcon } from 'lucide-react';

interface EvidenceCardProps {
  evidence: Evidence;
  index: number;
  isActive?: boolean;
}

export const EvidenceCard: React.FC<EvidenceCardProps> = ({ evidence, index, isActive }) => {
  return (
    <div 
      className={`p-4 rounded-lg border transition-all duration-300 ${
        isActive 
          ? 'bg-zinc-800/80 border-zinc-600 shadow-lg shadow-black/50' 
          : 'bg-zinc-900/40 border-zinc-800/50 hover:bg-zinc-800/40'
      }`}
    >
      <div className="flex justify-between items-start mb-3">
        <div className="flex items-center space-x-2">
          <span className="flex items-center justify-center w-5 h-5 rounded bg-zinc-800 text-xs font-mono text-zinc-400 border border-zinc-700">
            {index + 1}
          </span>
          <span className="font-mono text-xs font-semibold text-zinc-300 tracking-wider">
            {evidence.doc_id}
          </span>
        </div>
        <div className="flex items-center text-zinc-500 text-xs font-mono">
          <Calendar className="w-3 h-3 mr-1" />
          {evidence.date}
        </div>
      </div>
      
      <div className="pl-3 border-l-2 border-zinc-700 mb-3">
        <p className="text-sm text-zinc-300 leading-relaxed font-serif italic">
          "{evidence.snippet}"
        </p>
      </div>
      
      <div className="flex items-center text-xs text-zinc-500 font-mono mt-2 pt-2 border-t border-zinc-800/50">
        <LinkIcon className="w-3 h-3 mr-1.5" />
        <span className="truncate">{evidence.source_ref}</span>
        {evidence.score && (
          <span className="ml-auto text-zinc-600">
            Match: {(evidence.score * 100).toFixed(0)}%
          </span>
        )}
      </div>
    </div>
  );
};
