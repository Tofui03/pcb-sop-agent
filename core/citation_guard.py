"""Citation verification guardrails and deterministic fallback coordinator for SOP RAG."""

from __future__ import annotations

import re
from typing import Callable, Optional

from core.retriever import BM25SopRetriever
from core.schemas import RetrievedHit, SopAnswerResponse, SopQueryRequest


_CITATION_PATTERN = re.compile(r"\[([a-z0-9_]+#[a-z0-9_]+)\]")

# Reject any LLM claim that fatal Open/Short defects can PASS inspection
_FATAL_DEFECT_PASS_PATTERN = re.compile(
    r"\b(open|short)\b[^.\n]{0,60}\b(can\s+pass|is\s+pass|allowed\s+to\s+pass|disposition\s*:\s*pass)\b",
    re.IGNORECASE,
)


def extract_citations(text: str) -> list[str]:
    """Extract unique inline citations in order of appearance matching `[doc_id#section_slug]`."""
    found = _CITATION_PATTERN.findall(text)
    deduped: list[str] = []
    for cid in found:
        if cid not in deduped:
            deduped.append(cid)
    return deduped


def verify_citations(
    answer: str,
    retrieved_hits: list[RetrievedHit],
) -> tuple[bool, list[str], Optional[str]]:
    """Verify that an answer contains valid inline citations and respects IPC safety invariants.

    Returns:
        (is_valid, extracted_citations, failure_reason)
    """
    citations = extract_citations(answer)
    if not citations:
        return (
            False,
            [],
            "CitationGuard rejected LLM output: zero inline [doc_id#section_slug] citations found.",
        )

    allowed_ids = {hit.chunk.citation_id for hit in retrieved_hits}
    hallucinated = [cid for cid in citations if cid not in allowed_ids]
    if hallucinated:
        return (
            False,
            citations,
            f"CitationGuard rejected hallucinated citation(s) not in retrieved top-k: {hallucinated}",
        )

    if _FATAL_DEFECT_PASS_PATTERN.search(answer):
        return (
            False,
            citations,
            "CitationGuard rejected safety violation: Open/Short defects are mandatory SCRAP and cannot PASS.",
        )

    return True, citations, None


def build_deterministic_sop_answer(
    request: SopQueryRequest,
    retrieved_hits: list[RetrievedHit],
    guardrail_notes: Optional[str] = None,
) -> SopAnswerResponse:
    """Synthesize a 100% deterministic, citation-grounded response without requiring an external LLM."""
    if not retrieved_hits:
        return SopAnswerResponse(
            answer=(
                "Out of scope: No matching IPC-A-600 or Line Halt SOP sections were found for your query. "
                "Please ask about bare-board PCB defects (Open, Short, Mousebite, Spur, Spurious_Copper, Pin-hole) "
                "or etching/photolithography line-halt troubleshooting."
            ),
            citations=[],
            retrieved_chunks=[],
            source_mode="out_of_scope_refusal",
            guardrail_notes=guardrail_notes,
        )

    lines: list[str] = []
    citations: list[str] = []
    for hit in retrieved_hits:
        cid = hit.chunk.citation_id
        citations.append(cid)
        body_lines = [
            line.strip()
            for line in hit.chunk.content.splitlines()
            if line.strip() and not line.strip().startswith("## ")
        ]
        summary_text = " ".join(body_lines)
        lines.append(f"- **{hit.chunk.section_title}** [{cid}]: {summary_text}")

    header = "Grounded IPC-A-600 / SOP Guidance:"
    if request.halt_production_line:
        header = "LINE HALT ACTIVE — Grounded IPC-A-600 & Process Drift Guidance:"

    return SopAnswerResponse(
        answer=f"{header}\n" + "\n".join(lines),
        citations=citations,
        retrieved_chunks=retrieved_hits,
        source_mode="deterministic_template",
        guardrail_notes=guardrail_notes,
    )


class SopRagCoordinator:
    """Coordinates retrieval, optional LLM synthesis, CitationGuard verification, and deterministic fallback."""

    def __init__(
        self,
        retriever: BM25SopRetriever,
        llm_callable: Optional[Callable[[SopQueryRequest, list[RetrievedHit]], str]] = None,
    ) -> None:
        self._retriever = retriever
        self._llm_callable = llm_callable

    def answer_query(self, request: SopQueryRequest) -> SopAnswerResponse:
        """Retrieve relevant SOP chunks, verify LLM output if configured, or fall back deterministically."""
        hits = self._retriever.retrieve(request)
        if not hits:
            return build_deterministic_sop_answer(request, hits)

        if self._llm_callable is None:
            return build_deterministic_sop_answer(request, hits)

        try:
            candidate_answer = self._llm_callable(request, hits)
        except Exception as exc:
            return build_deterministic_sop_answer(
                request,
                hits,
                guardrail_notes=f"LLM provider error ({exc}); fell back to deterministic SOP template.",
            )

        is_valid, verified_citations, failure_reason = verify_citations(candidate_answer, hits)
        if not is_valid:
            return build_deterministic_sop_answer(
                request,
                hits,
                guardrail_notes=failure_reason,
            )

        return SopAnswerResponse(
            answer=candidate_answer,
            citations=verified_citations,
            retrieved_chunks=hits,
            source_mode="llm_verified",
            guardrail_notes=None,
        )
