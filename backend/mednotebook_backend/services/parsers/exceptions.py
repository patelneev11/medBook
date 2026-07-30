from typing import Optional

from ...exceptions import AppException


class ParserException(AppException):
    """Raised when a document parser cannot extract usable text from a file.

    Example:
        raise ParserException("PDF extraction failed", file_type="pdf", original_error=exc) from exc
    """

    def __init__(
        self,
        message: str,
        file_type: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        self.file_type = file_type
        self.original_error = original_error
        full_message = f"{message}: {original_error}" if original_error else message
        super().__init__(full_message, "PARSER_ERROR", 422)