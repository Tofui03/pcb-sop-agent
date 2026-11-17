"""Deterministic Markdown heading chunker with intra-section overlap and zero cross-section contamination."""

from __future__ import annotations

from pathlib import Path
import re

from core.schemas import SopChunk


_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def slugify_heading(heading: str) -> str:
    """Convert a section heading like '1. Open Circuit (Trace Break)' into '1_open_circuit_trace_break'."""
    slug = _SLUG_PATTERN.sub("_", heading.strip().lower()).strip("_")
    if not slug:
        raise ValueError(f"Heading produced an empty slug: {heading!r}")
    return slug


def _split_long_section_with_overlap(
    body: str,
    max_chars: int,
    overlap_chars: int,
) -> list[str]:
    """Split an oversized section body using sliding window overlap strictly within the same section."""
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError(f"overlap_chars ({overlap_chars}) must be in [0, max_chars ({max_chars})).")
    if len(body) <= max_chars:
        return [body]

    sub_bodies: list[str] = []
    step = max_chars - overlap_chars
    start = 0
    while start < len(body):
        end = min(start + max_chars, len(body))
        window = body[start:end].strip()
        if window:
            sub_bodies.append(window)
        if end >= len(body):
            break
        start += step
    return sub_bodies


def chunk_markdown_text(
    markdown_text: str,
    doc_id: str,
    max_chars: int = 1200,
    overlap_chars: int = 150,
) -> list[SopChunk]:
    """Split a Markdown document on `## ` (H2) headings into deterministic `SopChunk` records.

    - Cross-section boundary: strictly isolated (0 overlap between different `##` sections).
    - Intra-section boundary: if a single section body exceeds `max_chars`, splits with `overlap_chars`
      while preserving the parent section heading on every sub-chunk.
    """
    lines = markdown_text.splitlines()
    doc_title = doc_id
    chunks: list[SopChunk] = []

    current_section_title: str | None = None
    current_lines: list[str] = []

    def _flush_section() -> None:
        if current_section_title is None:
            return
        body = "\n".join(current_lines).strip()
        if not body:
            return
        base_slug = slugify_heading(current_section_title)
        windows = _split_long_section_with_overlap(
            body,
            max_chars=max_chars,
            overlap_chars=overlap_chars,
        )
        for idx, window_body in enumerate(windows):
            suffix = "" if len(windows) == 1 else f"_part{idx + 1}"
            chunks.append(
                SopChunk(
                    citation_id=f"{doc_id}#{base_slug}{suffix}",
                    doc_id=doc_id,
                    doc_title=doc_title,
                    section_title=current_section_title,
                    content=f"## {current_section_title}\n{window_body}",
                )
            )

    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            doc_title = stripped[2:].strip()
        elif stripped.startswith("## "):
            _flush_section()
            current_section_title = stripped[3:].strip()
            current_lines = []
        else:
            if current_section_title is not None:
                current_lines.append(raw_line)

    _flush_section()
    return chunks


def load_kb_directory(
    kb_dir: Path,
    max_chars: int = 1200,
    overlap_chars: int = 150,
) -> list[SopChunk]:
    """Load and chunk all `.md` files in `kb_dir` in sorted filename order."""
    if not kb_dir.exists() or not kb_dir.is_dir():
        raise FileNotFoundError(f"Knowledge base directory not found: {kb_dir}")

    all_chunks: list[SopChunk] = []
    for md_path in sorted(kb_dir.glob("*.md")):
        text = md_path.read_text(encoding="utf-8")
        all_chunks.extend(
            chunk_markdown_text(
                text,
                doc_id=md_path.stem,
                max_chars=max_chars,
                overlap_chars=overlap_chars,
            )
        )
    return all_chunks
