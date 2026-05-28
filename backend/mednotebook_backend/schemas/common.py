from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    database: str | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    per_page: int
    has_next: bool


class ErrorResponse(BaseModel):
    error: str
    detail: str
    code: str
