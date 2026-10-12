"""Checks that would fail if ground truth or source files drift."""

import copy
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_dataset  # noqa: E402
from validate_dataset import validate  # noqa: E402


def test_dataset_integrity():
    assert validate() == (30, 90, 6)


def test_rejects_incorrect_verification_label(tmp_path):
    source = generate_dataset.DATA
    shutil.copytree(source, tmp_path / "day2")
    data = tmp_path / "day2"
    path = data / "cases.jsonl"
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    bad = copy.deepcopy(cases)
    bad[2]["expected_verification"]["finding_codes"] = []
    path.write_text("".join(json.dumps(c) + "\n" for c in bad), encoding="utf-8")
    with pytest.raises(ValueError, match="Wrong findings"):
        validate(data)


def test_rejects_changed_pdf(tmp_path):
    shutil.copytree(generate_dataset.DATA, tmp_path / "day2")
    data = tmp_path / "day2"
    first = json.loads(
        (data / "cases.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    path = data / first["documents"]["invoice"]["file"]
    path.write_bytes(path.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="PDF hash mismatch"):
        validate(data)


def test_pdf_generation_is_deterministic(tmp_path, monkeypatch):
    monkeypatch.setattr(generate_dataset, "DATA", tmp_path / "generated")
    first = generate_dataset.generate()
    first_hashes = [
        doc["sha256"] for case in first for doc in case["documents"].values()
    ]
    second = generate_dataset.generate()
    second_hashes = [
        doc["sha256"] for case in second for doc in case["documents"].values()
    ]
    assert first_hashes == second_hashes
