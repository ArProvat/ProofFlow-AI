"""Import source files from the Day 2 manifest without loading ground truth."""

import argparse
import hashlib
import json
from pathlib import Path

from proofflow.db import make_session_factory
from proofflow.persistence import create_case, ingest_document


def import_day2(manifest: Path, data_root: Path, split: str, limit: int | None = None):
    root = data_root.resolve()
    session_factory = make_session_factory()
    count = 0
    with manifest.open(encoding="utf-8") as stream:
        for line in stream:
            item = json.loads(line)
            if item["split"] != split:
                continue
            # Validate the entire case before writing any of its files or records.
            sources = []
            for entry in item["documents"].values():
                path = (root / entry["file"]).resolve()
                if not path.is_relative_to(root) or not path.is_file():
                    raise ValueError(f"Invalid document path: {entry['file']}")
                if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
                    raise ValueError(f"PDF hash mismatch: {path}")
                sources.append((entry["document_type"], path))
            ids = {}
            for document_type, path in sources:
                with path.open("rb") as source, session_factory() as session:
                    document, _ = ingest_document(
                        session, source, path.name, document_type
                    )
                    ids[document_type] = document.id
            with session_factory() as session:
                create_case(session, ids, source_key=item["case_id"])
            count += 1
            if limit is not None and count >= limit:
                break
    return count


def main():
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command", required=True)
    importer = subcommands.add_parser("import-day2")
    importer.add_argument("--manifest", type=Path, required=True)
    importer.add_argument("--data-root", type=Path, required=True)
    importer.add_argument("--split", required=True)
    importer.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.command == "import-day2":
        print(import_day2(args.manifest, args.data_root, args.split, args.limit))


if __name__ == "__main__":
    main()
