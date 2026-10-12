# ProofFlow AI — Verification Rules Specification

**Document Version:** 1.0.0  
**Status:** Approved  
**Module:** Deterministic Verification Engine  

---

## 1. System Philosophy & Outcomes

ProofFlow separates **Document Extraction** (probabilistic OCR / Vision-Language Model) from **Business Verification** (deterministic Python rules).

* **Model Extraction Answer:** *"What text, numbers, and bounding boxes are present in these documents?"*
* **Verification Engine Answer:** *"Does this extracted data satisfy our business and financial invariants?"*

### The Three Business Outcomes
Every verification run concludes with exactly one case-level outcome:
1. `VERIFIED`: All required documents are present, all applicable rules (R001–R008) executed, and zero violations or unverified uncertainties were found.
2. `NEEDS_REVIEW`: A discrepancy was detected (e.g., price mismatch, overbilling), a required field was missing from extraction, or an unsupported business condition was encountered (e.g., unhandled currency conversion). A human reviewer must inspect the findings.
3. `FAILED`: A technical or validation exception occurred (e.g., unreadable corrupted file, model crash, timeout) preventing deterministic verification. **A technical failure never falls back to auto-approval.**

---

## 2. Business Policies

### 2.1 Partial Delivery Policy
* An order for $N$ units may be delivered and billed in smaller partial batches.
* **Condition:** If `invoiced_quantity == received_quantity` and `invoiced_quantity <= ordered_quantity`, this partial delivery is **permitted** and can pass rule R003.
* **Limitation for MVP:** Cumulative multi-shipment tracking across multiple historical cases is out of scope for Day 1. Each verification case evaluates the three uploaded documents in isolation.

### 2.2 Currency & Rounding Policy
* All financial values must be parsed and stored as Python `Decimal` with explicit quantization (e.g., 2 decimal places for USD, EUR, BDT).
* No floating-point operations are permitted.
* If currencies differ between documents, R008 triggers `CURRENCY_MISMATCH`. Currency conversion is explicitly flagged for human review.

### 2.3 Tax, Discount & Arithmetic Tolerances
* Line totals: `quantity * unit_price == line_total` within a strict rounding tolerance of $\pm 0.01$ (to allow for fractional cent rounding on unit rates).
* Grand total: `subtotal + tax_amount - discount == grand_total` within $\pm 0.02$.
* If tax rules or discounts cannot be deterministically verified from document excerpts, flag `TOTAL_MISMATCH` or `INSUFFICIENT_DATA`.

---

## 3. Detailed Verification Rules Catalog (R001 – R008)

### R001: Supplier Identity Agreement
* **Rule ID:** `R001`
* **Failure Outcome:** `SUPPLIER_MISMATCH`
* **Severity:** `ERROR`
* **Inputs:** `Invoice.supplier_name`, `PurchaseOrder.supplier_name`.
* **Decision Logic:**
  * Normalize names (lowercase, trim whitespace, strip corporate suffixes such as "Inc", "LLC", "Ltd", "Corp").
  * Check for string equality or approved alias mapping.
  * If normalized strings do not match, generate finding.
* **Edge Cases:** Legal entity name vs Doing-Business-As (DBA) trade name; subsidiary vendors. In MVP, unmapped aliases trigger `SUPPLIER_MISMATCH`.
* **Positive Example:**
  * PO Supplier: `"Acme Logistics Ltd."`
  * Invoice Supplier: `"Acme Logistics, LLC"`
  * Normalized: `"acme logistics"` == `"acme logistics"` $\rightarrow$ **PASS**.
* **Negative Example:**
  * PO Supplier: `"Acme Logistics Ltd."`
  * Invoice Supplier: `"Beta Supply Corp."`
  * Outcome: **FAIL** (`SUPPLIER_MISMATCH`).

---

### R002: Line Item Reconciliation & Matching
* **Rule ID:** `R002`
* **Failure Outcome:** `ITEM_NOT_MATCHED`
* **Severity:** `ERROR`
* **Inputs:** `Invoice.line_items`, `PurchaseOrder.line_items`, `GoodsReceipt.line_items`.
* **Decision Logic:**
  * Match items first by exact SKU/part number if present.
  * If SKU is absent, match by normalized description similarity (token set ratio $\ge 0.85$).
  * If an invoice contains items that cannot be tied to the PO, flag `ITEM_NOT_MATCHED`.
* **Edge Cases:** Bundled products, alternative part numbers, service descriptions with differing dates.
* **Positive Example:**
  * PO: SKU `KB-01` ("Mechanical Keyboard USB-C")
  * Invoice: SKU `KB-01` ("Mech Keyboard USB")
  * Match confirmed $\rightarrow$ **PASS**.
* **Negative Example:**
  * Invoice lists item: `"Ergonomic Wrist Rest"` (No matching item or SKU on PO).
  * Outcome: **FAIL** (`ITEM_NOT_MATCHED`).

---

### R003: Quantity Compliance (No Overbilling)
* **Rule ID:** `R003`
* **Failure Outcome:** `QUANTITY_MISMATCH`
* **Severity:** `ERROR`
* **Inputs:** `Invoice.item.quantity`, `GoodsReceipt.item.quantity`, `PurchaseOrder.item.quantity`.
* **Decision Logic:**
  * For each matched item:
    * Ensure `invoiced_quantity <= received_quantity`.
    * Ensure `invoiced_quantity <= ordered_quantity`.
  * If `invoiced_quantity > received_quantity`, flag `QUANTITY_MISMATCH`.
