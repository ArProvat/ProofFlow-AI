"""Queued processing preserves history and records bounded failures."""

import io
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from proofflow.db import Base
from proofflow.models import Document, EvidenceRef, ExtractionRun, Job
from proofflow.persistence import ingest_document
from proofflow.worker import claim_job, process_once

ROOT = Path(__file__).resolve().parents[1]
INVOICE = ROOT / "data/day2/pdfs/development/CASE-001-INV.pdf"


@pytest.fixture
def queue(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'worker.sqlite'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    yield factory
    engine.dispose()


def test_success_reprocessing_and_lease_recovery(queue):
    with INVOICE.open("rb") as source, queue() as session:
        document, job = ingest_document(session, source, INVOICE.name, "INVOICE")
    first = process_once(queue)
    assert first["status"] == "SUCCEEDED"
    assert first["version"] == 1
    with queue() as session:
        assert session.get(Document, document.id).status == "EXTRACTED"
        assert session.get(Job, job.id).status == "SUCCEEDED"
        assert session.scalar(select(func.count()).select_from(EvidenceRef)) > 0
        with session.begin_nested():
            retry = Job(document_id=document.id, status="RUNNING", attempt_count=1)
            retry.lease_until = datetime.now(UTC) - timedelta(minutes=1)
            session.add(retry)
        session.commit()
        retry_id = retry.id
    claim = claim_job(queue)
    assert claim.job_id == retry_id and claim.attempt == 2
    # Simulate a crashed second attempt; the next worker creates a new run.
    with queue() as session, session.begin():
        session.get(Job, retry_id).lease_until = datetime.now(UTC) - timedelta(
            seconds=1
        )
    second = process_once(queue)
    assert second["status"] == "SUCCEEDED"
    assert second["version"] == 2
    with queue() as session:
        runs = session.scalars(
            select(ExtractionRun).where(ExtractionRun.document_id == document.id)
        ).all()
        assert sorted(run.version for run in runs) == [1, 2]


def test_parse_failure_retries_then_fails(queue):
    with queue() as session:
        document, job = ingest_document(
            session, io.BytesIO(b"%PDF-broken"), "broken.pdf", "INVOICE"
        )
    for expected in ("QUEUED", "QUEUED", "FAILED"):
        assert process_once(queue)["status"] == expected
    with queue() as session:
        stored = session.get(Job, job.id)
        assert stored.attempt_count == 3
        assert stored.last_error.startswith("PARSE_ERROR:")
        assert session.get(Document, document.id).status == "FAILED"
        assert session.scalar(select(func.count()).select_from(ExtractionRun)) == 0
