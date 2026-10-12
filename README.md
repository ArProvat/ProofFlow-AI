# ProofFlow AI

> **Verifiable Document-to-Action Intelligence for Procurement & Accounts Payable**

ProofFlow AI is an auditable three-way document reconciliation system that extracts structured financial data from Purchase Orders, Goods Received Notes (GRN), and Supplier Invoices, links every extracted entity directly to visual document evidence, and applies deterministic verification rules to detect overbilling, price drift, arithmetic errors, and supplier mismatches.

---

## 15-Day MVP Architecture & Principles

ProofFlow enforces a strict separation of concerns:
* **Perception / Extraction:** OCR and Vision-Language Models parse visual document pixels into typed, immutable domain contracts (`ExtractedDocument`).
* **Deterministic Verification:** Pure Python verification rules (R001–R008) perform exact `Decimal` arithmetic. **No LLM is permitted to approve invoices or calculate financial math.**
* **Auditable Human Governance:** Discrepancies and uncertainties trigger `NEEDS_REVIEW` with exact coordinate bounding boxes and excerpts for human reviewer sign-off.

---

## Day 1 Architecture & Specifications

* **[Product Requirements Document (PRD)](docs/product-spec.md):** User personas, core user stories, scope constraints, and acceptance criteria.
* **[System Architecture & Trust Boundaries](docs/architecture.md):** Modular monolith design, lifecycle state machines, and indirect prompt injection defenses.
* **[Verification Rules Specification](docs/verification-rules.md):** Catalog of rules R001–R008 with inputs, decisions, and edge cases.
* **[REST API Contract](docs/api-contract.md):** Complete endpoint specifications, request/response models, and error envelopes.
* **[Day 2 Dataset Specification](docs/day-2-dataset-spec.md):** Six foundational ground truth test scenarios.
* **Architecture Decision Records (ADRs):**
  * [ADR 001: Modular Monolith with Background Worker](docs/adr/001-modular-monolith.md)
  * [ADR 002: Deterministic Python Verification](docs/adr/002-deterministic-verification.md)
  * [ADR 003: Provider-Independent Extraction Contracts](docs/adr/003-provider-independent-extraction.md)

---

## Getting Started

### Prerequisites
* Python 3.12+ (tested on Python 3.13)
* `uv` package manager

### Installation
```bash
# Sync dependencies and development tools
uv sync --extra dev
```

### Running Tests & Linting
```bash
# Run automated test suite
uv run pytest -q

# Run code style & lint checks
uv run ruff check .
```

### Starting the API Server
```bash
# Launch FastAPI development server
uv run uvicorn proofflow.api.main:app --reload
```
Interactive OpenAPI documentation will be accessible at: `http://127.0.0.1:8000/docs`
