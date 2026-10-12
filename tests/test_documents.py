from decimal import Decimal

import pytest
from pydantic import ValidationError

from proofflow.domain.documents import (
    DocumentType,
    EvidenceRef,
    ExtractedDocument,
    FindingOutcome,
    FindingSeverity,
    LineItem,
    RuleId,
    VerificationFinding,
)


def test_unknown_total_remains_unknown():
    document = ExtractedDocument(
        document_id="inv-001",
        document_type=DocumentType.INVOICE,
    )
    assert document.grand_total is None


def test_negative_quantity_is_rejected():
    with pytest.raises(ValidationError):
        LineItem(
            description="Keyboard",
            quantity="-5",
            unit_price="20.00",
        )


def test_decimal_calculation_is_exact():
    item = LineItem(
        description="Keyboard",
        quantity="3",
        unit_price="19.99",
    )
    assert item.quantity * item.unit_price == Decimal("59.97")


def test_evidence_requires_valid_page():
    with pytest.raises(ValidationError):
        EvidenceRef(
            document_id="inv-001",
            page=0,
        )


def test_negative_unit_price_is_rejected():
    with pytest.raises(ValidationError):
        LineItem(
            description="Keyboard",
            quantity="1",
            unit_price="-10.00",
        )


def test_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        EvidenceRef(
            document_id="inv-001",
            page=1,
            unauthorized_field="test",  # type: ignore[call-arg]
        )


def test_verification_finding_creation():
    finding = VerificationFinding(
        id="find-001",
        rule_id=RuleId.R003,
        outcome=FindingOutcome.QUANTITY_MISMATCH,
        severity=FindingSeverity.ERROR,
        message="Invoiced quantity (120) exceeds received quantity (100)",
        expected_value="100",
        actual_value="120",
    )
    assert finding.outcome == FindingOutcome.QUANTITY_MISMATCH
    assert finding.expected_value == "100"
