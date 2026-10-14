"""Generate the versioned Day 2 three-way matching benchmark."""

import hashlib
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path
from random import Random

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "day2"
SEED = 20261012
VERSION = "0.1.0"
KINDS = {"purchase_order": "PO", "invoice": "INV", "goods_receipt": "GRN"}
PRODUCTS = [
    ("KB-01", "Mechanical Keyboard USB-C", "20.00"),
    ("MN-02", "Adjustable Monitor Arm", "79.50"),
    ("HS-03", "Noise Cancelling Headset", "65.00"),
    ("DK-04", "USB-C Docking Station", "115.25"),
    ("MS-05", "Wireless Optical Mouse", "18.75"),
    ("ST-06", "Ergonomic Standing Desk Converter", "149.00"),
]
SPLITS = {"development": 18, "validation": 6, "test": 6}
LAYOUTS = {
    "development": ["classic", "boxed", "compact", "wide"],
    "validation": ["sidebar", "stacked"],
    "test": ["banner", "minimal"],
}
SUPPLIERS = {
    "development": ["Atlas Office Supply Ltd", "Cedar Business Goods Ltd"],
    "validation": ["Harbor Workspace Ltd", "Summit Trade Ltd"],
    "test": ["Orchid Equipment Ltd", "Vertex Office Goods Ltd"],
}
SCENARIOS_BY_SPLIT = {
    "development": [
        "full_match",
        "partial_delivery",
        "quantity_mismatch",
        "price_mismatch",
        "supplier_mismatch",
        "total_mismatch",
        "missing_information",
        "full_match",
        "partial_delivery",
        "quantity_mismatch",
        "price_mismatch",
        "supplier_mismatch",
        "full_match",
        "quantity_mismatch",
        "full_match",
        "quantity_mismatch",
        "full_match",
        "full_match",
    ],
    "validation": [
        "full_match",
        "partial_delivery",
        "quantity_mismatch",
        "price_mismatch",
        "total_mismatch",
        "missing_information",
    ],
    "test": [
        "full_match",
        "partial_delivery",
        "quantity_mismatch",
        "price_mismatch",
        "supplier_mismatch",
        "total_mismatch",
    ],
}
SCENARIOS = [scenario for rows in SCENARIOS_BY_SPLIT.values() for scenario in rows]
FINDINGS = {
    "quantity_mismatch": "QUANTITY_MISMATCH",
    "price_mismatch": "PRICE_MISMATCH",
    "supplier_mismatch": "SUPPLIER_MISMATCH",
    "total_mismatch": "TOTAL_MISMATCH",
    "missing_information": "INSUFFICIENT_DATA",
}


def money(value):
    return str(Decimal(value).quantize(Decimal("0.01")))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scenario_order():
    """Keep bundle allocation fixed across regenerations."""
    return SCENARIOS


