# FastAPI app and route definitions; mounts /api/chat, /api/document, /api/entities, /api/search, /api/stats, /api/tag-clusters.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import chat as chat_module
from api import documents as documents_module
from api import entities as entities_module
from api import graph as graph_module
from api import search as search_module
from api import sessions as sessions_module
from api import stats as stats_module

app = FastAPI(title="RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_module.router, prefix="/api")
app.include_router(documents_module.router, prefix="/api")
app.include_router(entities_module.router, prefix="/api")
app.include_router(graph_module.router, prefix="/api")
app.include_router(search_module.router, prefix="/api")
app.include_router(sessions_module.router, prefix="/api")
app.include_router(stats_module.router, prefix="/api")


@app.get("/")
def root():
    """Minimal root for deployment/health."""
    return {"status": "ok", "service": "RAG API"}


@app.get("/health")
def health():
    return {"status": "ok"}
