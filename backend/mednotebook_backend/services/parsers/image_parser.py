import logging
import os
import re
import tempfile
from datetime import datetime
from typing import Optional

import pytesseract
from PIL import Image, ImageFilter

from .exceptions import ParserException
from .text_cleanup import clean_whitespace

logger = logging.getLogger("mednotebook.parsers.image")

_TARGET_DPI = 300
_LOW_CONFIDENCE_THRESHOLD = 60

_JUNK_LINE_RE = re.compile(r"^[\W_]*$")
# Tokens that are mostly digits but got an O/l/I mixed in by the OCR engine
# confusing them with 0/1 — the classic lab-value misread.
_NUMERIC_TOKEN_RE = re.compile(r"\b[0-9OolI]{2,}\b")


def extract_text_from_image(file_content: bytes, filename: str) -> dict:
    """OCR an image file (JPEG/PNG/TIFF) via Tesseract, with light
    preprocessing to improve accuracy on small or low-contrast scans.
    """
    if not file_content:
        raise ParserException("Empty file content", file_type="image")

    tmp_path = _write_temp_image(file_content, filename)
    try:
        try:
            image = Image.open(tmp_path)
            image.load()
        except Exception as exc:
            raise ParserException("Could not open image file", file_type="image", original_error=exc) from exc

        original_size = image.size
        original_format = image.format
        original_mode = image.mode
        estimated_dpi = _estimate_dpi(image)
        created_date = _read_exif_datetime(image)

        processed = _preprocess_for_ocr(image, estimated_dpi)

        try:
            raw_text = pytesseract.image_to_string(processed, lang="eng", config="--psm 3")
            ocr_data = pytesseract.image_to_data(
                processed, lang="eng", config="--psm 3", output_type=pytesseract.Output.DICT
            )
        except Exception as exc:
            raise ParserException(
                "OCR failed — is tesseract installed? (brew install tesseract)",
                file_type="image",
                original_error=exc,
            ) from exc

        confidence = _average_confidence(ocr_data)
        text = _postprocess_ocr_text(raw_text)
        text = clean_whitespace(text).strip()
        word_count = len(text.split())

        metadata = {
            "title": filename,
            "author": None,
            "created_date": created_date,
            "modified_date": None,
            "width": original_size[0],
            "height": original_size[1],
            "format": original_format,
            "mode": original_mode,
            "estimated_dpi": estimated_dpi,
            "ocr_confidence": confidence,
        }
        if confidence is not None and confidence < _LOW_CONFIDENCE_THRESHOLD:
            metadata["warning"] = "Low OCR confidence — results may be inaccurate"

        return {
            "text": text,
            "pages": [{"page_number": 1, "text": text, "word_count": word_count}],
            "page_count": 1,
            "word_count": word_count,
            "is_scanned": True,
            "extraction_method": "tesseract",
            "metadata": metadata,
        }
    finally:
        os.unlink(tmp_path)


def _write_temp_image(file_content: bytes, filename: str) -> str:
    suffix = os.path.splitext(filename)[1] or ".img"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_content)
        return tmp.name


def _estimate_dpi(image: Image.Image) -> int:
    dpi_info = image.info.get("dpi")
    if dpi_info:
        try:
            return int(round(dpi_info[0]))
        except (TypeError, ValueError, IndexError):
            pass
    # No embedded DPI — estimate against a standard US Letter page width
    # (8.5in) as a rough baseline. An explicit estimate, not a measurement:
    # a cropped or non-page-shaped image won't reflect a real print DPI.
    width_px, _ = image.size
    return max(1, round(width_px / 8.5))


def _preprocess_for_ocr(image: Image.Image, estimated_dpi: int) -> Image.Image:
    processed = image.convert("L") if image.mode != "L" else image.copy()

    if estimated_dpi < _TARGET_DPI:
        scale = _TARGET_DPI / max(estimated_dpi, 1)
        new_size = (max(1, round(processed.width * scale)), max(1, round(processed.height * scale)))
        processed = processed.resize(new_size, Image.LANCZOS)

    return processed.filter(ImageFilter.SHARPEN)


def _average_confidence(ocr_data: dict) -> Optional[float]:
    scores = []
    for conf, text in zip(ocr_data.get("conf", []), ocr_data.get("text", [])):
        try:
            conf_val = float(conf)
        except (TypeError, ValueError):
            continue
        if conf_val < 0 or not str(text).strip():
            continue  # -1 is tesseract's sentinel for non-text regions
        scores.append(conf_val)
    if not scores:
        return None
    return round(sum(scores) / len(scores), 1)


def _postprocess_ocr_text(text: str) -> str:
    lines = [ln for ln in text.splitlines() if not _JUNK_LINE_RE.match(ln)]
    return _NUMERIC_TOKEN_RE.sub(_fix_ocr_token, "\n".join(lines))


def _fix_ocr_token(match: "re.Match") -> str:
    token = match.group(0)
    digit_count = sum(1 for c in token if c.isdigit())
    if digit_count == 0 or digit_count / len(token) < 0.5:
        return token  # not predominantly numeric — leave real words alone
    return token.replace("O", "0").replace("o", "0").replace("l", "1").replace("I", "1")


def _read_exif_datetime(image: Image.Image) -> Optional[str]:
    try:
        exif = image.getexif()
    except Exception:
        return None
    if not exif:
        return None
    raw = exif.get(306) or exif.get(36867)  # DateTime / DateTimeOriginal
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y:%m:%d %H:%M:%S").isoformat()
    except (ValueError, TypeError):
        return None