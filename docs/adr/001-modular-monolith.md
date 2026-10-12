# ADR 001: Adopt Modular Monolith with Asynchronous Background Worker

**Status:** Accepted  
**Date:** 2026-10-12  
**Deciders:** Core Engineering Team  

---

## Context
ProofFlow AI requires document ingestion, OCR/VLM text extraction, deterministic financial reconciliation, human review workflows, and analytical auditing. At the initial MVP stage, developing distributed microservices introduces operational overhead, network latency, distributed transaction complexities, and deployment friction that distracts from the core machine-learning and domain-rule verification challenge.

## Decision
We adopt a **modular monolith** architecture backed by a separate background worker:
1. **Single Repository & Shared Domain:** The API, worker, and verification rules live in a single unified codebase (`src/proofflow`) with strictly isolated internal module boundaries.
2. **Dedicated Background Processing:** Heavy OCR, PDF parsing, and VLM extraction execute asynchronously in background worker jobs without blocking FastAPI request threads.
3. **Unified Relational Store:** PostgreSQL serves as the single source of truth for transactional states, audit logs, and extraction metadata.

## Alternatives Considered
1. **Microservices Architecture (Document Service, Verification Service, Review Service):**
   * *Rejected:* Excessive infrastructure overhead, cross-service schema synchronization pain, and premature optimization for an MVP processing thousands rather than millions of documents per day.
2. **Serverless Functions (AWS Lambda / Cloud Functions):**
   * *Rejected:* Cold starts, binary size limits for OCR models (PyMuPDF / PaddleOCR), and 15-minute execution timeouts create fragility for batch document processing.

## Consequences
### Positive
* Fast local iteration, simple single-command testing (`uv run pytest`), and rapid schema evolution.
* Direct in-memory function calls between domain modules while maintaining logical decoupling.
* Streamlined end-to-end debugging and straightforward CI/CD deployments.

### Negative / Trade-offs
* Requires developer discipline to prevent cross-module circular imports or direct leaking of storage concerns into domain verification.
* Compute scaling for CPU/GPU-heavy extraction must scale worker processes independently from lightweight API gateway processes.

## Conditions to Revisit
* Document processing throughput exceeds 10,000 documents/hour.
* Specialized hardware requirements (e.g., GPU clusters for local open-source VLMs) necessitate completely segregated worker infrastructure.
