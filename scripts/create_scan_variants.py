"""Make six controlled JPEG derivatives; these are not independent cases."""

import hashlib
import json
from pathlib import Path

import pymupdf
from PIL import Image, ImageEnhance, ImageFilter

DATA = Path(__file__).resolve().parents[1] / "data" / "day2"
SAMPLES = [
    (3, "invoice"),
    (8, "purchase_order"),
    (17, "goods_receipt"),
    (21, "invoice"),
    (26, "invoice"),
    (29, "goods_receipt"),
]


def generate():
    cases = {
        int(c["case_id"][-3:]): c
        for c in (
            json.loads(line)
            for line in (DATA / "cases.jsonl").read_text(encoding="utf-8").splitlines()
        )
    }
    output = DATA / "scans"
    output.mkdir(parents=True, exist_ok=True)
    manifest = []
    for number, kind in SAMPLES:
        document = cases[number]["documents"][kind]
        source = DATA / document["file"]
        pdf = pymupdf.open(source)
        pix = pdf[0].get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        pdf.close()
        angle = 1.2 if number % 2 else -1.4
        image = image.rotate(angle, fillcolor="white")
        image = ImageEnhance.Contrast(image).enhance(0.75)
        image = image.filter(ImageFilter.GaussianBlur(radius=0.55))
        path = output / f"{document['document_id']}-scan.jpg"
        image.save(path, "JPEG", quality=62, optimize=True)
        manifest.append(
            {
                "case_id": cases[number]["case_id"],
                "document_id": document["document_id"],
                "split": cases[number]["split"],
                "source_file": document["file"],
                "file": path.relative_to(DATA).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "transform": {
                    "rotation_degrees": angle,
                    "contrast": 0.75,
                    "blur_radius": 0.55,
                    "jpeg_quality": 62,
                },
                "original_evidence_bboxes_valid": False,
            }
        )
    (DATA / "scan_variants.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in manifest),
        encoding="utf-8",
    )
    print("Generated 6 JPEG scan variants")


if __name__ == "__main__":
    generate()
