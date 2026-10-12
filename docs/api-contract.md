# ProofFlow AI — API Specification & Contract

**Version:** 0.1.0  
**Base URL:** `/api/v1`  
**Protocol:** HTTPS / JSON (Multipart for file uploads)  

---

## 1. Authentication & Common Headers

All API requests operate within an authorized tenant workspace context.

| Header | Required | Description | Example |
| :--- | :--- | :--- | :--- |
| `Authorization` | Yes | Bearer JWT token identifying the reviewer | `Bearer eyJhbGci...` |
| `X-Workspace-Id` | Yes | Target tenant workspace identifier | `ws-demo-01` |
| `Content-Type` | Conditional | `application/json` (or `multipart/form-data` for file uploads) | `application/json` |

### Standard Error Response Format
All 4xx and 5xx responses return a consistent structure:
```json
{
  "error_code": "RESOURCE_NOT_FOUND",
  "message": "Verification case with ID 'case-001' does not exist.",
  "details": {},
  "timestamp": "2026-10-12T08:30:00Z"
}
```

---

## 2. API Endpoints Catalog

### 2.1 Document Management

#### `POST /api/v1/documents`
Uploads a document file (PDF, PNG, JPEG). Validates size and MIME type, saves to storage, and enqueues background text extraction.

* **Content-Type:** `multipart/form-data`
* **Form Fields:**
  * `file`: Binary file stream (max 25MB, max 20 pages).
  * `document_type`: Enum (`INVOICE`, `PURCHASE_ORDER`, `GOODS_RECEIPT`).
* **Response `201 Created`:**
```json
{
  "id": "doc-inv-101",
  "workspace_id": "ws-demo-01",
  "filename": "supplier_invoice_9902.pdf",
  "mime_type": "application/pdf",
  "file_size_bytes": 142850,
  "status": "PROCESSING",
  "uploaded_at": "2026-10-12T08:30:00Z"
}
```

#### `GET /api/v1/documents/{id}`
Retrieves document status, metadata, and extracted data contract if extraction is finished.

* **Response `200 OK`:**
```json
{
  "id": "doc-inv-101",
  "workspace_id": "ws-demo-01",
  "filename": "supplier_invoice_9902.pdf",
  "status": "EXTRACTED",
  "extracted_data": {
    "document_id": "doc-inv-101",
    "document_type": "INVOICE",
    "supplier_name": "Acme Logistics Ltd",
    "invoice_number": "INV-9902",
    "po_number": "PO-4091",
    "issue_date": "2026-10-06",
    "currency": "USD",
    "line_items": [
      {
        "sku": "KB-01",
        "description": "Mechanical Keyboard USB-C",
        "quantity": "120",
        "unit_price": "20.00",
        "line_total": "2400.00",
        "evidence": {
          "document_id": "doc-inv-101",
          "page": 1,
          "bbox": [0.62, 0.44, 0.68, 0.47],
          "excerpt": "Mechanical Keyboard USB-C | 120 | $20.00 | $2,400.00"
        }
      }
    ],
    "subtotal": "2400.00",
    "tax_amount": "0.00",
    "grand_total": "2400.00"
  }
}
```

---

### 2.2 Reconciliation Cases

#### `POST /api/v1/cases`
Creates a reconciliation case grouping an invoice, purchase order, and goods received note.

* **Request Body:**
```json
{
  "invoice_document_id": "doc-inv-101",
  "purchase_order_document_id": "doc-po-202",
  "goods_receipt_document_id": "doc-grn-303"
}
```
* **Response `201 Created`:**
```json
{
  "id": "case-9901",
  "workspace_id": "ws-demo-01",
  "invoice_document_id": "doc-inv-101",
  "purchase_order_document_id": "doc-po-202",
  "goods_receipt_document_id": "doc-grn-303",
  "status": "READY",
  "findings": [],
  "created_at": "2026-10-12T08:31:00Z"
}
```

#### `POST /api/v1/cases/{id}/verify`
Triggers the deterministic verification pipeline for the case.

* **Response `202 Accepted`:**
```json
{
  "case_id": "case-9901",
  "job_id": "job-ver-5510",
  "status": "QUEUED"
}
```

#### `GET /api/v1/cases/{id}`
Returns case details, verification status, and all detected findings with visual evidence references.

* **Response `200 OK` (when verification found a discrepancy):**
```json
{
  "id": "case-9901",
  "workspace_id": "ws-demo-01",
  "status": "NEEDS_REVIEW",
  "findings": [
    {
      "id": "fnd-01",
      "rule_id": "R003",
      "outcome": "QUANTITY_MISMATCH",
      "severity": "ERROR",
      "message": "Invoiced quantity (120) exceeds received quantity (100) for SKU 'KB-01'.",
      "expected_value": "100",
      "actual_value": "120",
      "evidence_refs": [
        {
          "document_id": "doc-inv-101",
          "page": 1,
          "bbox": [0.62, 0.44, 0.68, 0.47],
          "excerpt": "Mechanical Keyboard USB-C | 120"
        },
        {
          "document_id": "doc-grn-303",
          "page": 1,
          "bbox": [0.55, 0.51, 0.60, 0.54],
          "excerpt": "Delivered: 100 Units"
        }
      ]
    }
  ],
  "created_at": "2026-10-12T08:31:00Z",
  "updated_at": "2026-10-12T08:31:15Z"
}
```

---

### 2.3 Human Review & Exception Handling

#### `POST /api/v1/cases/{id}/reviews`
Records an auditor's human review decision.

* **Request Body:**
```json
{
  "decision": "APPROVED_WITH_EXCEPTION",
  "notes": "Spoke with warehouse manager. 20 additional keyboards accepted under separate emergency delivery memo #41.",
  "corrections": {
    "goods_receipt.received_quantity": "120"
  }
}
```
* **Response `201 Created`:**
```json
{
  "id": "rev-event-881",
  "case_id": "case-9901",
  "reviewer_id": "usr-reviewer-01",
  "decision": "APPROVED_WITH_EXCEPTION",
  "notes": "Spoke with warehouse manager. 20 additional keyboards accepted under separate emergency delivery memo #41.",
  "created_at": "2026-10-12T08:35:00Z"
}
```

---

### 2.4 Background Job Status

#### `GET /api/v1/jobs/{id}`
Inspects the asynchronous processing status of an OCR extraction or verification job.

* **Response `200 OK`:**
```json
{
  "id": "job-ver-5510",
  "case_id": "case-9901",
  "status": "SUCCEEDED",
  "duration_ms": 342,
  "created_at": "2026-10-12T08:31:14Z",
  "completed_at": "2026-10-12T08:31:15Z"
}
```
