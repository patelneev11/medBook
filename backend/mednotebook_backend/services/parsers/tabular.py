import re
from typing import Optional

# Common clinical/lab units, shared by the PDF parser (protecting lab values
# in prose from being chunk-split) and the CSV/Excel parser (detecting which
# columns hold lab values).
LAB_UNITS = (
    r"mg/dL|mmol/L|g/dL|IU/L|mEq/L|U/L|ng/mL|pg/mL|mIU/L|mcg/mL|"
    r"µg/dL|ug/dL|mmHg|bpm|kg|cm|mL|%"
)
# \s* (not \s+): unlike PDF prose, a spreadsheet cell may read "7.2mg/dL"
# with no space at all.
LAB_VALUE_RE = re.compile(rf"(\d+\.?\d*)\s*({LAB_UNITS})(?![A-Za-z0-9])", re.IGNORECASE)
# For matching a unit against a COLUMN NAME (e.g. "Glucose_mg/dL") rather
# than a value — no preceding digit required, unlike LAB_VALUE_RE.
LAB_UNIT_NAME_RE = re.compile(LAB_UNITS, re.IGNORECASE)

PATIENT_ID_COLUMN_RE = re.compile(r"(mrn|patient[_\s]?id|subject[_\s]?id|patient[_\s]?no)", re.IGNORECASE)
DATE_COLUMN_RE = re.compile(r"(date|_dt$|^dt_|\bdob\b)", re.IGNORECASE)


def format_table_as_markdown(rows: list) -> str:
    """Render a list of rows (first row = header) as a markdown table."""
    rows = [row for row in rows if row is not None]
    if not rows:
        return ""

    def clean_cell(cell: Optional[object]) -> str:
        if cell is None:
            return ""
        return re.sub(r"\s+", " ", str(cell)).strip().replace("|", "\\|")

    cleaned = [[clean_cell(c) for c in row] for row in rows]
    col_count = max(len(r) for r in cleaned)
    cleaned = [r + [""] * (col_count - len(r)) for r in cleaned]

    header, *body = cleaned
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * col_count) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in body)
    return "\n".join(lines)