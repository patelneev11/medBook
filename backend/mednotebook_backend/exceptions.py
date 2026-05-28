class AppException(Exception):
    """Raise this anywhere in the app to return a structured error response.

    Example:
        raise AppException("Document not found", "DOCUMENT_NOT_FOUND", 404)
    """

    def __init__(self, message: str, code: str, status_code: int = 400) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)
