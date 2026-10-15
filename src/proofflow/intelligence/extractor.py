"""Coordinate-aware heuristic extraction for the synthetic procurement PDFs."""

import re
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation

from proofflow.domain.documents import (
    DocumentType,
    EvidenceRef,
    ExtractedDocument,
    LineItem,
)
from proofflow.intelligence.pdf_parser import ParsedDocument, ParsedWord

FIELDS = {
    "supplier_name": re.compile(r"^Supplier\s*:\s*(.+)$", re.I),
    "po_number": re.compile(r"^PO\s*(?:No|Number)\s*:\s*(\S+)", re.I),
    "invoice_number": re.compile(r"^Invoice\s*(?:No|Number)\s*:\s*(\S+)", re.I),
    "issue_date": re.compile(r"^Date\s*:\s*(\d{4}-\d{2}-\d{2})", re.I),
    "currency": re.compile(r"^Currency\s*:\s*([A-Z]{3})", re.I),
    "subtotal": re.compile(r"^Subtotal\s*:\s*([\d,]+(?:\.\d+)?)", re.I),
    "tax_amount": re.compile(r"^Tax\s*:\s*([\d,]+(?:\.\d+)?)", re.I),
    "grand_total": re.compile(r"^(?:Grand\s+)?Total\s*:\s*([\d,]+(?:\.\d+)?)", re.I),
}
MONEY_FIELDS = {"subtotal", "tax_amount", "grand_total"}
SKU = re.compile(r"^[A-Z0-9]+(?:-[A-Z0-9]+)+$", re.I)


def _rows(words: Iterable[ParsedWord], tolerance: float) -> list[list[ParsedWord]]:
    rows: list[list[ParsedWord]] = []
    for word in sorted(words, key=lambda w: ((w.bbox[1] + w.bbox[3]) / 2, w.bbox[0])):
        center = (word.bbox[1] + word.bbox[3]) / 2
        if (
            rows
            and abs(
                center
                - sum((w.bbox[1] + w.bbox[3]) / 2 for w in rows[-1]) / len(rows[-1])
            )
            < tolerance
        ):
            rows[-1].append(word)
        else:
            rows.append([word])
    return [sorted(row, key=lambda word: word.bbox[0]) for row in rows]


def _evidence(document_id: str, words: list[ParsedWord]) -> EvidenceRef | None:
    if not words:
        return None
    return EvidenceRef(
        document_id=document_id,
        page=words[0].page,
        bbox=(
            min(word.bbox[0] for word in words),
            min(word.bbox[1] for word in words),
            max(word.bbox[2] for word in words),
            max(word.bbox[3] for word in words),
        ),
        excerpt=" ".join(word.text for word in words),
    )


def _value_words(row: list[ParsedWord], value: str) -> list[ParsedWord]:
    target = [part.strip(" :#") for part in value.split()]
    for index in range(len(row) - len(target) + 1):
        candidate = row[index : index + len(target)]
        if [word.text.strip(" :#") for word in candidate] == target:
            return candidate
    return []


def _decimal(value: str | None) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(value.replace(",", ""))
    except InvalidOperation:
        return None


def _column_words(
    row: list[ParsedWord], lower: float, upper: float
) -> list[ParsedWord]:
    return [word for word in row if lower <= (word.bbox[0] + word.bbox[2]) / 2 < upper]


def _table_columns(header: list[ParsedWord]) -> dict[str, tuple[float, float]]:
    labels = {}
    for word in header:
        label = word.text.lower().rstrip(":")
        key = {
            "sku": "sku",
            "description": "description",
            "qty": "quantity",
            "ty": "quantity",
            "quantity": "quantity",
            "unit": "unit_price",
            "amount": "line_total",
        }.get(label)
        if key:
            labels[key] = word.bbox[0]
    positions = sorted(labels.items(), key=lambda item: item[1])
    return {
        name: (
            0 if index == 0 else (positions[index - 1][1] + x) / 2,
            1 if index == len(positions) - 1 else (x + positions[index + 1][1]) / 2,
        )
        for index, (name, x) in enumerate(positions)
    }


def extract_document(
    parsed: ParsedDocument, document_id: str, document_type: DocumentType
) -> ExtractedDocument:
    values = {field: None for field in FIELDS}
    evidence = {}
    items = []
    for page in parsed.pages:
        rows = _rows(page.words, 0.022 if page.method == "ocr" else 0.009)
        columns = None
        for row in rows:
            line = " ".join(word.text for word in row)
            for field, pattern in FIELDS.items():
                match = pattern.match(line)
                if match and values[field] is None:
                    value = match.group(1).strip()
                    values[field] = (
                        _decimal(value)
                        if field in MONEY_FIELDS
                        else value.upper()
                        if field == "currency"
                        else value
                    )
                    source = _evidence(document_id, _value_words(row, value))
                    if source:
                        evidence[field] = source
            if re.search(r"\bSKU\b", line, re.I) and re.search(
                r"\b(?:Qty|ty)\b", line, re.I
            ):
                columns = _table_columns(row)
                continue
            if columns is None or line.startswith(
                ("Subtotal", "Tax", "Total", "Synthetic")
            ):
                continue
            cells = {
                name: _column_words(row, *bounds) for name, bounds in columns.items()
            }
            sku = " ".join(word.text for word in cells.get("sku", []))
            quantity = _decimal(
                "".join(word.text for word in cells.get("quantity", []))
            )
            description = " ".join(word.text for word in cells.get("description", []))
            if not SKU.fullmatch(sku) or not description or quantity is None:
                continue
            index = len(items)
            item_evidence = {}
            for name, words in cells.items():
                source = _evidence(document_id, words)
                if source:
                    evidence[f"line_items[{index}].{name}"] = source
                    item_evidence[name] = source
            items.append(
                LineItem(
                    sku=sku,
                    description=description,
                    quantity=quantity,
                    unit_price=_decimal(
                        "".join(word.text for word in cells.get("unit_price", []))
                    ),
                    line_total=_decimal(
                        "".join(word.text for word in cells.get("line_total", []))
                    ),
                    evidence=item_evidence.get("description"),
                )
            )
    return ExtractedDocument(
        document_id=document_id,
        document_type=document_type,
        line_items=items,
        evidence=evidence,
        raw_text="\n".join(page.text for page in parsed.pages),
        **values,
    )
