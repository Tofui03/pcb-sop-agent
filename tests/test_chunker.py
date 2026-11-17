"""Unit tests for schemas and Markdown heading chunker."""

from pathlib import Path
import unittest
from pydantic import ValidationError

from core.chunker import chunk_markdown_text, load_kb_directory, slugify_heading
from core.schemas import SopChunk


class TestChunkerAndSchemas(unittest.TestCase):
    def test_slugify_heading_normalizes_punctuation_and_case(self) -> None:
        self.assertEqual(slugify_heading("1. Open Circuit (Trace Break)"), "1_open_circuit_trace_break")
        self.assertEqual(slugify_heading("  Pin-hole / Void  "), "pin_hole_void")

    def test_slugify_heading_rejects_empty_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "empty slug"):
            slugify_heading("   ???   ")

    def test_sop_chunk_validates_citation_id_format(self) -> None:
        with self.assertRaises(ValidationError):
            SopChunk(
                citation_id="invalid_without_hash",
                doc_id="doc",
                doc_title="Doc",
                section_title="Sec",
                content="Body",
            )

    def test_chunk_markdown_text_splits_h2_sections_without_cross_contamination(self) -> None:
        sample_md = """# Sample SOP Title

Intro paragraph before H2 is ignored.

## 1. Short Defect
Mandatory SCRAP.

## 2. Mousebite Defect
PASS if area <= 250 px.
"""
        chunks = chunk_markdown_text(sample_md, doc_id="sample_sop")
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].citation_id, "sample_sop#1_short_defect")
        self.assertNotIn("PASS", chunks[0].content)
        self.assertEqual(chunks[1].citation_id, "sample_sop#2_mousebite_defect")
        self.assertNotIn("SCRAP", chunks[1].content)

    def test_intra_section_overlap_splits_oversized_section_only_within_boundary(self) -> None:
        long_md = """# Long SOP

## 1. Etching Procedure
Step A: Check ORP 510-540 mV. Step B: Verify HCl concentration. Step C: Inspect upper and lower spray nozzles.
"""
        chunks = chunk_markdown_text(long_md, doc_id="long_sop", max_chars=60, overlap_chars=20)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertEqual(chunks[0].citation_id, "long_sop#1_etching_procedure_part1")
        self.assertEqual(chunks[1].citation_id, "long_sop#1_etching_procedure_part2")
        # Both sub-chunks retain the parent section header for context
        self.assertTrue(chunks[0].content.startswith("## 1. Etching Procedure\n"))
        self.assertTrue(chunks[1].content.startswith("## 1. Etching Procedure\n"))

    def test_load_kb_directory_loads_all_9_sop_sections(self) -> None:
        kb_dir = Path(__file__).resolve().parent.parent / "kb"
        chunks = load_kb_directory(kb_dir)
        self.assertEqual(len(chunks), 9)
        citation_ids = {c.citation_id for c in chunks}
        self.assertIn("ipc_a_600_defects#1_open_circuit_trace_break", citation_ids)
        self.assertIn("ipc_a_600_defects#2_short_circuit_copper_bridge", citation_ids)
        self.assertIn("line_halt_troubleshooting#1_batch_drift_line_halt_protocol", citation_ids)


if __name__ == "__main__":
    unittest.main()
