import enum
import uuid
from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

# sentence-transformers/all-MiniLM-L6-v2 output size
EMBEDDING_DIM = 384


class ChunkType(str, enum.Enum):
    paragraph = "paragraph"
    table = "table"
    list = "list"
    header_content = "header+content"


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # values_callable: bind using the member's *value* ("header+content"),
    # not its default Python name ("header_content") — the DB enum type's
    # labels are the values, so the mismatch on this one member (the only
    # one where name != value) would otherwise fail on insert.
    chunk_type: Mapped[Optional[ChunkType]] = mapped_column(
        Enum(ChunkType, values_callable=lambda enum_cls: [e.value for e in enum_cls]), nullable=True
    )
    embedding: Mapped[Optional[list]] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    embedding_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    embedding_generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # DB-computed (GENERATED ALWAYS ... STORED) — never set this from Python.
    content_tsv: Mapped[Optional[str]] = mapped_column(TSVECTOR, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")
