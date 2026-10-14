# ProofFlow Day 2 synthetic benchmark

**Version:** 0.1.0

**Seed:** 20261012
**License:** Project-owned synthetic data; no real customer documents.

## Intended use

This is an engineering smoke benchmark for document extraction and three-way
business verification. It has 30 linked purchase order, invoice, and goods
receipt bundles (90 one-page digital PDFs), plus six JPEG scan derivatives.
The scans remain in their source case's split and are not independent samples.

| Scenario | Cases | Expected status |
| --- | ---: | --- |
| Full match | 8 | VERIFIED |
| Valid partial delivery | 4 | VERIFIED |
| Quantity mismatch | 6 | NEEDS_REVIEW |
| Unit-price mismatch | 4 | NEEDS_REVIEW |
| Supplier mismatch | 3 | NEEDS_REVIEW |
| Incorrect invoice total | 3 | NEEDS_REVIEW |
| Missing required information | 2 | NEEDS_REVIEW |

Development has 18 cases; validation and held-out test each have 6. A case's
three documents are always in the same split. Layout families and supplier
names are disjoint between splits. All layouts still come from one renderer.
Keep the test split out of prompt examples and self-improvement loops.

The dataset is intentionally 60% exceptions, so its status distribution is
not representative of a real accounts-payable workload. Six held-out cases
support a smoke test, not a reliable production accuracy estimate. It does
not cover handwriting, Bangla-English forms, multi-page files, actual tax or
discount policies, cumulative partial deliveries, or real supplier variation.

## Rebuild and check

From the repository root:

```powershell
uv sync --extra dev
uv run python scripts/generate_dataset.py
uv run python scripts/create_scan_variants.py
uv run python scripts/validate_dataset.py
uv run pytest tests/test_dataset.py -q
```

`data/day2/cases.jsonl` has extraction truth for each original PDF and a
separate `expected_verification` decision. `split_manifest.json` fixes bundle
membership. `dataset_summary.json` records counts. `scan_variants.jsonl`
links degraded images to originals and marks their source bounding boxes
invalid after rotation. `experiment_template.json` prepares null model
metrics. Every original PDF and scan has a SHA-256 hash in its manifest.

## Evaluation plan

Extraction: compare present and missing fields separately; normalize money
with `Decimal` and currency; match line items by SKU or reviewed identity
before precision, recall, and F1. Compare evidence page and bounding-box
overlap, not just value text. Verification: evaluate status and finding codes
against the separate decision truth. Report finding precision and recall,
review rate, and false verification rate (bad cases marked `VERIFIED`).
No OCR or verification engine has been run against this benchmark yet, so
model metrics are unknown. The later experiment record should use null
metric values and `NOT_EVALUATED` until an actual run is made.
