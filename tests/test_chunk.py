"""Behavior of the SOP chunker."""

import subprocess
import sys
from pathlib import Path

from src.chunk import chunk_doc, doc_from_text, load_doc
from src.config import (
    CHARS_PER_TOKEN,
    MAX_CHUNK_CHARS,
    OVERLAP_CHARS,
    OVERLAP_TOKENS,
    TARGET_CHUNK_TOKENS,
)
from src.types import Chunk, Doc

REPO = Path(__file__).resolve().parents[1]
_BOUNDARY = ".!?。！？"


def test_window_constants_match_the_agreed_spec():
    assert CHARS_PER_TOKEN == 4
    assert TARGET_CHUNK_TOKENS == 500
    assert OVERLAP_TOKENS == 50
    assert MAX_CHUNK_CHARS == 2000
    assert OVERLAP_CHARS == 200


def test_short_section_is_one_chunk():
    text = "# Bench\n\n## Flux\n\nWipe the sample board.\n"
    doc = doc_from_text(text, "bench")
    chunks = chunk_doc(doc)
    assert len(chunks) == 1
    assert chunks[0].section_path == ["Flux"]
    assert "Wipe the sample board." in chunks[0].text
    _assert_contract(doc, chunks)


def test_short_sections_stay_separate_when_each_fits():
    text = "# Bench\n\n## Flux\n\nWipe the sample board.\n\n## Iron\n\nSet the sample iron down.\n"
    doc = doc_from_text(text, "bench")
    chunks = chunk_doc(doc)
    assert len(chunks) == 2
    assert chunks[0].section_path == ["Flux"]
    assert chunks[1].section_path == ["Iron"]
    assert len(_body(chunks[0])) + len(_body(chunks[1])) < MAX_CHUNK_CHARS
    _assert_contract(doc, chunks)


def test_short_text_without_headings_is_one_chunk():
    doc = doc_from_text("Wipe the sample board.\n", "note")
    chunks = chunk_doc(doc)
    assert len(chunks) == 1
    assert chunks[0].section_path == []
    assert chunks[0].text.startswith("note\n\nWipe the sample board.")
    _assert_contract(doc, chunks)


def test_body_at_the_character_limit_stays_one_chunk():
    body = "A" * MAX_CHUNK_CHARS
    doc = doc_from_text(f"# Limit\n\n## Edge\n\n{body}", "limit")
    chunks = chunk_doc(doc)
    assert len(chunks) == 1
    assert len(_body(chunks[0])) == MAX_CHUNK_CHARS
    _assert_contract(doc, chunks)


