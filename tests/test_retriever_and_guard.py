"""Unit tests for BM25SopRetriever, CitationGuard, SopRagCoordinator, and FastAPI endpoints."""

from __future__ import annotations

from pathlib import Path
import unittest

from api.main import health_check, list_chunks, query_sop
from core.chunker import load_kb_directory
from core.citation_guard import (
    SopRagCoordinator,
    extract_citations,
    verify_citations,
)
from core.retriever import BM25SopRetriever
from core.schemas import RetrievedHit, SopQueryRequest


class TestRetrieverAndCitationGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        kb_dir = Path(__file__).resolve().parent.parent / "kb"
        cls.chunks = load_kb_directory(kb_dir)
        cls.retriever = BM25SopRetriever(cls.chunks)

    def test_bm25_ranks_short_circuit_top_for_short_query(self) -> None:
        req = SopQueryRequest(
            question="What is the disposition and operator action for a copper bridge short circuit?",
            defect_class="Short",
            top_k=3,
        )
        hits = self.retriever.retrieve(req)
        self.assertGreaterEqual(len(hits), 1)
        self.assertEqual(
            hits[0].chunk.citation_id,
            "ipc_a_600_defects#2_short_circuit_copper_bridge",
        )

    def test_bm25_ranks_etching_bath_for_orp_query(self) -> None:
        req = SopQueryRequest(
            question="How should we adjust ORP 510 mV and cupric ion specific gravity?",
            top_k=2,
        )
        hits = self.retriever.retrieve(req)
        self.assertGreaterEqual(len(hits), 1)
        self.assertEqual(
            hits[0].chunk.citation_id,
            "line_halt_troubleshooting#2_etching_bath_chemical_drift_remediation",
        )

    def test_halt_production_line_boosts_troubleshooting_sop(self) -> None:
        req = SopQueryRequest(
            question="3 defects occurred in the same batch, what should the operator do?",
            defect_class="Open",
            halt_production_line=True,
            top_k=3,
        )
        hits = self.retriever.retrieve(req)
        top_docs = [h.chunk.doc_id for h in hits]
        self.assertIn("line_halt_troubleshooting", top_docs)
        self.assertEqual(
            hits[0].chunk.citation_id,
            "line_halt_troubleshooting#1_batch_drift_line_halt_protocol",
        )

    def test_out_of_scope_query_returns_refusal(self) -> None:
        coordinator = SopRagCoordinator(self.retriever)
        req = SopQueryRequest(question="What is the weather forecast in Kuala Lumpur tomorrow?")
        resp = coordinator.answer_query(req)
        self.assertEqual(resp.source_mode, "out_of_scope_refusal")
        self.assertEqual(resp.citations, [])
        self.assertEqual(resp.retrieved_chunks, [])
        self.assertIn("Out of scope", resp.answer)

    def test_citation_guard_accepts_grounded_llm_answer(self) -> None:
        def _valid_llm(_req: SopQueryRequest, hits: list[RetrievedHit]) -> str:
            cid = hits[0].chunk.citation_id
            return f"Mandatory SCRAP is required for Short defects per [{cid}]."

        coordinator = SopRagCoordinator(self.retriever, llm_callable=_valid_llm)
        req = SopQueryRequest(question="What is the policy for Short circuit?", defect_class="Short")
        resp = coordinator.answer_query(req)
        self.assertEqual(resp.source_mode, "llm_verified")
        self.assertEqual(resp.citations, ["ipc_a_600_defects#2_short_circuit_copper_bridge"])
        self.assertIsNone(resp.guardrail_notes)

    def test_citation_guard_rejects_hallucinated_citation_and_falls_back(self) -> None:
        def _hallucinating_llm(_req: SopQueryRequest, _hits: list[RetrievedHit]) -> str:
            return "According to [fake_doc#fake_sec], use jumper wire rework."

        coordinator = SopRagCoordinator(self.retriever, llm_callable=_hallucinating_llm)
        req = SopQueryRequest(question="How to handle Open circuit trace break?", defect_class="Open")
        resp = coordinator.answer_query(req)
        self.assertEqual(resp.source_mode, "deterministic_template")
        self.assertIsNotNone(resp.guardrail_notes)
        self.assertIn("hallucinated citation", resp.guardrail_notes or "")
        self.assertIn("ipc_a_600_defects#1_open_circuit_trace_break", resp.citations)

    def test_citation_guard_rejects_rogue_llm_claiming_short_can_pass(self) -> None:
        def _unsafe_llm(_req: SopQueryRequest, hits: list[RetrievedHit]) -> str:
            cid = hits[0].chunk.citation_id
            return f"A small Short defect can PASS if under 50 px [{cid}]."

        coordinator = SopRagCoordinator(self.retriever, llm_callable=_unsafe_llm)
        req = SopQueryRequest(question="Can a small Short pass?", defect_class="Short")
        resp = coordinator.answer_query(req)
        self.assertEqual(resp.source_mode, "deterministic_template")
        self.assertIn("safety violation", resp.guardrail_notes or "")

    def test_extract_and_verify_citations_zero_citations_rejected(self) -> None:
        req = SopQueryRequest(question="Mousebite limit?", defect_class="Mousebite")
        hits = self.retriever.retrieve(req)
        self.assertEqual(extract_citations("No brackets here."), [])
        is_valid, citations, reason = verify_citations("Uncited statement about Mousebite.", hits)
        self.assertFalse(is_valid)
        self.assertEqual(citations, [])
        self.assertIn("zero inline", reason or "")

    def test_fastapi_route_handlers(self) -> None:
        health = health_check()
        self.assertEqual(health.status, "ok")
        self.assertEqual(health.chunk_count, 9)

        chunks = list_chunks()
        self.assertEqual(len(chunks), 9)

        req = SopQueryRequest(question="Spur protrusion area limit", defect_class="Spur", top_k=2)
        normal_resp = query_sop(req, simulate_hallucinated_citation=False)
        self.assertEqual(normal_resp.source_mode, "deterministic_template")
        self.assertIn("ipc_a_600_defects#4_spur_copper_protrusion", normal_resp.citations)

        guarded_resp = query_sop(req, simulate_hallucinated_citation=True)
        self.assertEqual(guarded_resp.source_mode, "deterministic_template")
        self.assertIn("hallucinated citation", guarded_resp.guardrail_notes or "")


if __name__ == "__main__":
    unittest.main()
