"""Persistence records. Original files and each prediction/review have distinct rows."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from proofflow.db import Base


def new_id() -> str:
    return str(uuid4())


def now() -> datetime:
    return datetime.now(UTC)


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), unique=True)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "sha256", "document_type"),
        CheckConstraint("file_size_bytes > 0"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"))
    document_type: Mapped[str] = mapped_column(String(32))
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(32))
    file_size_bytes: Mapped[int]
    sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(24), default="UPLOADED")
    created_at: Mapped[datetime] = mapped_column(default=now)


class VerificationCase(Base):
    __tablename__ = "verification_cases"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "source_key"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"))
    source_key: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(24), default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(default=now)


class CaseDocument(Base):
    __tablename__ = "case_documents"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "case_id"],
            ["verification_cases.workspace_id", "verification_cases.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "document_id"], ["documents.workspace_id", "documents.id"]
        ),
        UniqueConstraint("case_id", "document_type"),
    )
    case_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36))
    document_type: Mapped[str] = mapped_column(String(32))


class ExtractionRun(Base):
    __tablename__ = "extraction_runs"
    __table_args__ = (UniqueConstraint("document_id", "version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    version: Mapped[int]
    model_name: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(100))
    predictions: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=now)


class EvidenceRef(Base):
    __tablename__ = "evidence_refs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    extraction_run_id: Mapped[str] = mapped_column(ForeignKey("extraction_runs.id"))
    field_path: Mapped[str] = mapped_column(String(200))
    page: Mapped[int]
    bbox: Mapped[list | None] = mapped_column(JSON)
    excerpt: Mapped[str | None]


class VerificationFinding(Base):
    __tablename__ = "verification_findings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("verification_cases.id"))
    rule_id: Mapped[str] = mapped_column(String(16))
    outcome: Mapped[str] = mapped_column(String(50))
    details: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=now)


class ReviewEvent(Base):
    __tablename__ = "review_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("verification_cases.id"))
    reviewer_id: Mapped[str] = mapped_column(String(100))
    decision: Mapped[str] = mapped_column(String(40))
    corrections: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=now)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    kind: Mapped[str] = mapped_column(String(32), default="EXTRACTION")
    status: Mapped[str] = mapped_column(String(24), default="QUEUED")
    attempt_count: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str | None]
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(default=now)
