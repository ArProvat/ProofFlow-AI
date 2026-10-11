# ProofFlow AI — MVP Plan & Technical Blueprint

> **Verifiable Multimodal Document-to-Action Platform with Agentic Workflows, Conversational Analytics, and Closed-Loop Self-Improvement.**

---

## 📌 Executive Summary

**ProofFlow AI** transforms messy, unstructured real-world business documents (scanned invoices, purchase orders, goods-received notes) into verified, structured business actions. 

Instead of an ordinary RAG chatbot or raw OCR extraction demo, ProofFlow combines:
1. **Multimodal Document Intelligence**: OCR (PyMuPDF / PaddleOCR) + Vision-Language Models (PaddleOCR-VL / open-weight VLMs).
2. **Deterministic Verification Engine**: Precise 3-way reconciliation (PO vs. Invoice vs. Goods Receipt) with strict mathematical verification and audit provenance.
3. **Agentic Workflows & Analytics**: LangGraph-orchestrated conversational analytics ("talk with your data") with verified Vega-Lite charts and Mermaid diagrams.
4. **Universal Interoperability**: Model Context Protocol (MCP) server + REST API for enterprise and external AI agent connectivity.
5. **Closed-Loop Self-Improvement**: Traced execution records, feedback-driven error classification, offline prompt/rule optimization, and regression-gated deployments.

---

## 📂 Documentation Directory

| Document | Purpose & Key Topics |
| :--- | :--- |
| **[01. 15-Day MVP Roadmap](file:///c:/provat/proofflow/docs/mvp-plan/01-15-day-roadmap.md)** | Day-by-day execution guide (Days 1–15), phase objectives, deliverables, Definition of Done, and contingency priorities (P0/P1/P2). |
| **[02. System Architecture](file:///c:/provat/proofflow/docs/mvp-plan/02-system-architecture.md)** | End-to-end component architecture, LangGraph state machine, MCP server tools, and closed-loop self-improvement engine. |
| **[03. Product Spec & Rules](file:///c:/provat/proofflow/docs/mvp-plan/03-product-spec-and-rules.md)** | Canonical schemas, 3-way matching rules, state machine, REST API contracts, and JSON payloads with bounding-box evidence. |
| **[04. Evaluation & Metrics](file:///c:/provat/proofflow/docs/mvp-plan/04-evaluation-and-metrics.md)** | Error taxonomy, baseline experiments (E001–E005), benchmark metrics (Line-Item F1, Critical Error Rate), and Day 15 demonstration script. |

---

## 🎯 Target Deliverable: ProofFlow MVP v0.1

By Day 15, ProofFlow will support:
- [x] Uploading and parsing complex multi-page document bundles (Invoice + PO + Goods Receipt).
- [x] Extracting structured data with exact bounding-box evidence and source page references.
- [x] Catching financial and quantity discrepancies deterministically without model hallucination.
- [x] Human-in-the-loop review interface for auditing discrepancies and submitting corrections.
- [x] Conversational agent answering data questions backed exclusively by verified database queries.
- [x] Dynamic generation of validated Vega-Lite charts and Mermaid process diagrams.
- [x] MCP server allowing external AI agents to query cases and metrics securely.
- [x] Offline self-improvement analyzer proposing candidate prompt adjustments from logged reviewer corrections.
- [x] Turnkey deployment via `docker compose up`.
