import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class SearchType(str, enum.Enum):
    semantic = "semantic"
    keyword = "keyword"
    hybrid = "hybrid"


class SearchHistory(Base):
    """A logged search request — distinct from AIQuery, which logs a full
    RAG question+answer. This just records what was searched for, not
    what an AI said about it.
    """

    __tablename__ = "search_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    search_type: Mapped[SearchType] = mapped_column(
        Enum(SearchType, values_callable=lambda enum_cls: [e.value for e in enum_cls]), nullable=False
    )
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    user: Mapped["User"] = relationship("User", back_populates="search_history")
    project: Mapped["Project"] = relationship("Project", back_populates="search_history")