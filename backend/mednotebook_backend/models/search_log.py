import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .search_history import SearchType


class SearchLog(Base):
    """Analytics record for every search request — distinct from
    SearchHistory, which stores the plain query text for a user's own
    "recent searches" list. This stores only a SHA256 hash of the query
    (never plain text) plus timing/outcome data, for aggregate analysis of
    content gaps, semantic-vs-hybrid performance, and search latency.
    """

    __tablename__ = "search_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    search_type: Mapped[SearchType] = mapped_column(
        Enum(SearchType, values_callable=lambda enum_cls: [e.value for e in enum_cls]), nullable=False
    )
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    search_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    had_results: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    user: Mapped["User"] = relationship("User", back_populates="search_logs")
    project: Mapped["Project"] = relationship("Project", back_populates="search_logs")