"""Durable, one-job-at-a-time OCR worker."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import perf_counter

from pydantic import ValidationError
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import sessionmaker

from proofflow.db import make_session_factory
from proofflow.domain.documents import DocumentType
from proofflow.intelligence.extractor import extract_document
from proofflow.intelligence.pdf_parser import OcrError, ParseError, parse_document
from proofflow.models import Document, EvidenceRef, ExtractionRun, Job
from proofflow.storage import original_path

MAX_ATTEMPTS = 3
LEASE_SECONDS = 600


@dataclass(frozen=True)
class Claim:
    job_id: str
    document_id: str
    attempt: int


def claim_job(factory: sessionmaker) -> Claim | None:
    """Claim one queued or expired job in a short transaction."""
    now = datetime.now(UTC)
    with factory() as session, session.begin():
        expired = and_(Job.status == "RUNNING", Job.lease_until < now)
        exhausted = (
            session.execute(
                update(Job)
                .where(expired, Job.attempt_count >= MAX_ATTEMPTS)
                .values(status="FAILED", last_error="LEASE_EXPIRED", lease_until=None)
                .returning(Job.document_id)
            )
            .scalars()
            .all()
        )
        if exhausted:
            session.execute(
                update(Document)
                .where(Document.id.in_(exhausted))
                .values(status="FAILED")
            )
        statement = (
            select(Job)
            .where(
                Job.kind == "EXTRACTION",
                Job.attempt_count < MAX_ATTEMPTS,
                or_(Job.status == "QUEUED", expired),
            )
            .order_by(Job.created_at, Job.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        job = session.scalar(statement)
        if job is None:
            return None
        job.status = "RUNNING"
        job.attempt_count += 1
        job.lease_until = now + timedelta(seconds=LEASE_SECONDS)
        session.get(Document, job.document_id).status = "PROCESSING"
        return Claim(job.id, job.document_id, job.attempt_count)


def _current_job(session, claim: Claim) -> Job:
    job = session.scalar(select(Job).where(Job.id == claim.job_id).with_for_update())
    if job is None or job.status != "RUNNING" or job.attempt_count != claim.attempt:
        raise RuntimeError("Job lease was claimed by another worker")
    return job


def _record_failure(
    factory: sessionmaker, claim: Claim, category: str, error: Exception
):
    with factory() as session, session.begin():
        try:
            job = _current_job(session, claim)
        except RuntimeError:
            return "LEASE_LOST"
        job.status = "QUEUED" if claim.attempt < MAX_ATTEMPTS else "FAILED"
        job.last_error = f"{category}: {error}"[:500]
        job.lease_until = None
        session.get(Document, claim.document_id).status = (
            "UPLOADED" if job.status == "QUEUED" else "FAILED"
        )
        return job.status


def process_once(factory: sessionmaker | None = None) -> dict | None:
    factory = factory or make_session_factory()
    claim = claim_job(factory)
    if claim is None:
        return None
    started = perf_counter()
    try:
        with factory() as session:
            document = session.get(Document, claim.document_id)
            path = original_path(document.storage_key)
            expected_hash = document.sha256
            document_type = DocumentType(document.document_type)
        with path.open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != expected_hash:
                raise ParseError("Original document checksum mismatch")
        parsed = parse_document(path)
        prediction = extract_document(parsed, claim.document_id, document_type)
        with factory() as session, session.begin():
            job = _current_job(session, claim)
            document = session.scalar(
                select(Document)
                .where(Document.id == claim.document_id)
                .with_for_update()
            )
            version = session.scalar(
                select(func.max(ExtractionRun.version)).where(
                    ExtractionRun.document_id == claim.document_id
                )
            )
            run = ExtractionRun(
                document_id=claim.document_id,
                version=(version or 0) + 1,
                model_name="heuristic-v1",
                prompt_version=None,
                predictions=prediction.model_dump(
                    mode="json",
                    exclude={"evidence": True, "line_items": {"__all__": {"evidence"}}},
                ),
            )
            session.add(run)
            session.flush()
            session.add_all(
                EvidenceRef(
                    extraction_run_id=run.id,
                    field_path=field,
                    page=source.page,
                    bbox=list(source.bbox) if source.bbox else None,
                    excerpt=source.excerpt,
                )
                for field, source in prediction.evidence.items()
            )
            job.status = "SUCCEEDED"
            job.last_error = None
            job.lease_until = None
            document.status = "EXTRACTED"
            run_id = run.id
        return {
            "job_id": claim.job_id,
            "status": "SUCCEEDED",
            "extraction_run_id": run_id,
            "version": (version or 0) + 1,
            "ocr_pages": sum(page.method == "ocr" for page in parsed.pages),
            "latency_ms": round((perf_counter() - started) * 1000),
        }
    except (OcrError, ParseError, ValidationError, OSError, ValueError) as error:
        failure = error
        category = (
            "OCR_ERROR"
            if isinstance(error, OcrError)
            else "PARSE_ERROR"
            if isinstance(error, (ParseError, OSError))
            else "EXTRACTION_ERROR"
        )
    except Exception as error:
        failure = error
        category = "PROCESSING_ERROR"
    status = _record_failure(factory, claim, category, failure)
    return {"job_id": claim.job_id, "status": status, "error": f"{category}: {failure}"}
