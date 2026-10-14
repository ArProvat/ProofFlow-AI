"""Independently check the generated Day 2 benchmark and its labels."""

import hashlib
import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

import pymupdf
from generate_dataset import DATA, FINDINGS, KINDS, SCENARIOS, SPLITS, VERSION
from PIL import Image


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def check(condition, message):
    if not condition:
        raise ValueError(message)


def amount(value):
    return Decimal(value)


def expected_from_fields(documents):
    """Recalculate findings from visible values, independently of labels."""
    po, inv, grn = (
        documents[k] for k in ("purchase_order", "invoice", "goods_receipt")
    )
    findings = []
    if inv["supplier_name"] != po["supplier_name"]:
        findings.append("SUPPLIER_MISMATCH")
    po_items = {item["sku"]: item for item in po["line_items"]}
    grn_items = {item["sku"]: item for item in grn["line_items"]}
    for item in inv["line_items"]:
        sku = item["sku"]
        check(sku in po_items and sku in grn_items, f"Unmatched SKU {sku}")
        if amount(item["quantity"]) > min(
            amount(po_items[sku]["quantity"]), amount(grn_items[sku]["quantity"])
        ):
            findings.append("QUANTITY_MISMATCH")
        if amount(item["unit_price"]) != amount(po_items[sku]["unit_price"]):
            findings.append("PRICE_MISMATCH")
        check(
            amount(item["line_total"])
            == amount(item["quantity"]) * amount(item["unit_price"]),
            f"Invalid invoice line arithmetic for {sku}",
        )
    subtotal = sum(
        (amount(item["line_total"]) for item in inv["line_items"]), Decimal(0)
    )
    check(amount(inv["subtotal"]) == subtotal, "Invalid invoice subtotal")
    if inv["grand_total"] is not None and amount(
        inv["grand_total"]
    ) != subtotal + amount(inv["tax_amount"]):
        findings.append("TOTAL_MISMATCH")
    if inv["invoice_number"] is None or inv["grand_total"] is None:
        findings.append("INSUFFICIENT_DATA")
    return sorted(set(findings))


def field_values(document):
    for key in (
        "supplier_name",
        "invoice_number",
        "po_number",
        "issue_date",
        "currency",
        "subtotal",
        "tax_amount",
        "grand_total",
    ):
        if document[key] is not None:
            yield key, str(document[key])
    for i, item in enumerate(document["line_items"]):
        for key, value in item.items():
            if value is not None:
                yield f"line_items[{i}].{key}", str(value)


