"""Transaction-scoped operations; callers own the session lifecycle."""

from pathlib import Path
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from proofflow.models import (
    CaseDocument,
    Document,
    EvidenceRef,
    ExtractionRun,
    Job,
    ReviewEvent,
    VerificationCase,
    Workspace,
)
from proofflow.storage import store_upload

DOCUMENT_TYPES = ("INVOICE", "PURCHASE_ORDER", "GOODS_RECEIPT")


def ingest_document(
    session: Session,
    source: BinaryIO,
    filename: str,
    document_type: str,
    workspace_id: str = "demo",
    max_bytes: int = 25 * 1024 * 1024,
    root: Path | None = None,
) -> tuple[Document, Job]:
    if document_type not in DOCUMENT_TYPES:
        raise ValueError("Invalid document type")
    key, sha256, size, mime = store_upload(source, workspace_id, max_bytes, root)
    with session.begin():
        if session.get(Workspace, workspace_id) is None:
            session.add(Workspace(id=workspace_id, name=workspace_id))
            session.flush()
        document = session.scalar(
            select(Document).where(
                Document.workspace_id == workspace_id,
                Document.sha256 == sha256,
                Document.document_type == document_type,
            )
        )
        if document is None:
            document = Document(
                workspace_id=workspace_id,
                document_type=document_type,
                filename=Path(filename).name[:255],
                mime_type=mime,
                file_size_bytes=size,
                sha256=sha256,
                storage_key=key,
            )
            session.add(document)
            session.flush()
            job = Job(document_id=document.id)
            session.add(job)
        else:
            job = session.scalar(select(Job).where(Job.document_id == document.id))
        session.flush()
    return document, job


def create_case(
    session: Session,
    document_ids: dict[str, str],
    workspace_id: str = "demo",
    source_key: str | None = None,
) -> VerificationCase:
    if set(document_ids) != set(DOCUMENT_TYPES) or len(set(document_ids.values())) != 3:
        raise ValueError("A case requires three distinct document types")
    with session.begin():
        if source_key:
            existing = session.scalar(
                select(VerificationCase).where(
                    VerificationCase.workspace_id == workspace_id,
                    VerificationCase.source_key == source_key,
                )
            )
            if existing:
                return existing
        for document_type, document_id in document_ids.items():
            document = session.get(Document, document_id)
            if (
                document is None
                or document.workspace_id != workspace_id
                or document.document_type != document_type
            ):
                raise ValueError(f"Invalid {document_type} document")
        case = VerificationCase(workspace_id=workspace_id, source_key=source_key)
        session.add(case)
        session.flush()
        session.add_all(
            CaseDocument(
                case_id=case.id,
                document_id=document_id,
                workspace_id=workspace_id,
                document_type=document_type,
            )
            for document_type, document_id in document_ids.items()
        )
    return case


def append_extraction(
    session: Session,
    document_id: str,
    model_name: str,
    predictions: dict,
    evidence: list[dict] = (),
    prompt_version: str | None = None,
) -> ExtractionRun:
    with session.begin():
        if session.get(Document, document_id) is None:
            raise ValueError("Document does not exist")
        previous = session.scalars(
            select(ExtractionRun.version)
            .where(ExtractionRun.document_id == document_id)
            .order_by(ExtractionRun.version.desc())
            .limit(1)
        ).first()
        run = ExtractionRun(
            document_id=document_id,
            version=(previous or 0) + 1,
            model_name=model_name,
            prompt_version=prompt_version,
            predictions=predictions,
        )
        session.add(run)
        session.flush()
        session.add_all(
            EvidenceRef(extraction_run_id=run.id, **ref) for ref in evidence
        )
    return run


def append_review(
    session: Session, case_id: str, reviewer_id: str, decision: str, corrections: dict
) -> ReviewEvent:
    with session.begin():
        if session.get(VerificationCase, case_id) is None:
            raise ValueError("Case does not exist")
        event = ReviewEvent(
            case_id=case_id,
            reviewer_id=reviewer_id,
            decision=decision,
            corrections=corrections,
        )
        session.add(event)
    return event
