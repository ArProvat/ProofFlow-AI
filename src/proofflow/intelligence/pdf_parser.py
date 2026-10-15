"""Read digital PDFs directly and use Tesseract for image-only pages."""

import os
import re
import shutil
from pathlib import Path
from typing import Literal

import pymupdf
import pytesseract
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ParseError(ValueError):
    pass


class OcrError(ParseError):
    pass


class ParsedWord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    page: int = Field(ge=1)
    bbox: tuple[float, float, float, float]

    @model_validator(mode="after")
    def valid_bbox(self):
        x0, y0, x1, y1 = self.bbox
        if not (0 <= x0 <= x1 <= 1 and 0 <= y0 <= y1 <= 1):
            raise ValueError("Word box must be normalized and ordered")
        return self


class ParsedPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(ge=1)
    text: str
    words: list[ParsedWord]
    method: Literal["native", "ocr"]


class ParsedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pages: list[ParsedPage] = Field(min_length=1, max_length=20)


def _box(x0, y0, x1, y1, width, height):
    return (
        max(0.0, min(1.0, x0 / width)),
        max(0.0, min(1.0, y0 / height)),
        max(0.0, min(1.0, x1 / width)),
        max(0.0, min(1.0, y1 / height)),
    )


def _ocr_image(image: Image.Image, page_number: int) -> ParsedPage:
    local = (
        Path(__file__).resolve().parents[3] / ".local_storage/tesseract/tesseract.exe"
    )
    pytesseract.pytesseract.tesseract_cmd = (
        os.getenv("TESSERACT_CMD") or shutil.which("tesseract") or str(local)
    )
    try:
        data = pytesseract.image_to_data(
            image.convert("RGB"),
            lang="eng",
            config="--psm 6",
            output_type=pytesseract.Output.DICT,
            timeout=90,
        )
    except (
        pytesseract.TesseractError,
        pytesseract.TesseractNotFoundError,
        RuntimeError,
    ) as error:
        raise OcrError(f"Tesseract OCR failed: {error}") from error
    words = []
    lines = {}
    for index, value in enumerate(data["text"]):
        value = re.sub(r"^[^\w]+", "", value.strip())
        if not value:
            continue
        left, top = data["left"][index], data["top"][index]
        width, height = data["width"][index], data["height"][index]
        words.append(
            ParsedWord(
                text=value,
                page=page_number,
                bbox=_box(
                    left, top, left + width, top + height, image.width, image.height
                ),
            )
        )
        key = (
            data["block_num"][index],
            data["par_num"][index],
            data["line_num"][index],
        )
        lines.setdefault(key, []).append(value)
    return ParsedPage(
        page=page_number,
        text="\n".join(" ".join(values) for values in lines.values()),
        words=words,
        method="ocr",
    )


def parse_document(path: Path, max_pages: int = 20) -> ParsedDocument:
    """Parse a PDF, PNG, or JPEG; never trust the filename alone as file type."""
    path = Path(path)
    if max_pages < 1 or max_pages > 20:
        raise ValueError("max_pages must be between 1 and 20")
    if not path.is_file() or path.stat().st_size > 25 * 1024 * 1024:
        raise ParseError("Missing or oversized document")
    try:
        with path.open("rb") as source:
            signature = source.read(8)
        if signature.startswith(b"%PDF-"):
            with pymupdf.open(path) as pdf:
                if pdf.is_encrypted or len(pdf) < 1 or len(pdf) > max_pages:
                    raise ParseError("Encrypted, empty, or over-limit PDF")
                pages = []
                for number, page in enumerate(pdf, 1):
                    native = page.get_text("words", sort=True)
                    if len(native) < 8:
                        pixmap = page.get_pixmap(dpi=200, alpha=False)
                        image = Image.frombytes(
                            "RGB", (pixmap.width, pixmap.height), pixmap.samples
                        )
                        pages.append(_ocr_image(image, number))
                        continue
                    words = [
                        ParsedWord(
                            text=item[4],
                            page=number,
                            bbox=_box(*item[:4], page.rect.width, page.rect.height),
                        )
                        for item in native
                    ]
                    pages.append(
                        ParsedPage(
                            page=number,
                            text=page.get_text("text", sort=True),
                            words=words,
                            method="native",
                        )
                    )
                return ParsedDocument(pages=pages)
        if signature.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff")):
            with Image.open(path) as image:
                image.load()
                return ParsedDocument(pages=[_ocr_image(image, 1)])
        raise ParseError("Unsupported document content")
    except (pymupdf.FileDataError, UnidentifiedImageError, OSError) as error:
        raise ParseError(f"Cannot read document: {error}") from error
