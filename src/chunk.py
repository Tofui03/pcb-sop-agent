"""Split SOP markdown into chunks with a header and metadata."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from src.config import MAX_CHUNK_CHARS, OVERLAP_CHARS
from src.types import Chunk, Doc

_HEADING = re.compile(r"^(#{1,3})[ \t]+(.+?)[ \t]*#*[ \t]*$", re.MULTILINE)
_STEP = re.compile(r"(?m)^(\d{1,3})(?:[.](?!\d)|[)、])[ \t]*\S")
_WS = " \t\n"


@dataclass(frozen=True)
class _Section:
    path: tuple[str, ...]
    start: int
    end: int


def contextual_header(doc_name: str, section_path: list[str]) -> str:
    """Doc title, then the section path. Example: 波峰焊 SOP > 4.3 温度."""
    if not section_path:
        return doc_name
    return doc_name + " > " + " > ".join(section_path)


def document_title(text: str, fallback: str) -> str:
    match = _HEADING.search(text)
    if match is None or len(match.group(1)) != 1:
        return fallback
    title = _heading_text(match.group(2))
    return title or fallback


def split_sections(text: str, doc_title: str) -> list[_Section]:
    """One section per heading. The body stops at the next heading."""
    headings = list(_HEADING.finditer(text))
    if not headings:
        trimmed = _trimmed(text, 0, len(text))
        if trimmed is None:
            return []
        return [_Section((), trimmed[0], trimmed[1])]

    sections: list[_Section] = []
    if headings[0].start() > 0:
        trimmed = _trimmed(text, 0, headings[0].start())
        if trimmed is not None:
            sections.append(_Section((), trimmed[0], trimmed[1]))

    stack: list[tuple[int, str]] = []
    for index, match in enumerate(headings):
        level = len(match.group(1))
        title = _heading_text(match.group(2))
        if not title:
            continue
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        body_end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        raw_start = match.end()
        if raw_start < len(text) and text[raw_start] == "\n":
            raw_start += 1
        trimmed = _trimmed(text, raw_start, body_end)
        if trimmed is None:
            continue
        path = _section_path(stack, doc_title)
        sections.append(_Section(path, trimmed[0], trimmed[1]))
    return sections


def section_windows(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """One span when the section fits. Windows when it does not."""
    if end <= start:
        return []
    # A section that fits stays one chunk. Windows are the fallback.
    if end - start <= MAX_CHUNK_CHARS:
        return [(start, end)]
    body = text[start:end]
    return [(start + left, start + right) for left, right in window_body(body) if right > left]


def window_body(text: str) -> list[tuple[int, int]]:
    """Fixed windows over a section body that missed the size limit."""
    if text == "":
        return []
    if len(text) <= MAX_CHUNK_CHARS:
        return [(0, len(text))]

    windows: list[tuple[int, int]] = []
    bucket: list[tuple[int, int]] = []

    def flush() -> None:
        if bucket:
            windows.extend(pack_windows(bucket))
            bucket.clear()

    for kind, spans in _pieces(text):
        if kind == "ready":
            flush()
            windows.extend(spans)
            continue
        bucket.extend(spans)
    flush()
    if windows:
        return windows
    return hard_windows(text, 0, len(text))


def pack_windows(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Pack atomic units. Neighbors share about OVERLAP_CHARS of text."""
    if not spans:
        return []
    windows: list[tuple[int, int]] = []
    index = 0
    last = len(spans)
    while index < last:
        end_index = index
        while (
            end_index + 1 < last
            and spans[end_index + 1][1] - spans[index][0] <= MAX_CHUNK_CHARS
        ):
            end_index += 1
        windows.append((spans[index][0], spans[end_index][1]))
        if end_index == last - 1:
            break
        index = _next_index(spans, index, end_index)
    return windows


