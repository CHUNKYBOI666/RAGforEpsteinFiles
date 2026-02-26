"""
Document cleaning layer. Runs between Load and Chunk to improve text quality.

Public API:
    clean_document(doc: dict) -> dict
        Input:  doc with doc_id, text, source_ref, doc_type, doc_title, doc_date.
        Output: same dict with text replaced by cleaned string and metrics attached.

Cleaning steps (v3, doc-type-aware):
    Default/court_filing/letter/biography/media_article: normalize, collapse WS,
    split → [book_excerpt: join OCR column fragments] → join continuation lines,
    strip line-edge punctuation, drop OCR/header/dedupe/short, rejoin.
    financial_document: normalize, collapse WS, split, drop boilerplate only (OMB, Page N of N), rejoin.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

CLEANING_VERSION = "v3"


# Sentence terminators: do not join after these
_SENTENCE_END_CHARS = '.!?:;"'


# Doc-type presets (used by get_config_for_doc_type)
_FINANCIAL_DOC_TYPE = "financial_document"
_BOOK_EXCERPT_DOC_TYPE = "book_excerpt"
_COURT_FILING_DOC_TYPE = "court_filing"
_LETTER_DOC_TYPE = "letter"
_BIOGRAPHY_DOC_TYPE = "biography"
_MEDIA_ARTICLE_DOC_TYPE = "media_article"
_OTHER_DOC_TYPE = "other"


@dataclass
class CleaningConfig:
    """Tunable thresholds for heuristic cleaning. No magic numbers in logic."""

    ocr_noise_ratio: float = 0.30
    min_line_chars: int = 30
    max_repeated_line_count: int = 2
    max_paragraph_newlines: int = 2
    join_continuation_lines: bool = True
    continuation_short_line_chars: int = 60
    max_header_chars: int = 50
    strip_line_edge_punctuation: bool = True
    doc_type: str | None = None
    join_ocr_column_fragments: bool = False
    conservative_financial: bool = False
    # Patterns that protect short but meaningful lines (evidence-like only)
    keep_patterns: list[re.Pattern] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.keep_patterns:
            self.keep_patterns = [
                re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"),
                re.compile(r"@"),
                re.compile(r"^[\s]*[-*]\s+[a-zA-Z0-9]"),
            ]


_DEFAULT_CONFIG = CleaningConfig()


def get_config_for_doc_type(doc_type: str | None) -> CleaningConfig:
    """Return a CleaningConfig preset for the given doc_type. Unknown/None gets default (v2-like)."""
    if not doc_type or not str(doc_type).strip():
        return CleaningConfig()
    dt = str(doc_type).strip().lower()
    if dt == _FINANCIAL_DOC_TYPE:
        return CleaningConfig(
            doc_type=dt,
            join_continuation_lines=False,
            join_ocr_column_fragments=False,
            conservative_financial=True,
            strip_line_edge_punctuation=False,
        )
    if dt == _BOOK_EXCERPT_DOC_TYPE:
        return CleaningConfig(
            doc_type=dt,
            join_continuation_lines=True,
            join_ocr_column_fragments=True,
            conservative_financial=False,
            strip_line_edge_punctuation=True,
        )
    if dt in (_COURT_FILING_DOC_TYPE, _LETTER_DOC_TYPE, _BIOGRAPHY_DOC_TYPE, _MEDIA_ARTICLE_DOC_TYPE, _OTHER_DOC_TYPE):
        return CleaningConfig(
            doc_type=dt,
            join_continuation_lines=True,
            join_ocr_column_fragments=False,
            conservative_financial=False,
            strip_line_edge_punctuation=True,
        )
    return CleaningConfig()


# ---------------------------------------------------------------------------
# Internal helpers — one per cleaning step
# ---------------------------------------------------------------------------

def _normalize_encoding(text: str) -> str:
    """NFKC normalization: fix weird unicode, broken quotes, odd spacing."""
    return unicodedata.normalize("NFKC", text)


def _collapse_whitespace(text: str, max_newlines: int) -> str:
    """Replace runs of spaces with single space; cap consecutive newlines."""
    text = re.sub(r"[^\S\n]+", " ", text)
    limit = "\n" * max_newlines
    text = re.sub(r"\n{" + str(max_newlines + 1) + r",}", limit, text)
    return text


def _is_ocr_garbage(line: str, threshold: float) -> bool:
    """True if the fraction of non-alphanumeric (excluding spaces) chars exceeds threshold."""
    stripped = line.strip()
    if not stripped:
        return True
    total = len(stripped)
    alnum_or_space = sum(1 for c in stripped if c.isalnum() or c == " ")
    noise_ratio = 1.0 - (alnum_or_space / total)
    return noise_ratio > threshold


def _matches_keep_pattern(line: str, patterns: list[re.Pattern]) -> bool:
    """True if the line matches any keep pattern (evidence-like content)."""
    return any(p.search(line) for p in patterns)


def _drop_ocr_lines(lines: list[str], threshold: float) -> list[str]:
    """Remove lines that are mostly non-alphanumeric (OCR junk)."""
    return [ln for ln in lines if not _is_ocr_garbage(ln, threshold)]


def _dedupe_repeated_lines(lines: list[str], max_count: int) -> list[str]:
    """Keep only the first N occurrences of any repeated line (headers/footers)."""
    counts: Counter[str] = Counter()
    result: list[str] = []
    for ln in lines:
        key = ln.strip().lower()
        if not key:
            result.append(ln)
            continue
        counts[key] += 1
        if counts[key] <= max_count:
            result.append(ln)
    return result


def _drop_short_garbage(
    lines: list[str],
    min_chars: int,
    keep_patterns: list[re.Pattern],
) -> list[str]:
    """Drop lines shorter than min_chars unless they match a keep pattern."""
    result: list[str] = []
    for ln in lines:
        if len(ln.strip()) >= min_chars:
            result.append(ln)
        elif _matches_keep_pattern(ln, keep_patterns):
            result.append(ln)
    return result


def _is_continuation_candidate(
    current: str,
    next_line: str,
    short_line_chars: int,
) -> bool:
    """True if current line should be joined with next (mid-sentence break)."""
    curr = current.strip()
    nxt = next_line.strip()
    if not nxt:
        return False
    if not curr:
        return False
    if curr[-1] in _SENTENCE_END_CHARS:
        return False
    next_starts_lower = nxt[0].islower() if nxt else False
    if next_starts_lower:
        return True
    if curr.endswith(",") or curr.endswith("-"):
        return True
    if len(curr) < short_line_chars and next_starts_lower:
        return True
    return False


def _join_continuation_lines(
    lines: list[str],
    cfg: CleaningConfig,
) -> list[str]:
    """Join lines that are mid-sentence continuations (de-OCR reconstruction)."""
    if not cfg.join_continuation_lines or not lines:
        return lines
    out: list[str] = []
    i = 0
    short_chars = cfg.continuation_short_line_chars
    while i < len(lines):
        line = lines[i]
        while i + 1 < len(lines):
            next_line = lines[i + 1]
            if next_line.strip() and _is_continuation_candidate(
                line, next_line, short_chars
            ):
                line = (line.rstrip() + " " + next_line.lstrip()).strip()
                i += 1
            else:
                break
        out.append(line)
        i += 1
    return out


def _strip_line_edge_punctuation(lines: list[str]) -> list[str]:
    """Strip leading non-alpha; strip trailing non-alpha but keep single . ! ? ; \" """
    result: list[str] = []
    for ln in lines:
        s = ln.strip()
        if not s:
            result.append(ln)
            continue
        start = 0
        while start < len(s) and not s[start].isalpha():
            start += 1
        end = len(s)
        while end > start and not s[end - 1].isalpha():
            end -= 1
        if end < len(s) and (len(s) - end) == 1 and s[end] in _SENTENCE_END_CHARS:
            end = len(s)
        if start >= end:
            result.append("")
        else:
            result.append(s[start:end])
    return result


