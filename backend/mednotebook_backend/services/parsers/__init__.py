from typing import Callable

from .csv_parser import extract_text_from_csv, extract_text_from_excel
from .exceptions import ParserException
from .image_parser import extract_text_from_image
from .pdf_parser import extract_text_from_pdf
from .text_parser import extract_text_from_text

__all__ = ["get_parser", "ParserException"]


def _parse_pdf(file_content: bytes, filename: str) -> dict:
    # extract_text_from_pdf doesn't take a filename — PDFs carry their own
    # title/author in-document metadata, unlike the other parsers.
    return extract_text_from_pdf(file_content)


# Mirrors mednotebook_backend.services.file_validator.ALLOWED_TYPES — every
# mime type accepted by uploads must have an entry here.
_PARSERS: dict = {
    "application/pdf": _parse_pdf,
    "text/csv": extract_text_from_csv,
    "text/plain": extract_text_from_text,
    "text/markdown": extract_text_from_text,
    "application/json": extract_text_from_text,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": extract_text_from_excel,
    # NOTE: legacy binary .xls is NOT actually readable — openpyxl only
    # supports the OOXML (.xlsx) format. A genuine old-format .xls upload
    # will fail with a clear ParserException from extract_text_from_excel
    # (it isn't a zip file), not a silent misparse. Add `xlrd` as a
    # dependency and branch here if real .xls support is needed.
    "application/vnd.ms-excel": extract_text_from_excel,
    "image/jpeg": extract_text_from_image,
    "image/png": extract_text_from_image,
    "image/tiff": extract_text_from_image,
}


def get_parser(mime_type: str) -> Callable[[bytes, str], dict]:
    """Return the extraction function for a mime type — always called as
    parser(file_content: bytes, filename: str) -> dict.
    """
    parser = _PARSERS.get(mime_type)
    if parser is None:
        raise ParserException(f"No parser available for mime type '{mime_type}'", file_type=mime_type)
    return parser