* **Edge Cases:** Bulk goods (sand, grain, liquids) where $\pm 5\%$ variance is contractually allowed. In MVP, exact threshold $\le$ applies unless overridden by review.
* **Positive Example:**
  * PO Ordered: 100
  * GRN Received: 60
  * Invoice Billed: 60
  * Outcome: **PASS** (Permitted partial delivery).
* **Negative Example:**
  * PO Ordered: 100
  * GRN Received: 100
  * Invoice Billed: 120
  * Outcome: **FAIL** (`QUANTITY_MISMATCH`: Billed 120, Received 100).

---

### R004: Unit Price Verification
* **Rule ID:** `R004`
* **Failure Outcome:** `PRICE_MISMATCH`
* **Severity:** `ERROR`
* **Inputs:** `Invoice.item.unit_price`, `PurchaseOrder.item.unit_price`.
* **Decision Logic:**
  * For each matched item, verify `Invoice.item.unit_price == PurchaseOrder.item.unit_price`.
  * A price increase on the invoice without an updated PO is an invariant violation.
* **Edge Cases:** Tiered volume pricing; agreed fuel or shipping surcharges.
* **Positive Example:**
  * PO Price: `$20.00`
  * Invoice Price: `$20.00`
  * Outcome: **PASS**.
* **Negative Example:**
  * PO Price: `$20.00`
  * Invoice Price: `$22.50`
  * Outcome: **FAIL** (`PRICE_MISMATCH`: Expected $20.00, Found $22.50).

---

### R005: Arithmetic & Mathematical Consistency
* **Rule ID:** `R005`
* **Failure Outcome:** `TOTAL_MISMATCH`
* **Severity:** `ERROR`
* **Inputs:** `LineItem.quantity`, `LineItem.unit_price`, `LineItem.line_total`, `ExtractedDocument.subtotal`, `ExtractedDocument.tax_amount`, `ExtractedDocument.grand_total`.
* **Decision Logic:**
  1. For each line item: $|(\text{quantity} \times \text{unit\_price}) - \text{line\_total}| \le 0.01$.
  2. Subtotal check: $|\sum(\text{line\_total}) - \text{subtotal}| \le 0.02$.
  3. Grand total check: $|(\text{subtotal} + \text{tax\_amount} - \text{discount}) - \text{grand\_total}| \le 0.02$.
* **Edge Cases:** Invoices omitting subtotal or displaying post-tax line totals.
* **Positive Example:**
  * Line 1: 3 @ $19.99 = $59.97. Tax = $0.00. Grand Total = $59.97 $\rightarrow$ **PASS**.
* **Negative Example:**
  * Line 1: 3 @ $20.00 = $60.00. Line 2: 1 @ $10.00 = $10.00. Stated Grand Total = $75.00.
  * Computed: $70.00 $\neq$ Stated: $75.00.
  * Outcome: **FAIL** (`TOTAL_MISMATCH`: Arithmetic variance $5.00).

---

### R006: Duplicate Invoice Detection
* **Rule ID:** `R006`
* **Failure Outcome:** `DUPLICATE_INVOICE`
* **Severity:** `ERROR`
* **Inputs:** `Invoice.supplier_name`, `Invoice.invoice_number`, `Workspace.historical_invoices`.
* **Decision Logic:**
  * Check existing verified/processing invoices within the workspace for identical `(normalized_supplier, invoice_number)`.
  * If found on another active or paid case, flag immediately.
* **Edge Cases:** Vendor resubmitting revised invoice with identical number after prior rejection.
* **Positive Example:**
  * Vendor: "Acme Logistics", Invoice #: "INV-2026-001" (first time seen in workspace) $\rightarrow$ **PASS**.
* **Negative Example:**
  * Vendor: "Acme Logistics", Invoice #: "INV-2026-001" (already verified and recorded in Case #104) $\rightarrow$ **FAIL** (`DUPLICATE_INVOICE`).

---

### R007: Mandatory Field & Evidence Sufficiency
* **Rule ID:** `R007`
* **Failure Outcome:** `INSUFFICIENT_DATA`
* **Severity:** `WARNING` / `ERROR`
* **Inputs:** All required fields on `ExtractedDocument` (`supplier_name`, `invoice_number`, `currency`, `grand_total`, `line_items`).
* **Decision Logic:**
  * If any mandatory header field is `None` or line items list is empty, trigger `INSUFFICIENT_DATA`.
  * If an extracted value has no valid `EvidenceRef` (missing page pointer), flag uncertainty.
* **Edge Cases:** Scanned receipt with obliterated total corner.
* **Positive Example:**
  * All header fields and line items populated with valid `EvidenceRef(page=1)` $\rightarrow$ **PASS**.
* **Negative Example:**
  * Invoice extraction succeeded on supplier and line items, but `grand_total is None` due to image blur.
  * Outcome: **FAIL** (`INSUFFICIENT_DATA`: Missing required field `grand_total`).

---

### R008: Currency Agreement
* **Rule ID:** `R008`
* **Failure Outcome:** `CURRENCY_MISMATCH`
* **Severity:** `ERROR`
* **Inputs:** `Invoice.currency`, `PurchaseOrder.currency`.
* **Decision Logic:**
  * Verify ISO currency codes match (e.g., `USD` == `USD`, `EUR` == `EUR`, `BDT` == `BDT`).
  * If different, flag for manual review (cross-currency triangulation deferred post-MVP).
* **Positive Example:**
  * PO: `USD`, Invoice: `USD` $\rightarrow$ **PASS**.
* **Negative Example:**
  * PO: `USD`, Invoice: `EUR` $\rightarrow$ **FAIL** (`CURRENCY_MISMATCH`: PO currency USD does not match Invoice currency EUR).
