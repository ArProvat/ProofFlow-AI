# ProofFlow AI — Evaluation Framework, Benchmarks & Metrics

> **Core Philosophy**: A hiring manager or enterprise buyer is far more impressed by a disciplined evaluation showing *why* Architecture C outperforms Baselines A & B, than by generic claims of having multiple unmeasured agents.

---

## 🔬 Error Taxonomy

To systematically diagnose and remediate errors, every failure observed in extraction or reconciliation is tagged into one of seven standardized failure modes:

| Category | Definition | Real-World Example | Remediated By |
| :--- | :--- | :--- | :--- |
| **`OCR_ERROR`** | Degradation in character recognition from image scans. | Recognizing `8` as `3`, or `O` as `0`. | Image preprocessing, binarization, PaddleOCR confidence tuning. |
| **`LAYOUT_ERROR`** | Multi-column or table boundary misinterpretation. | Merging line items across adjacent rows or columns. | Layout analysis models (PaddleOCR-VL). |
| **`EXTRACTION_ERROR`** | Value missed or assigned to the wrong JSON key. | Picking subtotal as total, or billing date as due date. | Few-shot prompting, schema-constrained generation. |
| **`NORMALIZATION_ERROR`** | Failure to standardize parsed format. | Inverting day and month in `04/05/2026`. | Regex pattern enforcement, locale-aware date parsers. |
| **`ENTITY_MATCHING_ERROR`**| Failure to reconcile equivalent items. | Failing to link `KB-BLU-01` with `Keyboard Blue Switches`. | Levenshtein / fuzzy item matching threshold. |
| **`HALLUCINATION`** | Synthesizing a value not present in source document. | Inventing a PO reference number when none exists. | Nullable field prompting, zero-temperature extraction. |
| **`EVIDENCE_ERROR`** | Extracted field references wrong bounding box/page. | Bounding box points to company header instead of total. | Visual coordinate verification. |

---

## 📊 Core Metric Definitions

### 1. Line-Item F1 Score
Line items (description, quantity, unit price, line total) must be evaluated as an interconnected tuple:
$$\text{Precision} = \frac{\text{Correctly Extracted Line Items}}{\text{Total Extracted Line Items}}$$
$$\text{Recall} = \frac{\text{Correctly Extracted Line Items}}{\text{Total Ground-Truth Line Items}}$$
$$\text{Line-Item F1} = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$$

### 2. Critical Financial Error Rate ($R_{\text{crit}}$)
Measures the percentage of processed documents where an error occurred in an actionable financial field (Totals, Tax, Bank Accounts):
$$R_{\text{crit}} = \frac{\text{Cases with Unflagged Financial Error}}{\text{Total Processed Cases}} \times 100\%$$
*Acceptance Target for Production*: $< 0.1\%$.

### 3. Straight-Through Processing (STP) Rate
The proportion of cases that pass through the system without requiring human intervention:
$$\text{STP Rate} = \frac{\text{Cases auto-verified with 0 discrepancies}}{\text{Total Cases Ingested}} \times 100\%$$

---

## 🧪 Planned Baseline Experiments (E001–E005)

| ID | Experiment Name | Hypothesis | Setup / Variables | Decision Criteria |
| :--- | :--- | :--- | :--- | :--- |
| **`E001`** | **Native PyMuPDF vs. OCR Baseline** | Digital PDF text extraction provides 10x throughput and higher accuracy than OCR on digital invoices. | Test PyMuPDF text vs. PaddleOCR on 30 digital PDFs. | Use PyMuPDF as Tier 1 parser whenever digital text stream is present. |
| **`E002`** | **OCR-Only vs. VLM Table Extraction** | Multimodal Vision-Language Models (PaddleOCR-VL) resolve complex multi-line tables with higher F1 than rule-based OCR. | Test on 20 multi-line invoices with merged cells and borderless tables. | Adopt VLM extraction if Line-Item F1 improves by $\ge 15\%$ at acceptable latency ($< 3\text{s/page}$). |
| **`E003`** | **Deterministic vs. LLM Reconciliation** | Deterministic Python rules eliminate 100% of mathematical hallucinations found in pure LLM reconciliation. | Run 30 cases through Python 3-way matcher vs. GPT-4o zero-shot prompt. | Keep Python reconciliation engine as non-negotiable invariant. |
| **`E004`** | **Agent Tool Bounding vs. SQL Generation** | Constrained LangGraph tools prevent data leakage and hallucinated numbers compared to direct text-to-SQL. | Test 50 conversational questions across 10 adversarial prompts. | Zero SQL injections; 100% of numerical answers backed by DB query evidence. |
| **`E005`** | **Feedback-Driven Prompt Optimization** | Analyzing reviewer corrections automatically improves prompt instructions without regressing historical cases. | Run `candidate_optimizer.py` on 15 user corrections across the development split. | Promote candidate prompt only if $\Delta\text{Accuracy} > 0$ and $\Delta\text{Regressions} = 0$. |

---

## 🎬 Day 15 Final Public Demonstration Script

Follow this 6-step walkthrough during hiring interviews or customer demos:

```text
[Step 1: Ingestion & Extraction]
- Action: Drag & drop a 3-document bundle (Invoice, PO, Goods Receipt) into ProofFlow Web.
- Highlight: Rapid asynchronous processing, PDF preview, and visual bounding boxes on extracted totals.

[Step 2: Discrepancy Detection]
- Action: Open the case flagged with status "NEEDS_REVIEW".
- Highlight: ProofFlow clearly shows: "Quantity Mismatch: Invoiced 120 units, but Goods Receipt shows only 100 received".

[Step 3: Visual Evidence Grounding]
- Action: Click the discrepancy card.
- Highlight: The PDF viewer immediately jumps to Page 1 and highlights the exact bounding box on the invoice.

[Step 4: Conversational Analytics]
- Action: In the AI Chat sidebar, ask: "Which supplier had the highest discrepancy rate this month?"
- Highlight: The agent executes get_metrics(), returns a cited answer, and renders an interactive Vega-Lite chart.

[Step 5: External Interoperability via MCP]
- Action: Open an MCP test client (e.g. Claude Desktop or Python script) and query: proofflow.get_case("case-001").
- Highlight: The external agent receives clean, verified JSON findings directly from the ProofFlow server.

[Step 6: Closed-Loop Self-Improvement]
- Action: Submit a correction for a misread invoice number. Run python scripts/optimize_candidate.py.
- Highlight: Show the generated diff report displaying zero regressions on historical test cases.
```
