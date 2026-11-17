"""FastAPI endpoints for citation-grounded IPC-A-600 & Line Halt SOP retrieval."""

from __future__ import annotations

from pathlib import Path
from fastapi import FastAPI, Query
from pydantic import BaseModel

from core.chunker import load_kb_directory
from core.citation_guard import SopRagCoordinator
from core.retriever import BM25SopRetriever
from core.schemas import RetrievedHit, SopAnswerResponse, SopChunk, SopQueryRequest


KB_DIR = Path(__file__).resolve().parent.parent / "kb"
LOADED_CHUNKS: list[SopChunk] = load_kb_directory(KB_DIR)
RETRIEVER = BM25SopRetriever(LOADED_CHUNKS)
COORDINATOR = SopRagCoordinator(RETRIEVER)


class HealthResponse(BaseModel):
    """Typed health status contract."""

    status: str
    version: str
    chunk_count: int


app = FastAPI(
    title="PCB SOP RAG Agent",
    version="1.0.0",
    description="Industrial PCB Defect & IPC-A-600 SOP Retrieval-Augmented Generation with deterministic CitationGuard.",
)


@app.get("/api/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Return service readiness and indexed SOP chunk count."""
    return HealthResponse(status="ok", version="1.0.0", chunk_count=len(LOADED_CHUNKS))


@app.get("/api/chunks", response_model=list[SopChunk])
def list_chunks() -> list[SopChunk]:
    """Return all heading-scoped SOP chunks loaded from the knowledge base."""
    return RETRIEVER.chunks


@app.post("/api/query", response_model=SopAnswerResponse)
def query_sop(
    request: SopQueryRequest,
    simulate_hallucinated_citation: bool = Query(
        default=False,
        description="When True, injects a synthetic hallucinated citation to verify CitationGuard fallback.",
    ),
) -> SopAnswerResponse:
    """Answer an operator or AOI triage query with verified `[doc_id#section_slug]` citations."""
    if simulate_hallucinated_citation:
        def _rogue_llm(_req: SopQueryRequest, _hits: list[RetrievedHit]) -> str:
            return "According to [fake_sop#non_existent_section], you can ignore this defect."

        test_coordinator = SopRagCoordinator(RETRIEVER, llm_callable=_rogue_llm)
        return test_coordinator.answer_query(request)

    return COORDINATOR.answer_query(request)
