import re

from fastapi import HTTPException, status

INJECTION_PATTERNS = [
    r"ignore\s+(previous|all|your|prior)\s+instructions",
    r"system\s*prompt",
    r"you\s+are\s+now",
    r"act\s+as\s+",
    r"\bDAN\b",
    r"jailbreak",
    r"forget\s+(your|all)",
    r"disregard\s+(previous|all|your)",
    r"pretend\s+you",
    r"roleplay\s+as",
    r"override\s+(your|the)\s+(instructions|prompt|rules)",
    r"new\s+instructions?:",
    r"</?(system|prompt|instruction)>",
]

_compiled = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def check_input(query: str) -> None:
    """Raise HTTPException 400 if query contains injection patterns."""
    for pattern in _compiled:
        if pattern.search(query):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query contains disallowed content.",
            )