def _is_header_like(line: str, max_header_chars: int) -> bool:
    """True if line looks like a short all-caps header/title (OCR garbage)."""
    stripped = line.strip()
    if not stripped or len(stripped) > max_header_chars:
        return False
    letters = [c for c in stripped if c.isalpha()]
    if not letters:
        return False
    upper = sum(1 for c in letters if c.isupper())
    return upper / len(letters) >= 0.80


def _drop_header_like_lines(lines: list[str], max_header_chars: int) -> list[str]:
    """Remove short all-caps lines (title/header junk)."""
    return [ln for ln in lines if not _is_header_like(ln, max_header_chars)]


# Lowercase fragment at line start: 3-10 letters then space or EOL (column-split OCR)
_OCR_FRAGMENT_PATTERN = re.compile(r"^[a-z]{3,10}(?:\s|$)")


def _is_ocr_column_fragment(line: str) -> bool:
    """True if line (stripped) starts with a lowercase word fragment 3-10 chars (column-split)."""
    s = line.strip()
    if not s or not s[0].islower():
        return False
    return bool(_OCR_FRAGMENT_PATTERN.match(s))


def _join_ocr_column_fragments(lines: list[str]) -> list[str]:
    """Merge lines that start with a lowercase 3-10 char fragment onto the previous non-empty line.
    Fragment and any rest are joined with spaces (e.g. 'criminal' + 'irs' -> 'criminal irs').
    """
    if not lines:
        return lines
    out: list[str] = []
    for ln in lines:
        stripped = ln.strip()
        if not stripped:
            out.append(ln)
            continue
        if _is_ocr_column_fragment(ln) and out:
            prev = out[-1]
            if prev.strip():
                match = _OCR_FRAGMENT_PATTERN.match(stripped)
                if match:
                    fragment = match.group(0).strip()
                    rest = stripped[len(fragment) :].strip()
                    merged = prev.rstrip() + " " + fragment
                    if rest:
                        merged += " " + rest
                    out[-1] = merged
                    continue
        out.append(ln)
    return out


