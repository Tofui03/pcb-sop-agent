# pcb-sop-agent — IPC-A-600 & Line Halt SOP RAG Service

Industrial Retrieval-Augmented Generation (RAG) microservice for **DeepPCB-AOI** and **PCB Inspection Viewer**, providing **citation-grounded** Standard Operating Procedure (SOP) answers with deterministic verification (`CitationGuard`).

---

## Architecture & Core Engineering Habits

1. **Contract-First Schemas (`core/schemas.py`)**:
   - Strict Pydantic data contracts (`SopChunk`, `RetrievedHit`, `SopQueryRequest`, `SopAnswerResponse`) with validator-enforced `doc_id#section_slug` citation IDs.
2. **Zero Cross-Section Contamination Chunker (`core/chunker.py`)**:
   - Splits SOP Markdown documents strictly on `## ` (H2) boundaries so `Open` (`SCRAP`) and `Mousebite` (`PASS`/`REWORK`) policies never bleed into the same chunk.
   - Applies sliding-window overlap *only* within a single oversized section while preserving its parent `## ` header.
3. **Deterministic BM25 + AOI Metadata Boosting (`core/retriever.py`)**:
   - Pure-Python Okapi BM25 (`k1=1.5`, `b=0.75`) over SOP chunks with structured boosts for `defect_class` (`Open`, `Short`, `Mousebite`, `Spur`, `Spurious_Copper`, `Pin-hole`) and Stage 4 `halt_production_line=True` alerts.
4. **CitationGuard & Deterministic Offline Fallback (`core/citation_guard.py`)**:
   - Verifies every inline `[doc_id#section_slug]` citation against the retrieved top-k chunks.
   - Rejects uncited answers, hallucinated citation IDs, or unsafe claims (e.g., claiming `Open` or `Short` can `PASS`), automatically falling back to `build_deterministic_sop_answer()`.

---

## API Endpoints (`api/main.py`)

- `GET /api/health` — Returns service health and indexed SOP chunk count (`9` sections across `kb/`).
- `GET /api/chunks` — Lists all indexed `SopChunk` records with deterministic `citation_id`s.
- `POST /api/query` — Accepts `SopQueryRequest` (`question`, optional `defect_class`, `ipc_class`, `halt_production_line`, `top_k`) and returns `SopAnswerResponse`.

---

## Quick Start & Testing

```bash
# Run the full unit test suite (Chunker + Schemas + BM25 + CitationGuard + FastAPI)
python3 -m unittest discover -s tests -v

# Start the FastAPI server
uvicorn api.main:app --host 0.0.0.0 --port 8010
```
