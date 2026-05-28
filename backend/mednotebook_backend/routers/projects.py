import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas.project import (
    MemberInvite,
    MemberResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    ProjectWithCount,
)

router = APIRouter(prefix="/projects", tags=["projects"])

_PLACEHOLDER_OWNER = uuid.UUID("00000000-0000-0000-0000-000000000001")
_PLACEHOLDER_PROJECT = uuid.UUID("00000000-0000-0000-0000-000000000002")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _placeholder_project(
    project_id: uuid.UUID = _PLACEHOLDER_PROJECT,
    name: str = "My Project",
    description: str | None = None,
    color: str = "#1B7F6E",
) -> ProjectResponse:
    now = _now()
    return ProjectResponse(
        id=project_id,
        owner_id=_PLACEHOLDER_OWNER,
        name=name,
        description=description,
        color=color,
        is_archived=False,
        created_at=now,
        updated_at=now,
    )


@router.get("", response_model=list[ProjectResponse])
async def list_projects(db: AsyncSession = Depends(get_db)):
    # TODO: filter by authenticated user — Session 4
    return []


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(payload: ProjectCreate, db: AsyncSession = Depends(get_db)):
    # TODO: save to DB with owner from JWT — Session 4
    return _placeholder_project(
        name=payload.name,
        description=payload.description,
        color=payload.color,
    )


@router.get("/{project_id}", response_model=ProjectWithCount)
async def get_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    # TODO: load from DB, check ownership — Session 4
    project = _placeholder_project(project_id=project_id)
    return ProjectWithCount(**project.model_dump(), document_count=0)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID, payload: ProjectUpdate, db: AsyncSession = Depends(get_db)
):
    # TODO: update in DB, check ownership — Session 4
    return _placeholder_project(
        project_id=project_id,
        name=payload.name or "My Project",
        description=payload.description,
        color=payload.color or "#1B7F6E",
    )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    # TODO: set is_archived=True in DB — Session 4
    pass


@router.get("/{project_id}/members", response_model=list[MemberResponse])
async def list_members(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    # TODO: load members from DB — Session 4
    return []


@router.post(
    "/{project_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_member(
    project_id: uuid.UUID, payload: MemberInvite, db: AsyncSession = Depends(get_db)
):
    # TODO: look up user by email, create membership — Session 4
    return MemberResponse(
        user_id=uuid.uuid4(),
        email=payload.email,
        full_name="Invited User",
        role=payload.role,
        joined_at=_now(),
    )


@router.delete(
    "/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_member(
    project_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    # TODO: delete membership row — Session 4
    pass
