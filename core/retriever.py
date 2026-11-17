"""Zero-dependency deterministic BM25 + metadata-boosted retriever for SOP chunks."""

from __future__ import annotations

from collections import Counter
import math
import re

from core.schemas import RetrievedHit, SopChunk, SopQueryRequest


_TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")

_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "do",
        "for",
        "from",
        "how",
        "if",
        "in",
        "into",
        "is",
        "it",
        "of",
        "on",
        "or",
        "should",
        "that",
        "the",
        "to",
        "what",
        "when",
        "where",
        "which",
        "with",
    }
)


def tokenize(text: str) -> list[str]:
    """Extract lowercase alphanumeric/underscore tokens excluding generic stopwords."""
    raw_tokens = _TOKEN_PATTERN.findall(text.lower())
    return [tok for tok in raw_tokens if tok not in _STOPWORDS and len(tok) > 1]


class BM25SopRetriever:
    """Deterministic Okapi BM25 retriever with structured AOI metadata boosting."""

    def __init__(
        self,
        chunks: list[SopChunk],
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        if not chunks:
            raise ValueError("BM25SopRetriever requires at least one SopChunk.")
        self._chunks = list(chunks)
        self._k1 = k1
        self._b = b

        self._doc_tokens: list[list[str]] = [
            tokenize(f"{c.doc_title} {c.section_title} {c.content}") for c in self._chunks
        ]
        self._doc_freqs: list[Counter[str]] = [Counter(tokens) for tokens in self._doc_tokens]
        self._doc_lens: list[int] = [len(tokens) for tokens in self._doc_tokens]
        self._avg_dl: float = sum(self._doc_lens) / len(self._doc_lens)

        df_counts: Counter[str] = Counter()
        for freq in self._doc_freqs:
            for term in freq:
                df_counts[term] += 1

        n_docs = len(self._chunks)
        self._idf: dict[str, float] = {
            term: math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))
            for term, df in df_counts.items()
        }

    @property
    def chunks(self) -> list[SopChunk]:
        """Return a copy of the indexed SOP chunks."""
        return list(self._chunks)

    def retrieve(self, request: SopQueryRequest) -> list[RetrievedHit]:
        """Rank SOP chunks using BM25 + structured metadata boosts (`defect_class`, `halt_production_line`)."""
        query_terms = tokenize(request.question)
        hits: list[RetrievedHit] = []

        for idx, chunk in enumerate(self._chunks):
            freq = self._doc_freqs[idx]
            doc_len = self._doc_lens[idx]
            score = 0.0

            for term in query_terms:
                tf = freq.get(term, 0)
                if tf == 0:
                    continue
                idf = self._idf.get(term, 0.0)
                denom = tf + self._k1 * (1.0 - self._b + self._b * (doc_len / self._avg_dl))
                score += idf * ((tf * (self._k1 + 1.0)) / denom)

            # Metadata boost 1: explicit defect_class filter/boost
            if request.defect_class is not None:
                defect_norm = request.defect_class.lower().replace("-", "_")
                chunk_text_norm = f"{chunk.section_title} {chunk.content}".lower().replace("-", "_")
                if defect_norm in chunk_text_norm:
                    if f"**defect class**: `{request.defect_class.lower()}`" in chunk.content.lower():
                        score += 3.0
                    else:
                        score += 1.5

            # Metadata boost 2: Stage 4 batch drift line-halt protocol
            if request.halt_production_line and chunk.doc_id == "line_halt_troubleshooting":
                score += 3.0
                if "batch_halt_threshold" in chunk.content.lower():
                    score += 2.0

            if score > 0.0:
                hits.append(RetrievedHit(chunk=chunk, score=round(score, 4)))

        hits.sort(key=lambda h: (-h.score, h.chunk.citation_id))
        return hits[: request.top_k]
