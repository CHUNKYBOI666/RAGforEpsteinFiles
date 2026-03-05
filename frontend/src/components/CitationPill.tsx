import React from 'react';

interface CitationPillProps {
  index: number;
  label: string;
  citationNumber: number;
  onClick?: () => void;
  isHighlighted?: boolean;
}

/** Perplexity-style inline citation: pill with label + "+N", clickable to highlight evidence panel. */
export const CitationPill: React.FC<CitationPillProps> = ({
  index,
  label,
  citationNumber,
  onClick,
  isHighlighted = false,
}) => {
  const displayLabel = label.length > 24 ? label.slice(0, 21) + '…' : label;
  const ariaLabel = `Source ${citationNumber}: ${label}. Click to highlight in evidence panel.`;

  return (
    <span
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onClick={onClick ? (e) => { e.preventDefault(); onClick(); } : undefined}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onClick();
              }
            }
          : undefined
      }
      className={`inline-flex items-center gap-1 mx-1 px-2 py-0.5 rounded-md text-xs font-medium align-middle whitespace-nowrap transition-colors ${
        isHighlighted
          ? 'bg-zinc-600 text-zinc-100 ring-1 ring-zinc-500'
          : 'bg-zinc-700/80 text-zinc-300 hover:bg-zinc-600/90'
      } ${onClick ? 'cursor-pointer' : ''}`}
      title={`View evidence ${citationNumber}: ${label}`}
      aria-label={ariaLabel}
    >
      <span className="truncate max-w-[140px]">{displayLabel}</span>
      <span className="text-zinc-400 shrink-0">+{citationNumber}</span>
    </span>
  );
};