def test_oversized_section_splits_on_sentence_boundaries_with_overlap():
    def sentence(index: int) -> str:
        return f"Sample sentence {index:03d} records a pretend probe value for this fixture. "

    count = (MAX_CHUNK_CHARS // len(sentence(0))) + 8
    sentences = [sentence(index) for index in range(count)]
    sentence_len = len(sentences[0])
    assert sentence(0).count(".") == 1
    body = "".join(sentences)
    assert len(body) > MAX_CHUNK_CHARS
    doc = doc_from_text(f"# Reflow sample\n\n## Profile\n\n{body}", "reflow")
    chunks = chunk_doc(doc)
    assert len(chunks) >= 2
    assert {tuple(chunk.section_path) for chunk in chunks} == {("Profile",)}
    section_start = min(chunk.char_span[0] for chunk in chunks)
    section_end = max(chunk.char_span[1] for chunk in chunks)
    for chunk in chunks:
        start, end = chunk.char_span
        if start != section_start:
            assert _on_boundary(doc.text, start)
        if end != section_end:
            assert _on_boundary(doc.text, end)
        size = end - start
        assert size <= MAX_CHUNK_CHARS
        if chunk is not chunks[-1]:
            assert size > MAX_CHUNK_CHARS - sentence_len
    for left, right in zip(chunks, chunks[1:]):
        shared_len = left.char_span[1] - right.char_span[0]
        assert OVERLAP_CHARS <= shared_len < OVERLAP_CHARS + sentence_len
        shared = doc.text[right.char_span[0] : left.char_span[1]]
        assert any(item.strip() in shared for item in sentences)
    _assert_contract(doc, chunks)


def test_chinese_period_is_a_sentence_boundary_without_a_space():
    def sentence(index: int) -> str:
        return f"样例句子{index:02d}记录一个虚构的锡温读数，不能拿去改设备。"

    sentence_len = len(sentence(0))
    count = (MAX_CHUNK_CHARS // sentence_len) + 8
    sentences = [sentence(index) for index in range(count)]
    body = "".join(sentences)
    assert "。" in body and " " not in body
    assert len(body) > MAX_CHUNK_CHARS
    doc = doc_from_text(f"# 波峰焊 SOP\n\n## 点检\n\n{body}", "wave")
    chunks = chunk_doc(doc)
    assert len(chunks) >= 2
    section_start = min(chunk.char_span[0] for chunk in chunks)
    section_end = max(chunk.char_span[1] for chunk in chunks)
    for chunk in chunks:
        start, end = chunk.char_span
        if start != section_start:
            assert _on_boundary(doc.text, start)
        if end != section_end:
            assert _on_boundary(doc.text, end)
    for left, right in zip(chunks, chunks[1:]):
        shared_len = left.char_span[1] - right.char_span[0]
        assert OVERLAP_CHARS <= shared_len < OVERLAP_CHARS + sentence_len
        shared = doc.text[right.char_span[0] : left.char_span[1]]
        assert any(item in shared for item in sentences)
    _assert_contract(doc, chunks)


def test_hard_cut_overlaps_when_no_boundary_exists():
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    body = "".join(alphabet[index % 26] for index in range(MAX_CHUNK_CHARS + 500))
    doc = doc_from_text(f"# Limit\n\n## Edge\n\n{body}", "limit")
    chunks = chunk_doc(doc)
    assert len(chunks) >= 2
    assert chunks[0].char_span[1] - chunks[0].char_span[0] == MAX_CHUNK_CHARS
    assert chunks[0].char_span[1] - chunks[1].char_span[0] == OVERLAP_CHARS
    _assert_contract(doc, chunks)


def test_numbered_steps_that_fit_stay_together():
    steps = [
        "1. Find the sample open mark.",
        "2. Confirm the lead is not seated.",
        "3. Send the board to the sample touch-up tray.",
    ]
    text = "# AOI sample\n\n## Open\n\n" + "\n".join(steps) + "\n"
    doc = doc_from_text(text, "aoi")
    chunks = chunk_doc(doc)
    assert len(chunks) == 1
    for step in steps:
        assert step in chunks[0].text
    _assert_contract(doc, chunks)


def test_chinese_step_markers_that_fit_stay_together():
    steps = [
        "1、核对样例助焊剂。",
        "2、看预热显示。",
        "3、调样例轨道。",
    ]
    text = "# 波峰焊 SOP\n\n## 准备\n\n" + "\n".join(steps) + "\n"
    doc = doc_from_text(text, "wave")
    chunks = chunk_doc(doc)
    assert len(chunks) == 1
    for step in steps:
        assert step in chunks[0].text
    assert chunks[0].text.startswith("波峰焊 SOP > 准备\n\n")
    _assert_contract(doc, chunks)


def test_numbered_steps_are_not_cut_when_each_step_fits():
    steps = []
    for index in range(1, 7):
        filler = " ".join(f"sample{index}w{n}" for n in range(70))
        steps.append(f"{index}. Check sample point {index} and record {filler}.")
    assert all(len(step) <= MAX_CHUNK_CHARS for step in steps)
    body = "\n".join(steps)
    assert len(body) > MAX_CHUNK_CHARS
    doc = doc_from_text("# Wave sample\n\n## Checks\n\n" + body + "\n", "wave")
    chunks = chunk_doc(doc)
    assert len(chunks) >= 2
    for step in steps:
        start = doc.text.index(step)
        stop = start + len(step)
        assert any(step in chunk.text for chunk in chunks)
        for chunk in chunks:
            left, right = chunk.char_span
            assert not (start < left < stop)
            assert not (start < right < stop)
    _assert_contract(doc, chunks)


def test_header_is_title_then_section():
    text = "# 波峰焊 SOP\n\n## 4.3 温度\n\n锡温只在本样例里出现。\n"
    doc = doc_from_text(text, "wave")
    chunks = chunk_doc(doc)
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.doc_name == "波峰焊 SOP"
    assert chunk.section_path == ["4.3 温度"]
    assert chunk.page is None
    assert chunk.chunk_index == 0
    assert chunk.chunk_id == "wave#0"
    assert chunk.text.startswith("波峰焊 SOP > 4.3 温度\n\n锡温只在本样例里出现。")
    _assert_contract(doc, chunks)


def test_header_joins_the_nested_section_path():
    text = "# 波峰焊 SOP\n\n## 4. 工艺参数\n\n### 4.3 温度\n\n锡温只在本样例里出现。\n"
    doc = doc_from_text(text, "wave")
    chunks = chunk_doc(doc)
    assert len(chunks) == 1
    assert chunks[0].section_path == ["4. 工艺参数", "4.3 温度"]
    assert chunks[0].text.startswith("波峰焊 SOP > 4. 工艺参数 > 4.3 温度\n\n")
    _assert_contract(doc, chunks)


def test_output_is_deterministic():
    text = "# Bench\n\n## Flux\n\nWipe the sample board.\n\n## Iron\n\n" + ("Hot. " * 500)
    doc = doc_from_text(text, "bench")
    first = [chunk.model_dump() for chunk in chunk_doc(doc)]
    second = [chunk.model_dump() for chunk in chunk_doc(doc)]
    assert first == second
    assert [chunk["chunk_id"] for chunk in first] == [f"bench#{index}" for index in range(len(first))]


def test_sample_corpus_covers_the_agreed_cases():
    files = sorted((REPO / "docs" / "corpus").glob("*.md"))
    assert [path.name for path in files] == [
        "aoi-defect-handling.md",
        "reflow-soldering.md",
        "touch-up.md",
        "wave-soldering.md",
    ]
    wave = chunk_doc(load_doc(REPO / "docs" / "corpus" / "wave-soldering.md", root=REPO))
    _assert_contract(load_doc(REPO / "docs" / "corpus" / "wave-soldering.md", root=REPO), wave)
    assert any(chunk.text.startswith("波峰焊 SOP > 4.3 温度\n\n") for chunk in wave)
    prep = [chunk for chunk in wave if chunk.section_path == ["2. 准备"]]
    assert len(prep) == 1
    for marker in ("1.", "2.", "3.", "4."):
        assert marker in prep[0].text
    grouped: dict[tuple[str, ...], list[Chunk]] = {}
    for chunk in wave:
        grouped.setdefault(tuple(chunk.section_path), []).append(chunk)
    oversized = [group for group in grouped.values() if len(group) > 1]
    assert oversized
    for group in oversized:
        for left, right in zip(group, group[1:]):
            assert left.char_span[1] > right.char_span[0]
            assert left.section_path == right.section_path
    nested = [chunk for chunk in wave if chunk.section_path == ["6. 出板", "6.1 目视"]]
    assert len(nested) == 1
    assert nested[0].text.startswith("波峰焊 SOP > 6. 出板 > 6.1 目视\n\n")


def test_cli_prints_a_count_per_file_and_writes_jsonl():
    result = subprocess.run(
        [sys.executable, "-m", "src.chunk"],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    stdout = result.stdout
    corpus = sorted((REPO / "docs" / "corpus").glob("*.md"))
    assert 3 <= len(corpus) <= 4
    for path in corpus:
        label = path.relative_to(REPO).as_posix()
        assert f"{label}:" in stdout
    assert "data/chunks.jsonl" in stdout
    raw = (REPO / "data" / "chunks.jsonl").read_text(encoding="utf-8")
    assert raw.endswith("\n")
    assert "波峰焊 SOP > 4.3 温度" in raw
    assert "\\u" not in raw
    rows = [Chunk.model_validate_json(line) for line in raw.splitlines()]
    again: list[Chunk] = []
    for path in corpus:
        again.extend(chunk_doc(load_doc(path, root=REPO)))
    assert [row.model_dump() for row in rows] == [chunk.model_dump() for chunk in again]
    for chunk in rows:
        assert chunk.page is None
        assert chunk.chunk_id == f"{chunk.doc_id}#{chunk.chunk_index}"


def _body(chunk: Chunk) -> str:
    return chunk.text.split("\n\n", 1)[1]


def _on_boundary(text: str, index: int) -> bool:
    if index <= 0 or index >= len(text):
        return True
    cursor = index - 1
    while cursor >= 0 and text[cursor].isspace():
        cursor -= 1
    return cursor >= 0 and text[cursor] in _BOUNDARY


def _assert_contract(doc: Doc, chunks: list[Chunk]) -> None:
    assert chunks
    for index, chunk in enumerate(chunks):
        assert chunk.chunk_index == index
        assert chunk.chunk_id == f"{doc.doc_id}#{index}"
        assert chunk.doc_id == doc.doc_id
        assert chunk.doc_name == doc.title
        assert chunk.page is None
        assert isinstance(chunk.section_path, list)
        start, end = chunk.char_span
        assert 0 <= start < end <= len(doc.text)
        body = doc.text[start:end]
        assert len(body) <= MAX_CHUNK_CHARS
        header = doc.title
        if chunk.section_path:
            header += " > " + " > ".join(chunk.section_path)
        assert chunk.text == f"{header}\n\n{body}"
