import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class AIQuery(Base):
    __tablename__ = "ai_queries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sources: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    model_used: Mapped[str] = mapped_column(
        String(100), default="claude-sonnet-4-20250514", nullable=False
    )
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Which search request's results were used as this answer's sources —
    # lets cost/quality analysis correlate a search_type/timing (SearchLog)
    # with whether the AI answer it fed turned out helpful.
    search_log_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("search_logs.id", ondelete="SET NULL"), nullable=True
    )
    # Null = not yet rated by the user; set via PATCH /queries/{id}/feedback.
    helpful: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="queries")
    project: Mapped["Project"] = relationship("Project", back_populates="queries")
    search_log: Mapped[Optional["SearchLog"]] = relationship("SearchLog")