def make_case(number, scenario, split, rng):
    case_id = f"CASE-{number:03d}"
    supplier = SUPPLIERS[split][number % 2]
    layout = LAYOUTS[split][number % len(LAYOUTS[split])]
    count = 1 + number % 3
    selected = rng.sample(PRODUCTS, count)
    ordered = [rng.randint(15, 90) for _ in selected]
    received = [
        q - rng.randint(2, 10) if scenario == "partial_delivery" else q for q in ordered
    ]
    invoiced = received.copy()
    if scenario == "quantity_mismatch":
        invoiced[0] += rng.randint(2, 8)
    po_price = [Decimal(p[2]) for p in selected]
    invoice_price = po_price.copy()
    if scenario == "price_mismatch":
        invoice_price[0] += Decimal("3.25")

    po_number = f"PO-2026-{number:03d}"
    invoice_number = f"INV-2026-{number:03d}"
    date = f"2026-10-{1 + number % 28:02d}"

    def items(quantities, prices=None):
        return [
            {
                "sku": product[0],
                "description": product[1],
                "quantity": str(quantities[i]),
                "unit_price": money(prices[i]) if prices else None,
                "line_total": money(Decimal(quantities[i]) * prices[i])
                if prices
                else None,
            }
            for i, product in enumerate(selected)
        ]

    def document(kind, supplier_name, line_items, prices=None):
        subtotal = (
            money(sum((Decimal(item["line_total"]) for item in line_items), Decimal(0)))
            if prices
            else None
        )
        return {
            "document_id": f"{case_id}-{KINDS[kind]}",
            "document_type": kind.upper(),
            "supplier_name": supplier_name,
            "invoice_number": invoice_number if kind == "invoice" else None,
            "po_number": po_number,
            "issue_date": date,
            "currency": "USD" if prices else None,
            "line_items": line_items,
            "subtotal": subtotal,
            "tax_amount": "0.00" if prices else None,
            "grand_total": subtotal,
            "evidence": {},
        }

    po = document("purchase_order", supplier, items(ordered, po_price), po_price)
    grn = document("goods_receipt", supplier, items(received))
    invoice_supplier = (
        "Unrelated Vendor Corp" if scenario == "supplier_mismatch" else supplier
    )
    invoice = document(
        "invoice", invoice_supplier, items(invoiced, invoice_price), invoice_price
    )
    if scenario == "total_mismatch":
        invoice["grand_total"] = money(
            Decimal(invoice["grand_total"]) + Decimal("7.00")
        )
    if scenario == "missing_information":
        invoice["invoice_number" if number % 2 else "grand_total"] = None
    documents = {"purchase_order": po, "invoice": invoice, "goods_receipt": grn}
    code = FINDINGS.get(scenario)
    evidence_fields = {
        "quantity_mismatch": [
            "invoice.line_items[0].quantity",
            "goods_receipt.line_items[0].quantity",
        ],
        "price_mismatch": [
            "invoice.line_items[0].unit_price",
            "purchase_order.line_items[0].unit_price",
        ],
        "supplier_mismatch": ["invoice.supplier_name", "purchase_order.supplier_name"],
        "total_mismatch": ["invoice.grand_total", "invoice.subtotal"],
        "missing_information": [],
    }
    return {
        "case_id": case_id,
        "split": split,
        "layout_family": layout,
        "scenario": scenario,
        "documents": documents,
        "expected_verification": {
            "status": "NEEDS_REVIEW" if code else "VERIFIED",
            "finding_codes": [code] if code else [],
            "evidence_fields": evidence_fields.get(scenario, []),
        },
    }


