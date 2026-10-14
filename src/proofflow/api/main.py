import hmac
import os
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from proofflow.db import make_session_factory
from proofflow.models import CaseDocument, Document, Job, VerificationCase
from proofflow.persistence import create_case, ingest_document
from proofflow.storage import InvalidUpload, UploadTooLarge, original_path

app = FastAPI(
    title="ProofFlow AI",
    version="0.1.0",
    description="Verifiable document intelligence API",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def authorized(authorization: Annotated[str | None, Header()] = None) -> str:
    token = os.getenv("API_KEY")
    if (
        not token
        or not authorization
        or not hmac.compare_digest(authorization, f"Bearer {token}")
    ):
        raise HTTPException(401, "Unauthorized")
    return "demo"


@lru_cache
def session_factory():
    return make_session_factory()


def get_session():
    with session_factory()() as session:
        yield session


WorkspaceId = Annotated[str, Depends(authorized)]
DbSession = Annotated[Session, Depends(get_session)]


def document_view(document: Document) -> dict:
    return {
        "id": document.id,
        "workspace_id": document.workspace_id,
        "document_type": document.document_type,
        "filename": document.filename,
        "mime_type": document.mime_type,
        "file_size_bytes": document.file_size_bytes,
        "sha256": document.sha256,
        "status": document.status,
        "created_at": document.created_at,
    }


@app.post("/api/v1/documents", status_code=201)
def upload_document(
    workspace_id: WorkspaceId,
    session: DbSession,
    file: Annotated[UploadFile, File()],
    document_type: Annotated[str, Form()],
):
    try:
        document, job = ingest_document(
            session,
            file.file,
            file.filename or "upload",
            document_type,
            workspace_id,
            int(os.getenv("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024))),
        )
    except UploadTooLarge as error:
        raise HTTPException(413, str(error)) from error
    except (InvalidUpload, ValueError) as error:
        raise HTTPException(422, str(error)) from error
    return {
        "document_id": document.id,
        "job_id": job.id,
        "document_status": document.status,
        "job_status": job.status,
    }


@app.get("/api/v1/documents/{document_id}")
def get_document(document_id: str, workspace_id: WorkspaceId, session: DbSession):
    document = session.get(Document, document_id)
    if document is None or document.workspace_id != workspace_id:
        raise HTTPException(404, "Document not found")
    return document_view(document)


@app.get("/api/v1/documents/{document_id}/content")
def get_document_content(
    document_id: str, workspace_id: WorkspaceId, session: DbSession
):
    document = session.get(Document, document_id)
    if document is None or document.workspace_id != workspace_id:
        raise HTTPException(404, "Document not found")
    path = original_path(document.storage_key)
    if not path.is_file():
        raise HTTPException(404, "Original file missing")
    return FileResponse(path, media_type=document.mime_type, filename=document.filename)


@app.get("/api/v1/jobs/{job_id}")
def get_job(job_id: str, workspace_id: WorkspaceId, session: DbSession):
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    document = session.get(Document, job.document_id)
    if document.workspace_id != workspace_id:
        raise HTTPException(404, "Job not found")
    return {
        "id": job.id,
        "document_id": job.document_id,
        "kind": job.kind,
        "status": job.status,
        "attempt_count": job.attempt_count,
    }


class CaseCreate(BaseModel):
    invoice_document_id: str
    purchase_order_document_id: str
    goods_receipt_document_id: str


def case_view(case: VerificationCase, session: Session) -> dict:
    links = session.scalars(
        select(CaseDocument).where(CaseDocument.case_id == case.id)
    ).all()
    ids = {link.document_type: link.document_id for link in links}
    return {
        "id": case.id,
        "workspace_id": case.workspace_id,
        "status": case.status,
        "invoice_document_id": ids["INVOICE"],
        "purchase_order_document_id": ids["PURCHASE_ORDER"],
        "goods_receipt_document_id": ids["GOODS_RECEIPT"],
        "created_at": case.created_at,
    }


@app.post("/api/v1/cases", status_code=201)
def post_case(body: CaseCreate, workspace_id: WorkspaceId, session: DbSession):
    try:
        case = create_case(
            session,
            {
                "INVOICE": body.invoice_document_id,
                "PURCHASE_ORDER": body.purchase_order_document_id,
                "GOODS_RECEIPT": body.goods_receipt_document_id,
            },
            workspace_id,
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return case_view(case, session)


@app.get("/api/v1/cases/{case_id}")
def get_case(case_id: str, workspace_id: WorkspaceId, session: DbSession):
    case = session.get(VerificationCase, case_id)
    if case is None or case.workspace_id != workspace_id:
        raise HTTPException(404, "Case not found")
    return case_view(case, session)