# Boilerplate patterns for financial forms only (drop these lines, keep tabular content)
_FINANCIAL_BOILERPLATE_PATTERNS = [
    re.compile(r"(?i)^\s*OMB\s+(No\.|Control\s+No\.?)", re.IGNORECASE),
    re.compile(r"(?i)^\s*Page\s+\d+\s+of\s+\d+\s*$"),
    re.compile(r"(?i)^\s*OMB\s+Approval"),
]


def _is_financial_boilerplate(line: str) -> bool:
    """True if line is known financial form boilerplate (OMB, Page N of N)."""
    stripped = line.strip()
    if not stripped:
        return False
    return any(p.search(stripped) for p in _FINANCIAL_BOILERPLATE_PATTERNS)


def _drop_financial_boilerplate_only(lines: list[str]) -> list[str]:
    """Drop only OMB notice, Page N of N, and similar; keep all tabular rows."""
    return [ln for ln in lines if not _is_financial_boilerplate(ln)]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def clean_text(raw_text: str, config: CleaningConfig | None = None) -> str:
    """
    Run the full cleaning pipeline on a raw text string.
    Returns the cleaned string. Pipeline branches on config.conservative_financial
    and config.join_ocr_column_fragments.
    """
    cfg = config or _DEFAULT_CONFIG

    text = _normalize_encoding(raw_text)
    text = _collapse_whitespace(text, cfg.max_paragraph_newlines)

    lines = text.split("\n")

    if cfg.conservative_financial:
        lines = _drop_financial_boilerplate_only(lines)
        text = "\n".join(lines)
        text = _collapse_whitespace(text, cfg.max_paragraph_newlines)
        return text.strip()

    if cfg.join_ocr_column_fragments:
        lines = _join_ocr_column_fragments(lines)

    lines = _join_continuation_lines(lines, cfg)
    if cfg.strip_line_edge_punctuation:
        lines = _strip_line_edge_punctuation(lines)
    lines = _drop_ocr_lines(lines, cfg.ocr_noise_ratio)
    lines = _drop_header_like_lines(lines, cfg.max_header_chars)
    lines = _dedupe_repeated_lines(lines, cfg.max_repeated_line_count)
    lines = _drop_short_garbage(lines, cfg.min_line_chars, cfg.keep_patterns)

    text = "\n".join(lines)
    text = _collapse_whitespace(text, cfg.max_paragraph_newlines)
    return text.strip()


def clean_document(
    doc: dict[str, Any],
    config: CleaningConfig | None = None,
) -> dict[str, Any]:
    """
    Clean a single document dict (doc-in, doc-out).

    Replaces doc["text"] with the cleaned version and attaches cleaning metrics:
        cleaning_applied (bool), original_length (int),
        cleaned_length (int), cleaning_ratio (float).
    When config is None, uses get_config_for_doc_type(doc.get("doc_type")).
    """
    raw_text = doc.get("text") or ""
    if not isinstance(raw_text, str):
        raw_text = str(raw_text)

    if config is None:
        config = get_config_for_doc_type(doc.get("doc_type"))

    original_length = len(raw_text)
    cleaned = clean_text(raw_text, config)
    cleaned_length = len(cleaned)

    doc["text"] = cleaned
    doc["cleaning_applied"] = True
    doc["original_length"] = original_length
    doc["cleaned_length"] = cleaned_length
    doc["cleaning_ratio"] = round(cleaned_length / original_length, 4) if original_length else 1.0
    return doc
