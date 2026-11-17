"""Data shapes for the SOP retrieval service.

Later modules take these types and do not invent new dicts.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Shape(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Doc(_Shape):
    doc_id: str
    path: str
    title: str
    text: str


class Chunk(_Shape):
    """One retrieval unit.

    `text` is what gets embedded. It starts with the contextual header.
    `char_span` is the body only, as a start and end in `Doc.text`.
    `page` stays null for markdown.
    """

    chunk_id: str
    doc_id: str
    doc_name: str
    section_path: list[str]
    page: int | None = None
    chunk_index: int
    char_span: tuple[int, int]
    text: str


class Citation(_Shape):
    chunk_id: str
    quote: str


class Sentence(_Shape):
    text: str
    citation: Citation


class GroundedAnswer(_Shape):
    sentences: list[Sentence] = Field(min_length=1)


class Refusal(_Shape):
    reason: Literal["not_in_docs", "ungrounded"]
    text: Literal["not in the docs"] = "not in the docs"


class EvalCase(_Shape):
    case_id: str
    question: str
    answerable: bool
    expected_chunk_ids: list[str]
    reference_answer: str
