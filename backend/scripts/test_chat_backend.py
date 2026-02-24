"""
Test /search and /chat from the backend (no frontend). Prints response JSON.
Requires the API server to be running on port 8000 (e.g. uvicorn src.api.app:app --port 8000).
Run from backend/ with: PYTHONPATH=. .venv/bin/python scripts/test_chat_backend.py [--search-only | --chat-only]
"""
import argparse
import json
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

# Default base URL for the API
DEFAULT_BASE_URL = "http://127.0.0.1:8000"


def request(method: str, path: str, body: dict | None = None, base_url: str = DEFAULT_BASE_URL) -> tuple[int, dict]:
    url = f"{base_url.rstrip('/')}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=30) as resp:
            body = resp.read().decode()
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                data = {"_raw": body}
            return resp.status, data
    except URLError as e:
        print(f"Request failed: {e}", file=sys.stderr)
        print("Ensure the API is running: cd backend && PYTHONPATH=. .venv/bin/python -m uvicorn src.api.app:app --port 8000", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    parser = argparse.ArgumentParser(description="Test /search and /chat endpoints (no frontend)")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="API base URL")
    parser.add_argument("--search-only", action="store_true", help="Only call POST /search")
    parser.add_argument("--chat-only", action="store_true", help="Only call POST /chat")
    parser.add_argument("--query", default="travel flights", help="Query for search and chat")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")

    if not args.chat_only:
        print("--- POST /search ---")
        status, data = request("POST", "/search", {"query": args.query}, base_url=base)
        print(f"Status: {status}")
        print(json.dumps(data, indent=2))
        print()

    if not args.search_only:
        print("--- POST /chat ---")
        status, data = request("POST", "/chat", {"query": args.query}, base_url=base)
        print(f"Status: {status}")
        print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
