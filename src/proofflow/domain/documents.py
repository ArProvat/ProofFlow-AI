from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class DocumentType(StrEnum):
    INVOICE = "INVOICE"
    PURCHASE_ORDER = "PURCHASE_ORDER"
    GOODS_RECEIPT = "GOODS_RECEIPT"


class DocumentStatus(StrEnum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    EXTRACTED = "EXTRACTED"
    FAILED = "FAILED"


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    page: int = Field(ge=1)
    # Normalized [x1, y1, x2, y2], 0..1.
    bbox: tuple[float, float, float, float] | None = None
    excerpt: str | None = None


class LineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: str | None = None
    description: str = Field(min_length=1)
    quantity: Decimal | None = Field(default=None, ge=0)
    unit_price: Decimal | None = Field(default=None, ge=0)
    line_total: Decimal | None = Field(default=None, ge=0)
    evidence: EvidenceRef | None = None


class ExtractedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    document_type: DocumentType
    supplier_name: str | None = None
    invoice_number: str | None = None
    po_number: str | None = None
    issue_date: date | None = None
    currency: str | None = None
    line_items: list[LineItem] = Field(default_factory=list)
    subtotal: Decimal | None = None
    tax_amount: Decimal | None = None
    grand_total: Decimal | None = None
    evidence: dict[str, EvidenceRef] = Field(default_factory=dict)
    confidence_scores: dict[str, float] = Field(default_factory=dict)
    raw_text: str | None = None


class Document(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    workspace_id: str
    filename: str
    mime_type: str
    file_size_bytes: int = Field(ge=0)
    page_count: int | None = Field(default=None, ge=1)
    status: DocumentStatus = DocumentStatus.UPLOADED
    storage_path: str
    uploaded_at: datetime
    extracted_data: ExtractedDocument | None = None


class VerificationStatus(StrEnum):
    DRAFT = "DRAFT"
    READY = "READY"
    VERIFYING = "VERIFYING"
    VERIFIED = "VERIFIED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    FAILED = "FAILED"


class RuleId(StrEnum):
    R001 = "R001"  # Supplier identities agree
    R002 = "R002"  # Items can be matched between documents
    R003 = "R003"  # Invoiced quantity does not exceed permitted received quantity
    R004 = "R004"  # Unit price agrees with the PO
    R005 = "R005"  # Line totals and invoice total satisfy arithmetic rules
    R006 = "R006"  # Invoice identity is not duplicated for that supplier
    R007 = "R007"  # Required fields and evidence are available
    R008 = "R008"  # Currencies match within the same reconciliation case


class FindingOutcome(StrEnum):
    SUPPLIER_MISMATCH = "SUPPLIER_MISMATCH"
    ITEM_NOT_MATCHED = "ITEM_NOT_MATCHED"
    QUANTITY_MISMATCH = "QUANTITY_MISMATCH"
    PRICE_MISMATCH = "PRICE_MISMATCH"
    TOTAL_MISMATCH = "TOTAL_MISMATCH"
    DUPLICATE_INVOICE = "DUPLICATE_INVOICE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"


class FindingSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class VerificationFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    rule_id: RuleId
    outcome: FindingOutcome
    severity: FindingSeverity
    message: str
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    expected_value: str | None = None
    actual_value: str | None = None


class VerificationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    workspace_id: str
    invoice_document_id: str
    purchase_order_document_id: str
    goods_receipt_document_id: str
    status: VerificationStatus = VerificationStatus.DRAFT
    findings: list[VerificationFinding] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ReviewDecision(StrEnum):
    PENDING = "PENDING"
    APPROVED_WITH_EXCEPTION = "APPROVED_WITH_EXCEPTION"
    REJECTED = "REJECTED"


class ReviewEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    case_id: str
    reviewer_id: str
    decision: ReviewDecision
    notes: str | None = None
    corrections: dict[str, str] = Field(default_factory=dict)
    created_at: datetime


class ExecutionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    document_id: str | None = None
    case_id: str | None = None
    model_provider: str
    model_version: str
    prompt_template_version: str | None = None
    duration_ms: int = Field(ge=0)
    tokens_used: int | None = None
    outcome: str
    created_at: datetime
