# Day 2 annotation contract

Each line of `data/day2/cases.jsonl` is one complete bundle. Required keys:
`case_id`, `split`, `layout_family`, `scenario`, `documents`, and
`expected_verification`. The document map has exactly `purchase_order`,
`invoice`, and `goods_receipt`. Each document records its original PDF path,
SHA-256, document ID and type, normalized field values, line items, and
field-level `evidence`. Quantity and money values are decimal strings.

Extraction truth describes only what is visibly printed. A missing field is
JSON `null` and has no evidence entry; never infer it from arithmetic or a
related document. Each non-null field has one evidence record keyed by its
field path, for example `line_items[0].quantity`. It contains the exact
printed `text`, `document_id`, one-based `page`, `bbox`, and
`bbox_source: synthetic_renderer`. Bounding boxes are `[left, top, right,
bottom]` in normalized 0–1 page coordinates. Wrapped descriptions use one
box covering both lines. A scan's rotated pixels invalidate these original
coordinates until a person re-annotates them.

Verification truth is **separate**: `expected_verification.status`,
`finding_codes`, and `evidence_fields`. The latter points to relevant source
fields, such as `invoice.line_items[0].quantity`. A missing value has no
bounding box; the absence is checked against the PDF and represented by
`INSUFFICIENT_DATA`.

The policies are those in [verification-rules.md](verification-rules.md):
invoice quantity may be below ordered quantity when it is no higher than
received quantity; unit price must equal the PO; invoice arithmetic must
agree internally; supplier names must agree; required invoice identity and
total must be present. A quantity or price mismatch can coexist with correct
invoice arithmetic. The generator constructs scenario labels directly. The
validator recalculates findings from annotated values independently of the
application's future verification engine.

Before adding a human-authored example, inspect its visual source, enter only
visible values, attach evidence for every present field, calculate the
business finding independently, and review it with a second person. Keep all
three documents and any derivatives in one split. Never tune on held-out test.
