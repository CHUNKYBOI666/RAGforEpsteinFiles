"""Stage 1: entity alias lookup — expand query with canonical + aliases from entity_aliases table."""

from __future__ import annotations

import argparse
import importlib.util
import re
from pathlib import Path
from typing import List, Set

from supabase import Client, create_client

# Load backend/.env then backend/config.py so credentials work from any cwd
_backend_dir = Path(__file__).resolve().parent.parent
_dotenv_path = _backend_dir / ".env"
if _dotenv_path.exists():
    from dotenv import load_dotenv

    load_dotenv(_dotenv_path, override=True)

_config_py = _backend_dir / "config.py"
_spec = importlib.util.spec_from_file_location("_env_config", _config_py)
_env_config = importlib.util.module_from_spec(_spec)
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(_env_config)

SUPABASE_URL: str = getattr(_env_config, "SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY: str = getattr(_env_config, "SUPABASE_SERVICE_ROLE_KEY", "")

# Stopwords to drop when tokenizing multi-word queries (so "Trump", "Epstein", "minors" surface).
_STOPWORDS: Set[str] = {
    "a", "an", "and", "any", "are", "did", "do", "does", "has", "have", "is",
    "or", "that", "the", "to", "was", "were", "what", "when", "where", "which",
    "who", "why",
}
_MIN_TOKEN_LEN = 2


def _validate_config() -> None:
    missing = []
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_SERVICE_ROLE_KEY:
        missing.append("SUPABASE_SERVICE_ROLE_KEY")
    if missing:
        joined = ", ".join(missing)
        raise SystemExit(
            f"Missing required configuration values: {joined}. "
            "Set them in backend/.env or your environment."
        )


def _create_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def _add_term_unique(terms: List[str], seen_lower: Set[str], term: str) -> None:
    cleaned = term.strip()
    if not cleaned:
        return
    key = cleaned.lower()
    if key in seen_lower:
        return
    seen_lower.add(key)
    terms.append(cleaned)


def _tokenize_query(query: str) -> List[str]:
    """Split query into tokens: non-empty, min length, not stopwords. Includes full query."""
    stripped = query.strip()
    if not stripped:
        return []
    tokens: List[str] = []
    seen_lower: Set[str] = set()
    # Include full query first for backward compatibility (single-name queries).
    if len(stripped) >= _MIN_TOKEN_LEN and stripped.lower() not in _STOPWORDS:
        tokens.append(stripped)
        seen_lower.add(stripped.lower())
    # Split on non-alphanumeric (keep words and numbers).
    for part in re.split(r"[^\w]+", stripped):
        s = part.strip()
        if len(s) < _MIN_TOKEN_LEN:
            continue
        key = s.lower()
        if key in _STOPWORDS or key in seen_lower:
            continue
        seen_lower.add(key)
        tokens.append(s)
    return tokens


def _escape_for_postgrest_quoted(s: str) -> str:
    """Escape string for use inside double-quoted PostgREST filter value (\\ and \")."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def expand_query(query: str) -> List[str]:
    """Expand a user query with all known aliases from entity_aliases.

    Multi-word queries are tokenized; each token (and the full query) is used
    to match entity_aliases (original_name / canonical_name). All matched
    canonical entities and their aliases are returned, with the original
    query first. If no entity matches, returns [stripped query].
    """
    _validate_config()

    stripped = query.strip()
    if not stripped:
        return []

    supabase = _create_supabase_client()
    tokens = _tokenize_query(stripped)
    if not tokens:
        return [stripped]

    canonical_names: Set[str] = set()
    for token in tokens:
        like_pattern = f"%{token}%"
        escaped = _escape_for_postgrest_quoted(like_pattern)
        or_filter = f'original_name.ilike."{escaped}",canonical_name.ilike."{escaped}"'
        resp = (
            supabase.table("entity_aliases")
            .select("original_name, canonical_name")
            .or_(or_filter)
            .limit(50)
            .execute()
        )
        rows = resp.data or []
        for row in rows:
            canonical = (row.get("canonical_name") or "").strip()
            if canonical:
                canonical_names.add(canonical)

    # If we did not recognize any canonical entity, just return the raw query.
    if not canonical_names:
        return [stripped]

    # Fetch all aliases for the matched canonical entities.
    resp_all = (
        supabase.table("entity_aliases")
        .select("original_name, canonical_name")
        .in_("canonical_name", list(canonical_names))
        .limit(1000)
        .execute()
    )

    alias_rows = resp_all.data or []

    expanded: List[str] = []
    seen_lower: Set[str] = set()

    # Always include the original query first.
    _add_term_unique(expanded, seen_lower, stripped)

    for row in alias_rows:
        original = row.get("original_name") or ""
        canonical = row.get("canonical_name") or ""
        _add_term_unique(expanded, seen_lower, original)
        _add_term_unique(expanded, seen_lower, canonical)

    # Include any token that wasn't already added (e.g. "minors" for keyword-style matching).
    for token in tokens:
        _add_term_unique(expanded, seen_lower, token)

    # Cap to avoid huge OR filters in triple lookup / triple candidate search (Supabase limits).
    MAX_EXPANDED_TERMS = 150
    if len(expanded) > MAX_EXPANDED_TERMS:
        expanded = expanded[:MAX_EXPANDED_TERMS]

    return expanded


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Stage 1: expand a query string using the entity_aliases table "
            "in Supabase."
        )
    )
    parser.add_argument(
        "query",
        nargs="?",
        default="Jeffrey Epstein",
        help='Query string to expand (default: "Jeffrey Epstein").',
    )
    args = parser.parse_args()

    results = expand_query(args.query)
    print(f"Input query: {args.query}")
    print("Expanded terms:")
    for term in results:
        print(f"- {term}")

