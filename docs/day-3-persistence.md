# Day 3: persistence and document ingestion

The Day 3 code is merged into the existing repository. The Day 2 source PDFs are
already in `data/day2`; no separate starter ZIP is required.

## Local PostgreSQL setup

```powershell
uv sync --extra dev
docker compose up -d db
$env:DATABASE_URL = "postgresql+psycopg://user:password@localhost:5433/proofflow"
$env:API_KEY = "replace-with-a-long-random-secret"
uv run python -m alembic upgrade head
uv run python -m alembic current
uv run python -m alembic check
uv run python -m proofflow.cli import-day2 --manifest data/day2/cases.jsonl --data-root data/day2 --split development --limit 1
uv run uvicorn proofflow.api.main:app --reload
```

Docker uses port 5433 on the host because 5432 may already be occupied. The
`db` service is the PostgreSQL service in this repository's Compose file.
`API_KEY` must be set before calling the API. The example `.env.example` lists
the variables but is not loaded automatically by the application.

## Data model

```mermaid
erDiagram
    WORKSPACES ||--o{ DOCUMENTS : owns
    WORKSPACES ||--o{ VERIFICATION_CASES : owns
    VERIFICATION_CASES ||--|{ CASE_DOCUMENTS : contains
    DOCUMENTS ||--o{ CASE_DOCUMENTS : linked_by
    DOCUMENTS ||--o{ JOBS : queues
    DOCUMENTS ||--o{ EXTRACTION_RUNS : processed_by
    EXTRACTION_RUNS ||--o{ EVIDENCE_REFS : cites
    VERIFICATION_CASES ||--o{ VERIFICATION_FINDINGS : has
    VERIFICATION_CASES ||--o{ REVIEW_EVENTS : records
```

- File bytes live under `.local_storage/<workspace>/<hash-prefix>/<sha256>`;
  `documents` stores metadata and the storage key. Filenames never form storage
  paths. The upload limit defaults to 25 MiB, and PDF, PNG, and JPEG signatures
  are checked before saving.
- A document and its queued extraction job commit in one database transaction.
  Re-uploading the same bytes and document type in one workspace returns the
  existing document and job. Jobs stay `QUEUED` on Day 3.
- Cases link exactly one document of each required type. The service checks
  document type and workspace before creating any case rows. Composite foreign
  keys also prevent links across workspaces.
- Extraction runs have a unique `(document_id, version)` pair. Evidence points
  to a run; human corrections are separate append-only review events.
- The importer reads only `case_id`, split, file path, document type, and hash
  from the Day 2 manifest. It validates paths and hashes and never inserts
  ground-truth fields or expected findings.

The file system and PostgreSQL do not share a transaction. If a database write
fails after storing a new blob, an orphan may remain. Do not delete it during
the failed request: another concurrent upload may reference the same hash.
An orphan reconciliation job can be added when uploads run concurrently.

## Verify the imported sample

The import is safe to repeat. In a fresh database, it should leave exactly
three documents, one `DRAFT` case, three case links, and three `QUEUED` jobs.

```powershell
docker compose exec db psql -U user -d proofflow -c "SELECT 'documents' AS item, count(*) FROM documents UNION ALL SELECT 'cases', count(*) FROM verification_cases UNION ALL SELECT 'links', count(*) FROM case_documents UNION ALL SELECT 'queued_jobs', count(*) FROM jobs WHERE status = 'QUEUED';"
uv run python -m pytest -q
uv run python -m ruff check .
```

The local verification on 2026-10-14 produced counts `3, 1, 3, 3`, with the
case in `DRAFT` and all jobs in `QUEUED`.
