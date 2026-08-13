from typing import Optional


class EmbeddingException(Exception):
    def __init__(self, message: str, chunk_id: Optional[str] = None, retry_count: int = 0):
        super().__init__(message)
        self.message = message
        self.chunk_id = chunk_id
        self.retry_count = retry_count