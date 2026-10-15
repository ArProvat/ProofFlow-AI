# OCR and structured extraction baseline

The worker reads files already registered in PostgreSQL and stored under
`.local_storage`. It never reads dataset labels. It writes a versioned
`extraction_runs` row and separate `evidence_refs` rows, then marks the job
`SUCCEEDED` in the same transaction.

## Run locally

Install Tesseract with English language data and make `tesseract` available on
PATH, or set `TESSERACT_CMD` to its executable. PyMuPDF, Pillow, pytesseract,
and pytest-cov are installed by `uv sync --extra dev`.

```powershell
uv sync --extra dev
docker compose up -d db
uv run python -m alembic upgrade head
uv run python -m proofflow.cli process-once
uv run python -m proofflow.cli evaluate-baseline
uv run python -m pytest -q
uv run python -m ruff check .
```

`process-once` claims one pending job. PostgreSQL uses `FOR UPDATE SKIP LOCKED`
so workers cannot claim the same job together. A claim commits before parsing
or OCR begins. The ten minute lease lets another worker reclaim an abandoned
job; failed jobs retry at most three times. A result from a worker that lost
its lease cannot replace a newer result.

Digital PDF pages use PyMuPDF text and word coordinates. Pages with fewer than
eight native words and PNG/JPEG files use Tesseract OCR. Word boxes are
normalized to page dimensions. The extractor uses labeled header rows and
table column positions, including wrapped descriptions. The eight word rule
is a first baseline; sparse legitimate pages can be routed to OCR.

## E001 measurements

The checked-in [E001 report](../experiments/E001-baseline.json) evaluates only
the development split: 54 PDFs and three degraded image variants. It reports
parse success, exact matches for non-null labeled fields, whole line item
accuracy, OCR use, evidence coverage for emitted values, latency among parsed
documents, and failure examples. The labels and report stay outside the
application database. The five current line item misses all occur on degraded
scans.

The evaluation command reads source files and labels directly from
`data/day2`; it does not import labels into PostgreSQL. The held-out split is
excluded by an explicit `development` filter.
