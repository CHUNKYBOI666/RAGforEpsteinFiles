"""
API tests: /search and /chat (chat may 503 if no LLM config).
Requires Qdrant index (e.g. run scripts/run_ingestion.py --index-test first).
"""
import pytest
from fastapi.testclient import TestClient

from src.api.app import app

client = TestClient(app)


def test_search_empty_query_returns_422():
    r = client.post("/search", json={"query": "", "top_k": 5})
    assert r.status_code == 422


def test_search_missing_query_returns_422():
    r = client.post("/search", json={"top_k": 5})
    assert r.status_code == 422


def test_search_valid_returns_200_and_structure():
    r = client.post("/search", json={"query": "flight log", "top_k": 3})
    if r.status_code == 503:
        pytest.skip("Index or retrieval unavailable (run ingestion --index-test)")
    assert r.status_code == 200
    data = r.json()
    assert "hits" in data and "citations" in data
    assert isinstance(data["hits"], list) and isinstance(data["citations"], list)
    assert len(data["hits"]) <= 3
    if data["hits"]:
        assert "score" in data["hits"][0] and "payload" in data["hits"][0]
        assert "doc_id" in data["citations"][0] and "snippet" in data["citations"][0]


def test_chat_empty_query_returns_422():
    r = client.post("/chat", json={"query": ""})
    assert r.status_code == 422


def test_chat_valid_returns_answer_or_503_or_502():
    r = client.post("/chat", json={"query": "What do the documents say about flights?", "top_k": 2})
    # 200 if LLM OK, 503 if no LLM config, 502 if LLM errors (e.g. rate limit)
    assert r.status_code in (200, 502, 503)
    if r.status_code == 200:
        data = r.json()
        assert "answer" in data and "citations" in data
        assert isinstance(data["answer"], str) and isinstance(data["citations"], list)
