"""Content-addressed local storage for original uploads."""

import hashlib
import os
import tempfile
from pathlib import Path
from typing import BinaryIO

MIME_SIGNATURES = {
    "application/pdf": lambda b: b.startswith(b"%PDF-"),
    "image/png": lambda b: b.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": lambda b: b.startswith(b"\xff\xd8\xff"),
}


class InvalidUpload(ValueError):
    pass


class UploadTooLarge(InvalidUpload):
    pass


def storage_root() -> Path:
    return Path(os.getenv("STORAGE_ROOT", ".local_storage")).resolve()


def store_upload(
    source: BinaryIO, workspace_id: str, max_bytes: int, root: Path | None = None
) -> tuple[str, str, int, str]:
    root = root or storage_root()
    root.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    size = 0
    first = b""
    with tempfile.NamedTemporaryFile(dir=root, delete=False) as temporary:
        temp_path = Path(temporary.name)
        try:
            while chunk := source.read(1024 * 1024):
                if not first:
                    first = chunk[:8]
                size += len(chunk)
                if size > max_bytes:
                    raise UploadTooLarge("File exceeds upload limit")
                digest.update(chunk)
                temporary.write(chunk)
            mime_type = next(
                (mime for mime, matches in MIME_SIGNATURES.items() if matches(first)),
                None,
            )
            if mime_type is None:
                raise InvalidUpload("Unsupported file content")
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise
    sha256 = digest.hexdigest()
    key = f"{workspace_id}/{sha256[:2]}/{sha256}"
    destination = root / key
    destination.parent.mkdir(parents=True, exist_ok=True)
    # The key is derived only from trusted workspace context and file bytes.
    if destination.exists():
        temp_path.unlink()
    else:
        os.replace(temp_path, destination)
    return key, sha256, size, mime_type


def original_path(key: str, root: Path | None = None) -> Path:
    root = root or storage_root()
    path = (root / key).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Invalid storage key")
    return path
