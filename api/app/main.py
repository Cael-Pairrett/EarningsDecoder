"""EarningsDecoder FastAPI — RAG over stock/earnings title+URL corpus."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import get_settings
from .rag import build_index, load_records, run_query


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    # Load or build FAISS on startup so the first query is fast
    build_index(settings, force=False)
    yield


app = FastAPI(
    title="EarningsDecoder API",
    description="Stock/earnings RAG prototype — titles-only vs content answers",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)


@app.get("/health")
def health():
    settings = get_settings()
    n = 0
    try:
        n = len(load_records(settings.records_path))
    except Exception:
        pass
    return {
        "ok": True,
        "records": n,
        "model": settings.grok_model,
        "has_api_key": bool(settings.api_key),
    }


@app.get("/samples")
def samples():
    return {
        "queries": [
            "How is Apple's services revenue growing?",
            "What did NVIDIA say about data center demand?",
            "Summarize recent bank earnings and net interest margin trends",
        ]
    }


@app.post("/query")
def query(body: QueryRequest):
    settings = get_settings()
    if not settings.api_key:
        raise HTTPException(
            status_code=503,
            detail="Set XAI_API_KEY (or GROK_API_KEY) in .env before querying.",
        )
    try:
        return run_query(body.query.strip(), settings)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
