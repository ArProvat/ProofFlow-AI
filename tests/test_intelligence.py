"""Parsing and baseline extraction on real digital and degraded source files."""

import shutil
from pathlib import Path

import pymupdf
import pytest
from PIL import Image

from proofflow.domain.documents import DocumentType
from proofflow.evaluation.baseline import evaluate
from proofflow.intelligence.extractor import extract_document
from proofflow.intelligence.pdf_parser import ParseError, parse_document

ROOT = Path(__file__).resolve().parents[1]
PDFS = ROOT / "data/day2/pdfs/development"
SCAN = ROOT / "data/day2/scans/CASE-003-INV-scan.jpg"
LOCAL_TESSERACT = ROOT / ".local_storage/tesseract/tesseract.exe"


def test_digital_pdf_fields_wrapped_items_and_evidence():
    parsed = parse_document(PDFS / "CASE-002-INV.pdf")
    result = extract_document(parsed, "doc-1", DocumentType.INVOICE)
    assert parsed.pages[0].method == "native"
    assert result.supplier_name == "Atlas Office Supply Ltd"
    assert result.invoice_number == "INV-2026-002"
    assert result.line_items[2].description == "Ergonomic Standing Desk Converter"
    assert result.line_items[2].quantity == 11
    assert result.grand_total == 3544
    assert result.evidence["line_items[2].description"].excerpt.endswith(
        "Desk Converter"
    )
    assert all(
        0 <= coordinate <= 1
        for page in parsed.pages
        for word in page.words
        for coordinate in word.bbox
    )


def test_ocr_jpeg_png_and_scanned_pdf(tmp_path):
    if not (shutil.which("tesseract") or LOCAL_TESSERACT.is_file()):
        pytest.skip("Tesseract executable is unavailable")
    with Image.open(SCAN) as image:
        png = tmp_path / "scan.png"
        image.save(png)
    with pymupdf.open(SCAN) as image_doc:
        scanned_pdf = tmp_path / "scan.pdf"
        scanned_pdf.write_bytes(image_doc.convert_to_pdf())
    for path in (SCAN, png, scanned_pdf):
        parsed = parse_document(path)
        result = extract_document(parsed, "scan", DocumentType.INVOICE)
        assert parsed.pages[0].method == "ocr"
        assert result.invoice_number == "INV-2026-003"
        assert result.line_items[0].description == "Wireless Optical Mouse"
        assert result.evidence["line_items[0].quantity"].page == 1
        assert all(
            0 <= coordinate <= 1
            for word in parsed.pages[0].words
            for coordinate in word.bbox
        )


def test_rejects_invalid_and_over_limit_documents(tmp_path):
    fake = tmp_path / "fake.pdf"
    fake.write_bytes(b"not a PDF")
    with pytest.raises(ParseError, match="Unsupported"):
        parse_document(fake)
    with pymupdf.open() as pdf:
        pdf.new_page()
        pdf.new_page()
        two_pages = tmp_path / "two-pages.pdf"
        pdf.save(two_pages)
    with pytest.raises(ParseError, match="over-limit"):
        parse_document(two_pages, max_pages=1)


def test_evaluation_uses_development_files_and_records_failures():
    if not (shutil.which("tesseract") or LOCAL_TESSERACT.is_file()):
        pytest.skip("Tesseract executable is unavailable")
    report = evaluate(ROOT / "data/day2/cases.jsonl", ROOT / "data/day2")
    assert report["split"] == "development"
    assert report["documents"] == 57
    assert report["scans"] == 3
    assert report["parsing_success"] == 1
    assert report["line_items"]["total"] > 0
    assert report["failure_examples"]
