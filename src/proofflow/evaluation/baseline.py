"""E001 exact-match measurements on development documents and scan variants."""

import json
import math
import statistics
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from proofflow.domain.documents import DocumentType
from proofflow.intelligence.extractor import extract_document
from proofflow.intelligence.pdf_parser import OcrError, ParseError, parse_document

FIELDS = (
    "supplier_name",
    "invoice_number",
    "po_number",
    "issue_date",
    "currency",
    "subtotal",
    "tax_amount",
    "grand_total",
)
ITEM_FIELDS = ("sku", "description", "quantity", "unit_price", "line_total")


def _normalized(value):
    if value is None:
        return None
    return " ".join(str(value).casefold().replace(",", "").split())


def _p95(values: list[float]) -> float:
    return sorted(values)[math.ceil(0.95 * len(values)) - 1] if values else 0.0


def evaluate(
    manifest: Path, data_root: Path, scan_manifest: Path | None = None
) -> dict:
    """Read labels only here, in the offline evaluator; use development split only."""
    root = data_root.resolve()
    cases = [
        item
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if (item := json.loads(line))["split"] == "development"
    ]
    labels = {
        entry["document_id"]: entry
        for case in cases
        for entry in case["documents"].values()
    }
    samples = [
        (entry["document_id"], entry["file"], False) for entry in labels.values()
    ]
    scan_manifest = scan_manifest or root / "scan_variants.jsonl"
    if scan_manifest.is_file():
        samples += [
            (item["document_id"], item["file"], True)
            for line in scan_manifest.read_text(encoding="utf-8").splitlines()
            if (item := json.loads(line))["split"] == "development"
        ]
    exact = Counter()
    totals = Counter()
    errors = Counter()
    examples = []
    latencies = []
    parsed_count = ocr_count = evidence_count = predicted_count = item_count = (
        item_correct
    ) = 0
    for document_id, relative, is_scan in samples:
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"Dataset path escapes root: {relative}")
        started = perf_counter()
        try:
            parsed = parse_document(path)
            predicted = extract_document(
                parsed, document_id, DocumentType(labels[document_id]["document_type"])
            )
        except (ParseError, OcrError, OSError, ValueError) as error:
            errors["ocr" if isinstance(error, OcrError) else "parsing"] += 1
            examples.append(
                {"document_id": document_id, "scan": is_scan, "error": str(error)}
            )
            continue
        latencies.append((perf_counter() - started) * 1000)
        parsed_count += 1
        ocr_count += any(page.method == "ocr" for page in parsed.pages)
        expected = labels[document_id]
        for field in FIELDS:
            actual, truth = getattr(predicted, field), expected[field]
            if truth is not None:
                totals[field] += 1
                if _normalized(actual) == _normalized(truth):
                    exact[field] += 1
                else:
                    errors["field"] += 1
                    if len(examples) < 12:
                        examples.append(
                            {
                                "document_id": document_id,
                                "scan": is_scan,
                                "field": field,
                                "expected": truth,
                                "predicted": str(actual)
                                if actual is not None
                                else None,
                            }
                        )
            if actual is not None:
                predicted_count += 1
                evidence_count += field in predicted.evidence
        predicted_items = {item.sku: item for item in predicted.line_items}
        for truth in expected["line_items"]:
            item_count += 1
            actual = predicted_items.get(truth["sku"])
            if actual and all(
                _normalized(getattr(actual, field)) == _normalized(truth[field])
                for field in ITEM_FIELDS
            ):
                item_correct += 1
            else:
                errors["line_item"] += 1
                if len(examples) < 12:
                    examples.append(
                        {
                            "document_id": document_id,
                            "scan": is_scan,
                            "field": f"line_item:{truth['sku']}",
                            "expected": truth,
                            "predicted": (
                                actual.model_dump(mode="json", exclude={"evidence"})
                                if actual
                                else None
                            ),
                        }
                    )
        for index, item in enumerate(predicted.line_items):
            for field in ITEM_FIELDS:
                if getattr(item, field) is not None:
                    predicted_count += 1
                    evidence_count += (
                        f"line_items[{index}].{field}" in predicted.evidence
                    )
    return {
        "experiment": "E001",
        "model": "heuristic-v1",
        "split": "development",
        "created_at": datetime.now(UTC).isoformat(),
        "documents": len(samples),
        "scans": sum(is_scan for _, _, is_scan in samples),
        "parsing_success": parsed_count / len(samples) if samples else 0,
        "field_exact_match": {
            field: {
                "correct": exact[field],
                "total": totals[field],
                "accuracy": exact[field] / totals[field] if totals[field] else None,
            }
            for field in FIELDS
        },
        "line_item_accuracy": item_correct / item_count if item_count else None,
        "line_items": {"correct": item_correct, "total": item_count},
        "ocr_fallback_rate": ocr_count / parsed_count if parsed_count else 0,
        "evidence_coverage": evidence_count / predicted_count if predicted_count else 0,
        "latency_ms": {
            "p50": round(statistics.median(latencies), 1) if latencies else 0,
            "p95": round(_p95(latencies), 1),
        },
        "errors": dict(errors),
        "failure_examples": examples[:12],
    }
