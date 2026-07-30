import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from ..models.project import MemberRole


class ProjectBase(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    color: str = "#1B7F6E"


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    color: Optional[str] = None


class ProjectResponse(ProjectBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectWithCount(ProjectResponse):
    document_count: int


# ── Members ───────────────────────────────────────────────────────────────────

class MemberInvite(BaseModel):
    email: EmailStr
    role: MemberRole


class MemberUpdate(BaseModel):
    role: MemberRole


class MemberResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: str
    role: MemberRole
    joined_at: datetime

    model_config = {"from_attributes": True}
