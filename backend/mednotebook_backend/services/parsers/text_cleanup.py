import re
import unicodedata

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")


def clean_whitespace(text: str) -> str:
    """NFKC-normalize, strip control characters (keeping tab/newline/CR),
    and collapse runs of 3+ newlines down to a single paragraph break.
    """
    text = unicodedata.normalize("NFKC", text)
    text = _CONTROL_CHARS_RE.sub("", text)
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)
    return text