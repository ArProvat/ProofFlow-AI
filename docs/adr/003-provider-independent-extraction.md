# ADR 003: Provider-Independent Extraction Contracts

**Status:** Accepted  
**Date:** 2026-10-12  
**Deciders:** Core Engineering Team  

---

## Context
AI document understanding technology evolves rapidly. Today's best approach might combine PyMuPDF with PaddleOCR or an external VLM (OpenAI GPT-4o, Google Gemini, Claude, or local open-weights models like Qwen2-VL or DeepSeek-VL). Directly coupling our domain models or API endpoints to provider-specific response schemas (e.g., Azure Form Recognizer, AWS Textract, or OpenAI tool calls) would create tight vendor lock-in and impede ongoing model evaluation and benchmarking.

## Decision
We define an immutable, typed **Pydantic extraction contract (`ExtractedDocument`)** at the domain boundary:
1. All extractor implementations (local OCR, cloud VLM, or hybrid cascades) must implement a uniform interface:
   ```python
   class DocumentExtractor(Protocol):
       async def extract(self, document: Document) -> ExtractedDocument: ...
   ```
2. The domain model `ExtractedDocument` is strictly agnostic of the extraction provider.
3. Every extraction run records an `ExecutionRecord` capturing model provider, model version, latency, token consumption, and timestamp to enable rigorous comparative evaluation (Day 7 benchmarking).

## Alternatives Considered
1. **Adopting Cloud Provider Native Schemas (e.g., AWS Textract or Azure Document Intelligence SDKs directly):**
   * *Rejected:* Locks our database and domain logic into proprietary vendor representations; migrating to local self-hosted open-source models would require full rewrites.
2. **Dynamic Unvalidated JSON Dictionaries:**
   * *Rejected:* Omits type safety, allowing silent schema drifts, missing keys, and runtime `KeyError` crashes in downstream verification rules.

## Consequences
### Positive
* Ability to hot-swap extraction backends (e.g. testing local PaddleOCR against Gemini or GPT-4o) without modifying a single line of verification or UI code.
* Facilitates automated benchmark test suites where ground-truth evaluation compares different providers against the exact same contract.
* Standardized bounding box coordinate normalization `[x1, y1, x2, y2]` across all engines.

### Negative / Trade-offs
* Requires writing adapter translation layers for each integrated OCR or VLM service.

## Conditions to Revisit
* Emergence of an industry-wide open standard schema for document visual intelligence with universal vendor adoption.
