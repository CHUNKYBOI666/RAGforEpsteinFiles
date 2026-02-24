"""
FastAPI app: POST /search (retrieval only) and POST /chat (retrieval + LLM).
Retrieval logic lives in src.retrieval; this module only wires HTTP to retrieval and LLM.
"""
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.retrieval import format_retrieval_result, search

logger = logging.getLogger(__name__)

app = FastAPI(title="RAGforEFN API", description="Search and chat over document index")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request/response models ---


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query")
    top_k: int = Field(10, ge=1, le=100, description="Max number of hits")
    date_from: str | None = Field(None, description="Filter: doc_date >= this (ISO date string)")
    date_to: str | None = Field(None, description="Filter: doc_date <= this (ISO date string)")
    doc_type: str | None = Field(None, description="Filter by doc_type (e.g. email, court_filing, biography)")


class SearchResponse(BaseModel):
    hits: list[dict]
    citations: list[dict]
    results: list[dict]
    total_found: int


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User question")
    top_k: int = Field(10, ge=1, le=100, description="Max chunks for context")
    date_from: str | None = Field(None, description="Filter: doc_date >= this (ISO date string)")
    date_to: str | None = Field(None, description="Filter: doc_date <= this (ISO date string)")
    doc_type: str | None = Field(None, description="Filter by doc_type (e.g. email, court_filing, biography)")


class ChatResponse(BaseModel):
    answer: str
    citations: list[dict]


# --- Endpoints ---


@app.post("/search", response_model=SearchResponse)
def post_search(body: SearchRequest) -> SearchResponse:
    """Retrieve top-k chunks for a query; return hits and citations. No LLM."""
    try:
        hits = search(
            body.query,
            top_k=body.top_k,
            date_from=body.date_from,
            date_to=body.date_to,
            doc_type=body.doc_type or None,
        )
        result = format_retrieval_result(hits)
        citations = result["citations"]
        return SearchResponse(
            hits=hits,
            citations=citations,
            results=citations,
            total_found=len(hits),
        )
    except Exception as e:
        logger.exception("Search failed")
        raise HTTPException(status_code=503, detail="Search temporarily unavailable") from e


@app.post("/chat", response_model=ChatResponse)
def post_chat(body: ChatRequest) -> ChatResponse:
    """Retrieve chunks, build context, call LLM, return answer and citations."""
    from config import settings

    try:
        hits = search(
            body.query,
            top_k=body.top_k,
            date_from=body.date_from,
            date_to=body.date_to,
            doc_type=body.doc_type or None,
        )
        result = format_retrieval_result(hits)
        context = result["context_for_llm"]
        citations = result["citations"]
    except Exception as e:
        logger.exception("Retrieval failed in chat")
        raise HTTPException(status_code=503, detail="Retrieval temporarily unavailable") from e

    # LLM: require API key for OpenAI; allow local with OPENAI_API_BASE only
    api_key = settings.OPENAI_API_KEY
    base_url = settings.OPENAI_API_BASE
    if settings.LLM_PROVIDER == "openai" and not api_key and not base_url:
        raise HTTPException(
            status_code=503,
            detail="LLM not configured: set OPENAI_API_KEY or OPENAI_API_BASE for local",
        )

    prompt = _build_chat_prompt(context, body.query)
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key or "not-needed", base_url=base_url)
        response = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        answer = (response.choices[0].message.content or "").strip()
    except Exception as e:
        logger.exception("LLM call failed")
        return ChatResponse(
            answer="[Unable to generate an answer; see sources below.]",
            citations=citations,
        )

    return ChatResponse(answer=answer, citations=citations)


def _build_chat_prompt(context: str, question: str) -> str:
    if not context:
        return f"Answer based on no retrieved context (say so if the question cannot be answered):\n\nQuestion: {question}"
    return f"""Use the following context to answer the question. If the context does not contain relevant information, say so.

Context:
{context}

Question: {question}

Answer:"""
