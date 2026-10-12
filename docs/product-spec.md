# ProofFlow AI — Product Requirements Document (PRD)

**Document Version:** 1.0.0  
**Phase:** 15-Day MVP · Day 1 Foundation  
**Status:** Approved  
**Target Milestone:** Accounts Payable & Procurement 3-Way Reconciliation MVP  

---

## 1. Problem Statement & User Persona

### 1.1 The User Persona
* **Primary Persona:** Accounts Payable (AP) Specialist / Procurement Reviewer.
* **Secondary Persona:** Finance Operations Lead / Compliance Auditor.
* **Context:** Mid-market organizations processing hundreds to thousands of supplier invoices monthly against Purchase Orders (POs) and Goods Received Notes (GRNs) / Delivery Receipts.

### 1.2 The Problem
Manual invoice matching ("three-way matching") is time-intensive, cognitively draining, and error-prone:
* Reviewers cross-reference numbers across multiple messy PDFs, scans, and emails.
* Overbilling (invoiced quantity > received quantity), price slippage (unit price > PO agreement), arithmetic errors, duplicate submissions, and unexpected surcharges slip through.
* When discrepancies occur, compiling evidence for vendors requires manual screenshots and transcriptions.
* Existing enterprise OCR solutions are brittle (template-bound), while pure LLM wrappers suffer from hallucinations, non-deterministic math, and a lack of auditability.

### 1.3 Desired Outcome
ProofFlow AI automates three-way reconciliation by:
1. Parsing unstructured multi-format documents (PDF, PNG, JPEG) into structured data contracts.
2. Linking every extracted numerical and textual entity directly to visual/page evidence coordinates.
3. Applying strict, deterministic Python verification rules (not LLM arithmetic).
4. Generating traceable discrepancies with exact citations.
5. Routing uncertain, missing, or mismatched cases to human reviewers while approving clean matches.

---

## 2. Core User Story & Interaction Flow

### 2.1 Foundational User Story
> **As an** Accounts Payable reviewer,  
> **I want to** upload an invoice, a purchase order, and a goods received note for a transaction,  
> **So that** ProofFlow AI can automatically identify discrepancies, compute arithmetic consistency, and highlight the exact document evidence without requiring me to manually cross-compare every line item.

### 2.2 First Successful Interaction (The "Golden Path" & Exception Example)

**Inputs:**
* **Purchase Order (PO-4091):** 100 Mechanical Keyboards @ $20.00 each = $2,000.00. Supplier: "Acme Logistics Ltd".
* **Goods Received Note (GRN-882):** 100 Mechanical Keyboards received in good condition. Received date: 2026-10-05.
* **Supplier Invoice (INV-9902):** 120 Mechanical Keyboards @ $20.00 each = $2,400.00. Supplier: "Acme Logistics Ltd".

**Expected ProofFlow Result:**
* **Decision:** `NEEDS_REVIEW`
* **Finding:** `QUANTITY_MISMATCH` (Rule R003)
* **Severity:** `ERROR`
* **Evidence:**
  * Invoice `INV-9902`, Page 1: Quantity `120` [BBox: [0.62, 0.44, 0.68, 0.47]]
  * Goods Receipt `GRN-882`, Page 1: Received Quantity `100` [BBox: [0.55, 0.51, 0.60, 0.54]]
* **User Action:** Reviewer inspects side-by-side evidence with highlighted bounding boxes, confirms 20 units were never received, and rejects the excess line item or triggers a vendor dispute notice.

---

## 3. Product Scope & MVP Constraints

| Dimension | MVP Policy (Days 1–15) | Post-MVP / Production Scope |
| :--- | :--- | :--- |
| **Supported File Formats** | PDF (native & scanned), PNG, JPEG | TIFF, DOCX, XLSX, Multi-page TIFF |
| **Document Types** | Invoices, Purchase Orders, Goods Received Notes (GRN) | Credit notes, bill of lading, contracts, tax receipts |
| **Language Support** | English (core), initial Bengali-English dual receipts | Multilingual (Spanish, German, Arabic, Japanese) |
| **Reconciliation Scope** | 3-Way Match per isolated transaction case | Cumulative delivery batches, multi-PO split invoices |
| **User & Tenant Model** | Single authenticated reviewer / demo workspace | Multi-tenant RBAC, enterprise SSO (SAML/Okta) |
| **Financial Execution** | Read-only analysis & human decision queue; **NO autonomous payments** | ERP write-back (SAP, NetSuite, QuickBooks) |
| **Data Storage** | PostgreSQL (relational metadata) + Local/S3-compatible blob storage | Encrypted S3/GCS with retention vaults & DLP |
| **AI Processing** | Configurable OCR (PaddleOCR/PyMuPDF) + VLM/LLM extraction | Hybrid cascade with fine-tuned local models |
| **Human In The Loop** | Mandatory approval for any `NEEDS_REVIEW` or `FAILED` case | Automated confidence-tiered STP (Straight-Through-Processing) |

---

## 4. Key Functional Requirements

1. **Document Ingestion:**
   * Validate MIME type, file size (max 25MB), and page count (max 20 pages per doc).
   * Store immutable original file; assign persistent UUID.
2. **Extraction Contract:**
   * Extract header metadata (Supplier, Document ID, Issue Date, Currency).
   * Extract line item tables (SKU, Description, Quantity, Unit Price, Line Total).
   * Extract summary totals (Subtotal, Tax, Grand Total).
   * Preserve source page and bounding box coordinates for each field where available.
   * Represent missing fields strictly as `None` / `null` (never guess or default to zero).
3. **Deterministic Verification Engine:**
   * Execute business verification rules R001–R008.
   * Enforce Decimal arithmetic; zero floating-point imprecision.
   * Provide explicit reason strings and evidence links for every finding.
4. **Auditability & Execution Tracking:**
   * Every model inference run logged with model name, prompt template version, execution time, and raw output.
   * Human reviews stored as immutable append-only events (no overwriting model extractions).

---

## 5. Success Metrics & Quality Criteria

* **Extraction Precision:** $\ge 95\%$ on standard header fields (Invoice #, Date, Total).
* **Extraction Recall on Line Items:** $\ge 90\%$ across structured invoices.
* **Deterministic Verification Accuracy:** $100\%$ rule execution accuracy on valid extracted inputs.
* **False Approval Rate:** $0.0\%$ (No case with overbilled quantity or mismatched supplier may pass as `VERIFIED`).
* **Processing Latency:** $\le 10$ seconds end-to-end for a standard 3-document case.
* **Evidence Citation Coverage:** $100\%$ of flagged findings must link to at least one document ID and page number.
