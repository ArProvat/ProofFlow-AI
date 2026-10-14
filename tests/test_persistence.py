"""Day 3 storage, API, transaction, and import checks."""

import hashlib
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from proofflow.api.main import app, get_session
from proofflow.cli import import_day2
from proofflow.db import Base
from proofflow.models import (
    CaseDocument,
    Document,
    EvidenceRef,
    ExtractionRun,
    Job,
    ReviewEvent,
    VerificationCase,
)
from proofflow.persistence import append_extraction, append_review, ingest_document

ROOT = Path(__file__).resolve().parents[1]
PDF_ROOT = ROOT / "data" / "day2" / "pdfs" / "development"
AUTH = {"Authorization": "Bearer change-me-to-a-long-random-secret"}


@pytest.fixture
def database(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setattr("proofflow.cli.make_session_factory", lambda: factory)

    def session_override():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    yield factory
    app.dependency_overrides.clear()
    engine.dispose()


def count(factory, model):
    with factory() as session:
        return session.scalar(select(func.count()).select_from(model))


def test_upload_case_content_and_idempotency(database):
    client = TestClient(app)
    ids = {}
    for suffix, document_type in (
        ("INV", "INVOICE"),
        ("PO", "PURCHASE_ORDER"),
        ("GRN", "GOODS_RECEIPT"),
    ):
        path = PDF_ROOT / f"CASE-001-{suffix}.pdf"
        payload = path.read_bytes()
        response = client.post(
            "/api/v1/documents",
            headers=AUTH,
            data={"document_type": document_type},
            files={"file": (path.name, payload, "application/pdf")},
        )
        assert response.status_code == 201
        ids[document_type] = response.json()["document_id"]
        job_id = response.json()["job_id"]
        assert (
            client.get(f"/api/v1/jobs/{job_id}", headers=AUTH).json()["status"]
            == "QUEUED"
        )
        metadata = client.get(f"/api/v1/documents/{ids[document_type]}", headers=AUTH)
        assert metadata.json()["sha256"] == hashlib.sha256(payload).hexdigest()
        content = client.get(
            f"/api/v1/documents/{ids[document_type]}/content", headers=AUTH
        )
        assert content.content == payload
        if suffix == "INV":
            repeated = client.post(
                "/api/v1/documents",
                headers=AUTH,
                data={"document_type": document_type},
                files={"file": (path.name, payload, "application/pdf")},
            )
            assert repeated.json()["document_id"] == ids[document_type]
            assert repeated.json()["job_id"] == job_id
    response = client.post(
        "/api/v1/cases",
        headers=AUTH,
        json={
            "invoice_document_id": ids["INVOICE"],
            "purchase_order_document_id": ids["PURCHASE_ORDER"],
            "goods_receipt_document_id": ids["GOODS_RECEIPT"],
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "DRAFT"
    case_id = response.json()["id"]
    assert client.get(f"/api/v1/cases/{case_id}", headers=AUTH).json()["id"] == case_id
    assert (
        count(database, Document),
        count(database, Job),
        count(database, CaseDocument),
    ) == (
        3,
        3,
        3,
    )


def test_rejects_bad_upload_and_invalid_case(database, monkeypatch):
    client = TestClient(app)
    assert client.get("/api/v1/documents/missing").status_code == 401
    assert (
        client.post(
            "/api/v1/documents",
            headers=AUTH,
            data={"document_type": "INVOICE"},
            files={"file": ("fake.pdf", b"arbitrary text", "application/pdf")},
        ).status_code
        == 422
    )
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "8")
    assert (
        client.post(
            "/api/v1/documents",
            headers=AUTH,
            data={"document_type": "INVOICE"},
            files={"file": ("large.pdf", b"%PDF-123456789", "application/pdf")},
        ).status_code
        == 413
    )
    assert (
        client.post(
            "/api/v1/cases",
            headers=AUTH,
            json={
                "invoice_document_id": "missing",
                "purchase_order_document_id": "missing2",
                "goods_receipt_document_id": "missing3",
            },
        ).status_code
        == 422
    )
    assert count(database, Document) == count(database, VerificationCase) == 0


def test_import_repeat_history_and_workspace_isolation(database):
    manifest = ROOT / "data" / "day2" / "cases.jsonl"
    data_root = ROOT / "data" / "day2"
    assert import_day2(manifest, data_root, "development", 1) == 1
    assert import_day2(manifest, data_root, "development", 1) == 1
    assert (
        count(database, Document),
        count(database, Job),
        count(database, VerificationCase),
        count(database, CaseDocument),
    ) == (3, 3, 1, 3)
    with database() as session:
        document_id = session.scalar(select(Document.id).limit(1))
        case_id = session.scalar(select(VerificationCase.id).limit(1))
    with database() as session:
        first = append_extraction(
            session,
            document_id,
            "OCR",
            {"invoice_number": "INV-1008"},
            [
                {
                    "field_path": "invoice_number",
                    "page": 1,
                    "bbox": [0, 0, 1, 1],
                    "excerpt": "INV-1008",
                }
            ],
        )
    with database() as session:
        second = append_extraction(
            session, document_id, "VLM", {"invoice_number": "INV-1003"}
        )
    with database() as session:
        append_review(
            session,
            case_id,
            "reviewer",
            "APPROVED_WITH_EXCEPTION",
            {"invoice_number": "INV-1003"},
        )
    assert (first.version, second.version) == (1, 2)
    assert (
        count(database, ExtractionRun),
        count(database, EvidenceRef),
        count(database, ReviewEvent),
    ) == (
        2,
        1,
        1,
    )
    client = TestClient(app)
    with database() as session:
        other, _ = ingest_document(
            session,
            io.BytesIO(b"%PDF-other"),
            "other.pdf",
            "INVOICE",
            "other",
        )
    assert client.get(f"/api/v1/documents/{other.id}", headers=AUTH).status_code == 404
