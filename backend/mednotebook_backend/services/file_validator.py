import os
import re

from ..config import settings
from ..exceptions import AppException

# mime_type → (label, allowed_extensions)
ALLOWED_TYPES: dict[str, tuple[str, tuple[str, ...]]] = {
    "application/pdf": ("PDF Document", (".pdf",)),
    "text/csv": ("CSV Spreadsheet", (".csv",)),
    "text/plain": ("Text File", (".txt",)),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (
        "Excel Spreadsheet",
        (".xlsx",),
    ),
    "application/vnd.ms-excel": ("Excel Spreadsheet", (".xls",)),
    "image/jpeg": ("JPEG Image", (".jpg", ".jpeg")),
    "image/png": ("PNG Image", (".png",)),
    "image/tiff": ("TIFF Image", (".tiff", ".tif")),
    "application/json": ("JSON File", (".json",)),
    "text/markdown": ("Markdown Document", (".md",)),
}

_ALLOWED_EXTENSIONS: set[str] = {
    ext for _, (_, exts) in ALLOWED_TYPES.items() for ext in exts
}


def validate_file(filename: str, mime_type: str, file_size_bytes: int) -> bool:
    """Run pre-upload checks. Raises AppException on any failure, returns True on success."""
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if file_size_bytes > max_bytes:
        raise AppException(
            f"File too large. Maximum size is {settings.max_upload_size_mb}MB",
            "FILE_TOO_LARGE",
            413,
        )

    ext = os.path.splitext(filename)[1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise AppException("File type not supported", "UNSUPPORTED_FILE_TYPE", 415)

    if mime_type not in ALLOWED_TYPES:
        raise AppException("File type not supported", "UNSUPPORTED_FILE_TYPE", 415)

    if (
        ".." in filename
        or "/" in filename
        or "\\" in filename
        or "\x00" in filename
        or len(filename) > 255
    ):
        raise AppException("Invalid filename", "INVALID_FILENAME", 400)

    return True


def sanitize_filename(filename: str) -> str:
    """Return a safe, storage-friendly version of the filename."""
    filename = os.path.basename(filename)

    name, ext = os.path.splitext(filename)
    ext = ext.lower()

    name = name.replace(" ", "_")
    name = re.sub(r"[^\w\-]", "", name)  # keep alphanumeric, dash, underscore

    # Truncate name so total length stays within 100, keeping the extension intact
    max_name_len = 100 - len(ext)
    return name[:max_name_len] + ext


def get_mime_type_label(mime_type: str) -> str:
    """Return a human-readable label for a MIME type, e.g. 'PDF Document'."""
    entry = ALLOWED_TYPES.get(mime_type)
    if entry:
        return entry[0]
    return "Unknown File Type"
