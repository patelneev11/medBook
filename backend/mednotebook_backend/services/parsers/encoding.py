import chardet

from .exceptions import ParserException


def decode_bytes(file_content: bytes, file_type: str = "text") -> str:
    """Decode bytes to text, using chardet's best guess first and falling
    back through common alternates (some lab exports use Latin-1 or UTF-16
    rather than UTF-8).
    """
    detected = chardet.detect(file_content)
    candidates = []
    if detected.get("encoding"):
        candidates.append(detected["encoding"])
    for enc in ("utf-8", "utf-16", "latin-1"):
        if enc not in candidates:
            candidates.append(enc)

    for enc in candidates:
        try:
            return file_content.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    # latin-1 (last candidate) maps every byte 0-255 to a codepoint and can
    # never raise UnicodeDecodeError, so this is unreachable in practice —
    # kept only so the function has an explicit failure mode.
    raise ParserException("Could not decode file with any supported encoding", file_type=file_type)