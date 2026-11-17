"""Data contracts (schemas) for SOP chunking, retrieval, and citation-verified Q&A."""

from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field, validator


DefectClassName = Literal[
    "Open",
    "Short",
    "Mousebite",
    "Spur",
    "Spurious_Copper",
    "Pin-hole",
]


class SopChunk(BaseModel):
    """A single heading-scoped section extracted from an SOP markdown file."""

    citation_id: str = Field(
        ...,
        description="Deterministic citation identifier in 'doc_id#section_slug' format.",
    )
    doc_id: str = Field(..., description="Markdown filename stem (e.g. 'ipc_a_600_defects').")
    doc_title: str = Field(..., description="Top-level H1 document title.")
    section_title: str = Field(..., description="H2 section heading title.")
    content: str = Field(..., description="Full text of the section including heading.")

    @validator("citation_id")
    def validate_citation_id_format(cls, value: str) -> str:
        if "#" not in value or value.startswith("#") or value.endswith("#"):
            raise ValueError(f"citation_id must follow 'doc_id#section_slug' format, got: {value!r}")
        return value


class RetrievedHit(BaseModel):
    """A ranked chunk returned by the BM25 / hybrid retriever."""

    chunk: SopChunk
    score: float = Field(..., ge=0.0, description="Non-negative relevance score.")


class SopQueryRequest(BaseModel):
    """Input query from an operator or downstream AOI triage alert."""

    question: str = Field(..., min_length=2, description="Natural-language operator question.")
    defect_class: Optional[DefectClassName] = Field(
        default=None,
        description="Optional DeepPCB-AOI defect class filter/boost.",
    )
    ipc_class: Optional[Literal["CLASS_2", "CLASS_3"]] = Field(
        default=None,
        description="Optional IPC-A-600 target class context.",
    )
    halt_production_line: bool = Field(
        default=False,
        description="True when Stage 4 guardrails triggered a 3-strike batch line halt.",
    )
    top_k: int = Field(default=3, ge=1, le=10, description="Number of SOP sections to retrieve.")


class SopAnswerResponse(BaseModel):
    """Citation-grounded answer verified by CitationGuard."""

    answer: str = Field(..., description="Answer containing inline [doc_id#section_slug] citations.")
    citations: list[str] = Field(
        default_factory=list,
        description="Verified citation IDs present in both the answer and retrieved chunks.",
    )
    retrieved_chunks: list[RetrievedHit] = Field(
        default_factory=list,
        description="Top-k SOP sections used as grounding context.",
    )
    source_mode: Literal["llm_verified", "deterministic_template", "out_of_scope_refusal"] = Field(
        ...,
        description="Indicates whether the response came from a verified LLM, deterministic fallback, or refusal.",
    )
    guardrail_notes: Optional[str] = Field(
        default=None,
        description="Populated when CitationGuard rejects an ungrounded LLM response and falls back.",
    )