def validate(data=DATA):
    cases = read_jsonl(data / "cases.jsonl")
    check(len(cases) == 30, "Expected 30 cases")
    check(len({c["case_id"] for c in cases}) == 30, "Duplicate case ID")
    check(
        Counter(c["scenario"] for c in cases) == Counter(SCENARIOS),
        "Scenario distribution changed",
    )
    check(Counter(c["split"] for c in cases) == SPLITS, "Split counts changed")
    check(
        Counter(c["expected_verification"]["status"] for c in cases)
        == {"VERIFIED": 12, "NEEDS_REVIEW": 18},
        "Status distribution changed",
    )
    families = defaultdict(set)
    suppliers = defaultdict(set)
    referenced = set()
    for case in cases:
        split = case["split"]
        families[split].add(case["layout_family"])
        suppliers[split].add(case["documents"]["purchase_order"]["supplier_name"])
        docs = case["documents"]
        check(
            set(docs) == {"purchase_order", "invoice", "goods_receipt"},
            "Document trio incomplete",
        )
        expected = case["expected_verification"]
        findings = expected_from_fields(docs)
        check(
            expected["finding_codes"] == findings, f"Wrong findings: {case['case_id']}"
        )
        check(
            expected["status"] == ("NEEDS_REVIEW" if findings else "VERIFIED"),
            f"Wrong status: {case['case_id']}",
        )
        check(
            findings
            == ([FINDINGS[case["scenario"]]] if case["scenario"] in FINDINGS else []),
            f"Scenario inconsistency: {case['case_id']}",
        )
        for ref in expected["evidence_fields"]:
            kind, field = ref.split(".", 1)
            check(field in docs[kind]["evidence"], f"Missing finding evidence: {ref}")
        for kind, document in docs.items():
            check(
                document["document_id"] == f"{case['case_id']}-{KINDS[kind]}",
                "Document ID mismatch",
            )
            check(document["document_type"] == kind.upper(), "Document type mismatch")
            relative = Path(document["file"])
            check(relative.parts[:2] == ("pdfs", split), "PDF outside its split")
            path = data / relative
            check(path.is_file(), f"Missing PDF: {path}")
            check(
                hashlib.sha256(path.read_bytes()).hexdigest() == document["sha256"],
                f"PDF hash mismatch: {path}",
            )
            referenced.add(path.resolve())
            with pymupdf.open(path) as pdf:
                check(len(pdf) == 1, f"Expected one PDF page: {path}")
                page = pdf[0]
                expected_fields = dict(field_values(document))
                check(
                    set(document["evidence"]) == set(expected_fields),
                    f"Missing or invented field evidence: {path}",
                )
                for field, value in expected_fields.items():
                    evidence = document["evidence"][field]
                    check(
                        evidence["document_id"] == document["document_id"]
                        and evidence["page"] == 1
                        and evidence["bbox_source"] == "synthetic_renderer"
                        and evidence["text"] == value,
                        f"Bad evidence metadata: {path} {field}",
                    )
                    x1, y1, x2, y2 = evidence["bbox"]
                    check(
                        0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1,
                        f"Invalid bbox: {path} {field}",
                    )
                    box = pymupdf.Rect(
                        x1 * page.rect.width,
                        y1 * page.rect.height,
                        x2 * page.rect.width,
                        y2 * page.rect.height,
                    )
                    found = " ".join(page.get_textbox(box).split())
                    check(
                        found == value,
                        f"Evidence does not match PDF: {path} {field}: {found!r}",
                    )
    for first in SPLITS:
        for second in SPLITS:
            if first != second:
                check(families[first].isdisjoint(families[second]), "Layout leakage")
                check(
                    suppliers[first].isdisjoint(suppliers[second]), "Supplier leakage"
                )
    check(
        set((data / "pdfs").rglob("*.pdf")) == referenced,
        "Extra or missing original PDFs",
    )
    manifest = json.loads((data / "split_manifest.json").read_text(encoding="utf-8"))
    check(
        manifest
        == {s: [c["case_id"] for c in cases if c["split"] == s] for s in SPLITS},
        "Split manifest inconsistent",
    )
    summary = json.loads((data / "dataset_summary.json").read_text(encoding="utf-8"))
    check(
        summary["dataset_version"] == VERSION
        and summary["original_document_count"] == 90,
        "Dataset summary inconsistent",
    )
    scans = read_jsonl(data / "scan_variants.jsonl")
    check(
        len(scans) == 6 and len({s["document_id"] for s in scans}) == 6,
        "Expected six distinct scan variants",
    )
    scan_paths = set()
    for scan in scans:
        check(scan["case_id"] in manifest[scan["split"]], "Scan split mismatch")
        check(
            not scan["original_evidence_bboxes_valid"],
            "Rotated evidence cannot be reused",
        )
        path = data / scan["file"]
        check(path.is_file(), f"Missing scan: {path}")
        check(
            hashlib.sha256(path.read_bytes()).hexdigest() == scan["sha256"],
            f"Scan hash mismatch: {path}",
        )
        with Image.open(path) as image:
            check(
                image.format == "JPEG" and min(image.size) >= 800,
                f"Invalid scan image: {path}",
            )
        scan_paths.add(path.resolve())
    check(set((data / "scans").rglob("*.jpg")) == scan_paths, "Extra or missing scans")
    return len(cases), len(referenced), len(scans)


if __name__ == "__main__":
    print("Validated cases, PDFs, scans:", *validate())