def hard_windows(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Cut a span that has no paragraph or sentence boundary.

    The slice is still about MAX_CHUNK_CHARS, and the next window starts
    about OVERLAP_CHARS earlier. A space is used when one exists.
    """
    windows: list[tuple[int, int]] = []
    pos = start
    while pos < end:
        hard_end = min(pos + MAX_CHUNK_CHARS, end)
        if hard_end < end:
            snap = _snap_back(text, pos, hard_end)
            if snap is not None:
                hard_end = snap
        if hard_end <= pos:
            hard_end = min(pos + MAX_CHUNK_CHARS, end)
        windows.append((pos, hard_end))
        if hard_end >= end:
            break
        nxt = hard_end - OVERLAP_CHARS
        if nxt <= pos:
            nxt = hard_end
        else:
            snapped = _snap_forward(text, nxt, hard_end)
            if pos < snapped < hard_end:
                nxt = snapped
        if nxt <= pos:
            nxt = hard_end
        pos = nxt
    return windows


def chunk_doc(doc: Doc) -> list[Chunk]:
    """Chunk one document. Every chunk carries the same metadata fields."""
    chunks: list[Chunk] = []
    for section in split_sections(doc.text, doc.title):
        for start, end in section_windows(doc.text, section.start, section.end):
            body = doc.text[start:end]
            # The header is part of the embedded text. char_span covers the body only.
            header = contextual_header(doc.title, list(section.path))
            index = len(chunks)
            chunks.append(
                Chunk(
                    chunk_id=f"{doc.doc_id}#{index}",
                    doc_id=doc.doc_id,
                    doc_name=doc.title,
                    section_path=list(section.path),
                    page=None,
                    chunk_index=index,
                    char_span=(start, end),
                    text=f"{header}\n\n{body}",
                )
            )
    return chunks


def doc_from_text(text: str, doc_id: str, path: str | None = None) -> Doc:
    title = document_title(text, fallback=doc_id)
    return Doc(
        doc_id=doc_id,
        path=path if path is not None else f"{doc_id}.md",
        title=title,
        text=text,
    )


def load_doc(path: Path, root: Path | None = None) -> Doc:
    raw = path.read_text(encoding="utf-8")
    if raw.startswith("\ufeff"):
        raw = raw[1:]
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    if root is None:
        shown = path.as_posix()
    else:
        try:
            shown = path.relative_to(root).as_posix()
        except ValueError:
            shown = path.as_posix()
    doc_id = path.stem
    return Doc(
        doc_id=doc_id,
        path=shown,
        title=document_title(text, fallback=doc_id),
        text=text,
    )


def run(corpus_dir: Path, out_path: Path, label_root: Path | None = None) -> list[tuple[str, int]]:
    root = label_root or corpus_dir.parent
    paths = sorted(path for path in corpus_dir.glob("*.md") if path.is_file())
    counts: list[tuple[str, int]] = []
    chunks: list[Chunk] = []
    for path in paths:
        file_chunks = chunk_doc(load_doc(path, root=root))
        chunks.extend(file_chunks)
        try:
            label = path.relative_to(root).as_posix()
        except ValueError:
            label = path.name
        counts.append((label, len(file_chunks)))
    write_jsonl(chunks, out_path)
    return counts


def write_jsonl(chunks: list[Chunk], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(chunk.model_dump(mode="json"), ensure_ascii=False) for chunk in chunks
    ]
    text = "\n".join(lines)
    if text:
        text += "\n"
    path.write_text(text, encoding="utf-8")


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    corpus = repo / "docs" / "corpus"
    if not corpus.is_dir():
        raise SystemExit(f"missing corpus directory: {corpus}")
    out = repo / "data" / "chunks.jsonl"
    counts = run(corpus, out, label_root=repo)
    for label, count in counts:
        print(f"{label}: {count}")
    total = sum(count for _, count in counts)
    print(f"{len(counts)} files, {total} chunks -> data/chunks.jsonl")


def _heading_text(raw: str) -> str:
    return raw.strip().strip("#").strip()


def _section_path(stack: list[tuple[int, str]], doc_title: str) -> tuple[str, ...]:
    if stack and stack[0][0] == 1 and stack[0][1] == doc_title:
        return tuple(title for _, title in stack[1:])
    return tuple(title for _, title in stack)


def _trimmed(text: str, start: int, end: int) -> tuple[int, int] | None:
    if end <= start:
        return None
    raw = text[start:end]
    core = raw.strip()
    if not core:
        return None
    lead = len(raw) - len(raw.lstrip())
    begin = start + lead
    return begin, begin + len(core)


def _rough_pieces(text: str) -> list[tuple[int, int]]:
    steps = _step_spans(text)
    if steps is not None:
        return steps
    return _paragraph_spans(text, 0, len(text))


def _step_spans(text: str) -> list[tuple[int, int]] | None:
    """A numbered step that fits is one unit, so a cut falls between steps."""
    matches = list(_STEP.finditer(text))
    if len(matches) < 2:
        return None
    spans: list[tuple[int, int]] = []
    if matches[0].start() > 0:
        spans.extend(_paragraph_spans(text, 0, matches[0].start()))
    for index, match in enumerate(matches):
        stop = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        if text[match.start() : stop].strip():
            spans.append((match.start(), stop))
    return spans


def _paragraph_spans(text: str, start: int, end: int) -> list[tuple[int, int]]:
    region = text[start:end]
    spans: list[tuple[int, int]] = []
    cursor = 0
    for match in re.finditer(r"\n{2,}", region):
        if match.start() > cursor and region[cursor : match.start()].strip():
            spans.append((start + cursor, start + match.start()))
        cursor = match.end()
    if cursor < len(region) and region[cursor:].strip():
        spans.append((start + cursor, end))
    return spans


def _pieces(text: str) -> list[tuple[str, list[tuple[int, int]]]]:
    pieces: list[tuple[str, list[tuple[int, int]]]] = []
    for start, end in _rough_pieces(text):
        if end - start <= MAX_CHUNK_CHARS:
            pieces.append(("unit", [(start, end)]))
            continue
        sentences = _sentence_spans(text, start, end)
        if len(sentences) <= 1:
            pieces.append(("ready", hard_windows(text, start, end)))
            continue
        for sent_start, sent_end in sentences:
            if sent_end - sent_start <= MAX_CHUNK_CHARS:
                pieces.append(("unit", [(sent_start, sent_end)]))
            else:
                pieces.append(("ready", hard_windows(text, sent_start, sent_end)))
    return pieces


def _sentence_spans(text: str, start: int, end: int) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = start
    index = start
    while index < end:
        nxt = _boundary_end(text, index, end)
        if nxt is None:
            index += 1
            continue
        if nxt > cursor and text[cursor:nxt].strip():
            spans.append((cursor, nxt))
        cursor = max(cursor, nxt)
        index = max(nxt, index + 1)
    if cursor < end and text[cursor:end].strip():
        spans.append((cursor, end))
    return spans


def _boundary_end(text: str, index: int, end: int) -> int | None:
    ch = text[index]
    if ch in "。！？":
        nxt = index + 1
    elif ch in ".!?":
        if _step_marker_dot(text, index):
            return None
        following = text[index + 1] if index + 1 < end else ""
        if following != "" and not following.isspace():
            return None
        nxt = index + 1
    else:
        return None
    while nxt < end and text[nxt] in _WS:
        nxt += 1
    return nxt


def _step_marker_dot(text: str, index: int) -> bool:
    if text[index] != ".":
        return False
    line = text.rfind("\n", 0, index) + 1
    prefix = text[line:index]
    return prefix.isdigit() and prefix != ""


def _next_index(spans: list[tuple[int, int]], start: int, end: int) -> int:
    """First unit of the next window. Always moves forward."""
    if end == start or OVERLAP_CHARS <= 0:
        return end + 1
    window_end = spans[end][1]
    cursor = end
    while cursor > start and window_end - spans[cursor][0] < OVERLAP_CHARS:
        cursor -= 1
    if cursor == start:
        return start + 1
    return cursor


def _snap_back(text: str, pos: int, hard_end: int) -> int | None:
    floor = pos + max(1, (hard_end - pos) // 2)
    snap = max(text.rfind(" ", floor, hard_end), text.rfind("\n", floor, hard_end))
    if snap <= pos:
        return None
    return snap


def _snap_forward(text: str, nxt: int, limit: int) -> int:
    if nxt <= 0 or text[nxt - 1].isspace():
        return nxt
    space = text.find(" ", nxt, limit)
    newline = text.find("\n", nxt, limit)
    spots = [spot for spot in (space, newline) if spot != -1]
    if not spots:
        return nxt
    return min(spots) + 1


if __name__ == "__main__":
    main()