def render_document(path, document, layout):
    """Render visible field values and record their exact source regions."""
    width, height = A4
    c = canvas.Canvas(str(path), pagesize=A4, pageCompression=1, invariant=1)
    c.setTitle(document["document_id"])
    c.setAuthor("ProofFlow synthetic dataset")
    accent = {
        "classic": (0.08, 0.22, 0.38),
        "boxed": (0.16, 0.35, 0.37),
        "compact": (0.38, 0.22, 0.14),
        "wide": (0.24, 0.25, 0.42),
        "sidebar": (0.17, 0.32, 0.23),
        "stacked": (0.35, 0.19, 0.31),
        "banner": (0.1, 0.32, 0.47),
        "minimal": (0.22, 0.22, 0.22),
    }[layout]
    c.setFillColorRGB(*accent)
    if layout in {"banner", "boxed", "sidebar"}:
        c.rect(0, height - 90, width, 90, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 18)
    title = document["document_type"].replace("_", " ")
    c.drawString(44, height - 55, title)
    c.setFillColorRGB(0.08, 0.08, 0.08)
    evidence = document["evidence"]

    def value_at(key, value, x, y, size=10, font="Helvetica"):
        if value is None:
            return
        raw = str(value)
        c.setFont(font, size)
        c.drawString(x, y, raw)
        box = [
            round(x / width, 4),
            round((height - y - size) / height, 4),
            round((x + stringWidth(raw, font, size)) / width, 4),
            round((height - y + size * 0.35) / height, 4),
        ]
        evidence[key] = {
            "document_id": document["document_id"],
            "page": 1,
            "bbox": box,
            "text": raw,
            "bbox_source": "synthetic_renderer",
        }

    headers = [
        ("supplier_name", "Supplier"),
        ("po_number", "PO No"),
        ("invoice_number", "Invoice No"),
        ("issue_date", "Date"),
        ("currency", "Currency"),
    ]
    if layout in {"compact", "stacked", "minimal"}:
        headers = list(reversed(headers))
    header_y = height - 125
    for key, label in headers:
        if document[key] is None and key != "invoice_number":
            continue
        if key == "invoice_number" and document["document_type"] != "INVOICE":
            continue
        c.setFont("Helvetica-Bold", 9)
        c.drawString(44, header_y, f"{label}:")
        value_at(key, document[key], 125 if layout != "wide" else 180, header_y)
        header_y -= 23 if layout not in {"compact", "minimal"} else 19

    table_top = min(header_y - 36, height - 260)
    c.setStrokeColorRGB(*accent)
    c.line(44, table_top + 10, width - 44, table_top + 10)
    c.setFont("Helvetica-Bold", 9)
    columns = [
        (44, "SKU"),
        (112, "Description"),
        (365, "Qty"),
        (425, "Unit price"),
        (505, "Amount"),
    ]
    if document["document_type"] == "GOODS_RECEIPT":
        columns = columns[:3]
    for x, label in columns:
        c.drawString(x, table_top - 4, label)
    c.line(44, table_top - 12, width - 44, table_top - 12)

    row_y = table_top - 35
    for i, item in enumerate(document["line_items"]):
        prefix = f"line_items[{i}]"
        value_at(f"{prefix}.sku", item["sku"], 44, row_y, 9)
        words = item["description"].split()
        if len(item["description"]) > 27:
            split_at = len(words) // 2
            lines = [" ".join(words[:split_at]), " ".join(words[split_at:])]
        else:
            lines = [item["description"]]
        value_at(f"{prefix}.description", lines[0], 112, row_y, 9)
        if len(lines) > 1:
            c.setFont("Helvetica", 9)
            c.drawString(112, row_y - 12, lines[1])
            first = evidence[f"{prefix}.description"]["bbox"]
            first[2] = round(
                (112 + max(stringWidth(line, "Helvetica", 9) for line in lines))
                / width,
                4,
            )
            first[3] = round((height - (row_y - 12) + 9 * 0.35) / height, 4)
            evidence[f"{prefix}.description"]["text"] = item["description"]
        value_at(f"{prefix}.quantity", item["quantity"], 365, row_y, 9)
        if item["unit_price"] is not None:
            value_at(f"{prefix}.unit_price", item["unit_price"], 425, row_y, 9)
            value_at(f"{prefix}.line_total", item["line_total"], 505, row_y, 9)
        row_y -= 42 if len(lines) > 1 else 30

    if document["subtotal"] is not None:
        total_y = row_y - (95 if layout in {"boxed", "sidebar", "banner"} else 38)
        for key, label in [
            ("subtotal", "Subtotal"),
            ("tax_amount", "Tax"),
            ("grand_total", "Total"),
        ]:
            c.setFont("Helvetica-Bold", 10)
            c.drawString(395, total_y, f"{label}:")
            value_at(key, document[key], 485, total_y, 10)
            total_y -= 25
    c.setFont("Helvetica", 8)
    c.drawString(44, 40, f"Synthetic training document  |  {document['document_id']}")
    c.save()


def generate():
    rng = Random(SEED)
    cases = []
    for number, scenario in enumerate(scenario_order(), 1):
        split = (
            "development" if number <= 18 else "validation" if number <= 24 else "test"
        )
        case = make_case(number, scenario, split, rng)
        for document in case["documents"].values():
            path = DATA / "pdfs" / split / f"{document['document_id']}.pdf"
            path.parent.mkdir(parents=True, exist_ok=True)
            render_document(path, document, case["layout_family"])
            document["file"] = path.relative_to(DATA).as_posix()
            document["sha256"] = sha256(path)
        cases.append(case)

    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "cases.jsonl").write_text(
        "".join(json.dumps(case, sort_keys=True) + "\n" for case in cases),
        encoding="utf-8",
    )
    summary = {
        "dataset_version": VERSION,
        "seed": SEED,
        "case_count": len(cases),
        "original_document_count": len(cases) * 3,
        "split_counts": dict(Counter(case["split"] for case in cases)),
        "scenario_counts": dict(Counter(case["scenario"] for case in cases)),
        "status_counts": dict(
            Counter(case["expected_verification"]["status"] for case in cases)
        ),
    }
    (DATA / "dataset_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (DATA / "split_manifest.json").write_text(
        json.dumps(
            {
                split: [case["case_id"] for case in cases if case["split"] == split]
                for split in SPLITS
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return cases


if __name__ == "__main__":
    generate()
    print("Generated 30 cases and 90 PDFs in data/day2")
