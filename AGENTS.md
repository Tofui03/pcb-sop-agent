# pcb-sop-agent — Engineering & Agent Guidelines

Industrial PCB Defect & IPC-A-600 SOP Retrieval-Augmented Generation (RAG) service with deterministic citation verification.

## Architecture & Invariants

1. **Citation-Grounded Answers (`CitationGuard`)**:
   - Every answer must cite retrieved SOP sections using `[doc_id#section_id]`.
   - Code-level validation verifies that all cited IDs exist in the retrieved top-k chunks and rejects hallucinated citations or out-of-scope claims.
   - Deterministic template fallback must work when no external LLM API key is configured.
2. **Graphify Navigation Rules**:
   - Use Graphify (`graphify query` via a lightweight `flash` subagent) for cross-module dependency analysis; skip Graphify when editing a known single file and line range.
