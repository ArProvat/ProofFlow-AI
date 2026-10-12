# ProofFlow AI — Day 2 Dataset Specification & Test Scenarios

**Document Version:** 1.0.0  
**Status:** Approved  
**Target Milestone:** Day 2 Dataset Preparation & Verification Ground Truth  

---

## 1. Objectives

To rigorously validate extraction models and verification rules without relying on subjective human impressions, Day 2 establishes a benchmark dataset of synthetic and real-world sample document trios (Purchase Order, Goods Receipt, Supplier Invoice) paired with machine-readable ground truth annotations.

---

## 2. Six Foundational Day 2 Test Scenarios

| Scenario ID | Scenario Name | PO Input | GRN Input | Invoice Input | Expected Decision | Primary Finding / Rule | Rationale |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SC-01** | Clean Exact Match | 100 Keyboards @ $20.00 | 100 Keyboards | 100 Keyboards @ $20.00 | `VERIFIED` | None | Baseline clean golden path; all rules pass. |
| **SC-02** | Quantity Overbilling | 100 Keyboards @ $20.00 | 100 Keyboards | 120 Keyboards @ $20.00 | `NEEDS_REVIEW` | `R003: QUANTITY_MISMATCH` | Invoiced quantity (120) exceeds received quantity (100). |
| **SC-03** | Valid Partial Delivery | 100 Keyboards @ $20.00 | 60 Keyboards | 60 Keyboards @ $20.00 | `VERIFIED` | None | Permitted partial shipment: invoiced == received <= ordered. |
| **SC-04** | Supplier Identity Mismatch | PO: "Acme Logistics Ltd" | GRN: "Acme Logistics Ltd" | INV: "Global Express Corp" | `NEEDS_REVIEW` | `R001: SUPPLIER_MISMATCH` | Vendor on invoice does not match PO vendor entity. |
| **SC-05** | Missing Required Field | 100 Keyboards @ $20.00 | 100 Keyboards | Missing quantity (unreadable) | `NEEDS_REVIEW` | `R007: INSUFFICIENT_DATA` | Incomplete extraction must never default to zero or auto-approve. |
| **SC-06** | Engine / OCR Pipeline Failure | Valid PO | Valid GRN | Corrupted / unparseable binary | `FAILED` | Technical Failure | System must register `FAILED` state and block downstream approval. |

---

## 3. Extended Regression & Stress Scenarios

* **SC-07: Unit Price Drift (`R004: PRICE_MISMATCH`):** PO unit price is $20.00, invoice charges $22.50.
* **SC-08: Arithmetic Subtotal Error (`R005: TOTAL_MISMATCH`):** Invoiced line items sum to $2,000.00, but stated grand total reads $2,150.00 without explanation.
* **SC-09: Currency Mismatch (`R008: CURRENCY_MISMATCH`):** PO in `USD`, Invoice issued in `EUR`.
* **SC-10: Duplicate Invoice (`R006: DUPLICATE_INVOICE`):** Identical invoice number from same vendor submitted twice.
* **SC-11: Ambiguous Description (`R002: ITEM_NOT_MATCHED`):** PO specifies "Mechanical Keyboard USB-C", Invoice specifies "Ergonomic Monitor Arm".
* **SC-12: Multi-Language / Script:** Bengali-English dual invoice (bilingual line items and numerals).

---

## 4. Ground Truth Fixture Data Schema

Every scenario fixture in `tests/fixtures/scenarios/` will consist of:
1. `po.pdf` / `po.png`: Source document visual.
2. `grn.pdf` / `grn.png`: Goods received receipt visual.
3. `invoice.pdf` / `invoice.png`: Supplier invoice visual.
4. `ground_truth.json`: Clean expected extraction contract and target verification decision.

### Ground Truth JSON Example (`sc-01-clean-match.json`):
```json
{
  "scenario_id": "SC-01",
  "name": "Clean Exact Match",
  "expected_outcome": "VERIFIED",
  "expected_findings": [],
  "documents": {
    "purchase_order": {
      "document_type": "PURCHASE_ORDER",
      "supplier_name": "Acme Logistics Ltd",
      "po_number": "PO-4091",
      "currency": "USD",
      "line_items": [
        {
          "sku": "KB-01",
          "description": "Mechanical Keyboard USB-C",
          "quantity": "100",
          "unit_price": "20.00",
          "line_total": "2000.00"
        }
      ],
      "grand_total": "2000.00"
    },
    "goods_receipt": {
      "document_type": "GOODS_RECEIPT",
      "po_number": "PO-4091",
      "line_items": [
        {
          "sku": "KB-01",
          "description": "Mechanical Keyboard USB-C",
          "quantity": "100"
        }
      ]
    },
    "invoice": {
      "document_type": "INVOICE",
      "supplier_name": "Acme Logistics Ltd",
      "invoice_number": "INV-9901",
      "po_number": "PO-4091",
      "currency": "USD",
      "line_items": [
        {
          "sku": "KB-01",
          "description": "Mechanical Keyboard USB-C",
          "quantity": "100",
          "unit_price": "20.00",
          "line_total": "2000.00"
        }
      ],
      "grand_total": "2000.00"
    }
  }
}
```
