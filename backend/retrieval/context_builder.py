"""Stage 5: assembles LLM prompt from retrieved chunks, filtered triples, and cite-doc_ids system instruction."""

from __future__ import annotations

import argparse
import json
from typing import Dict, List


SYSTEM_INSTRUCTION = """You are an assistant answering questions about the Epstein document corpus.
You are given:
- Retrieved document chunks, each labeled with its doc_id and index.
- Structured facts (triples) extracted from documents, labeled with doc_id.

Rules:
- Answer the user's question using only the provided chunks and triples.
- If the context is insufficient to answer, say you do not know based on the provided documents.
- Cite document ids inline in square brackets wherever you use evidence, e.g. [DOC_ID] or [DOC_ID1, DOC_ID2].
- Treat the structured triples as reliable facts; do not contradict them.
- Do not invent doc_ids or facts that are not supported by the context.
"""

MAX_CHUNKS = 10
MAX_CHARS_PER_CHUNK = 800
MAX_TRIPLES = 50


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def build_context_prompt(
    question: str, chunks: List[Dict], triples: List[Dict]
) -> Dict[str, object]:
    """Build the full LLM prompt string and aggregate doc_ids.

    Args:
        question: User's natural language question.
        chunks: List of chunk dicts from chunk_search.
        triples: List of triple dicts from triple_lookup.

    Returns:
        Dict with:
          - "prompt": str (full concatenation, for backward compatibility)
          - "system_prompt": str (for Claude system message)
          - "user_prompt": str (question + chunks + triples + "Answer:")
          - "doc_ids": List[str]
          - "chunk_count": int
          - "triple_count": int
    """
    clean_chunks: List[Dict] = []
    clean_triples: List[Dict] = []
    doc_ids_set = set()

    # Clean and collect chunks.
    for ch in chunks or []:
        doc_id = ch.get("doc_id")
        text = ch.get("chunk_text")
        if not doc_id or not text:
            continue
        idx = ch.get("chunk_index", 0)
        clean_chunks.append(
            {
                "doc_id": str(doc_id),
                "chunk_index": int(idx),
                "chunk_text": str(text),
            }
        )
        doc_ids_set.add(str(doc_id))

    # Sort by doc_id then chunk_index for readability.
    clean_chunks.sort(key=lambda c: (c["doc_id"], c["chunk_index"]))
    clean_chunks = clean_chunks[:MAX_CHUNKS]

    # Clean and collect triples.
    for t in triples or []:
        doc_id = t.get("doc_id")
        if not doc_id:
            continue
        actor = t.get("actor") or ""
        action = t.get("action") or ""
        target = t.get("target") or ""
        timestamp = t.get("timestamp") or ""
        location = t.get("location") or ""
        if not actor and not target and not action:
            continue
        clean_triples.append(
            {
                "doc_id": str(doc_id),
                "actor": str(actor),
                "action": str(action),
                "target": str(target),
                "timestamp": str(timestamp),
                "location": str(location),
            }
        )
        doc_ids_set.add(str(doc_id))

    clean_triples = clean_triples[:MAX_TRIPLES]

    # Build system prompt (instruction only).
    system_prompt = SYSTEM_INSTRUCTION.strip()

    # Build user prompt (question + context + answer placeholder).
    user_lines: List[str] = []
    user_lines.append("Question:")
    user_lines.append(question.strip())
    user_lines.append("")
    user_lines.append("Retrieved document chunks:")
    if clean_chunks:
        for ch in clean_chunks:
            doc_id = ch["doc_id"]
            idx = ch["chunk_index"]
            text = _truncate(ch["chunk_text"], MAX_CHARS_PER_CHUNK)
            user_lines.append(f"- [DOC_ID={doc_id}, INDEX={idx}] {text}")
    else:
        user_lines.append("- (none)")

    user_lines.append("")
    user_lines.append("Structured facts (triples):")
    if clean_triples:
        for t in clean_triples:
            parts = [f"[DOC_ID={t['doc_id']}]"]
            if t["actor"]:
                parts.append(f"ACTOR={t['actor']}")
            if t["action"]:
                parts.append(f"ACTION={t['action']}")
            if t["target"]:
                parts.append(f"TARGET={t['target']}")
            if t["timestamp"]:
                parts.append(f"TIME={t['timestamp']}")
            if t["location"]:
                parts.append(f"LOCATION={t['location']}")
            user_lines.append("- " + "; ".join(parts))
    else:
        user_lines.append("- (none)")

    user_lines.append("")
    user_lines.append("Answer:")

    user_prompt = "\n".join(user_lines)
    prompt = system_prompt + "\n\n" + user_prompt
    doc_ids = sorted(doc_ids_set)

    return {
        "prompt": prompt,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "doc_ids": doc_ids,
        "chunk_count": len(clean_chunks),
        "triple_count": len(clean_triples),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Stage 5: assemble an LLM prompt from retrieved chunks and triples."
        )
    )
    parser.add_argument(
        "--question",
        required=True,
        help="User question to embed in the prompt.",
    )
    parser.add_argument(
        "--chunks-file",
        type=str,
        help="Optional JSON file containing a list of chunk dicts.",
    )
    parser.add_argument(
        "--triples-file",
        type=str,
        help="Optional JSON file containing a list of triple dicts.",
    )

    args = parser.parse_args()

    if args.chunks_file:
        with open(args.chunks_file, "r", encoding="utf-8") as f:
            chunks = json.load(f)
    else:
        # Minimal dummy chunks for manual inspection.
        chunks = [
            {
                "doc_id": "DOC1",
                "chunk_index": 0,
                "chunk_text": "This is a sample chunk of text about Jeffrey Epstein.",
                "similarity": 0.9,
            }
        ]

    if args.triples_file:
        with open(args.triples_file, "r", encoding="utf-8") as f:
            triples = json.load(f)
    else:
        triples = [
            {
                "actor": "Jeffrey Epstein",
                "action": "met",
                "target": "Person X",
                "timestamp": "2005-01-01",
                "location": "Location Y",
                "doc_id": "DOC1",
            }
        ]

    result = build_context_prompt(args.question, chunks, triples)
    print("Doc IDs used:", result["doc_ids"])
    print()
    print("Prompt:\n")
    print(result["prompt"])

