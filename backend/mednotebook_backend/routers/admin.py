import calendar
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.embedding_cost import EmbeddingCost
from ..models.user import User
from ..schemas.admin import CostPerUserItem, EmbeddingCostsResponse

# No admin auth yet — same placeholder-auth state as the rest of the API.
# These endpoints are consumed by the admin dashboard built in Session 17;
# this just makes the underlying data real ahead of that.
router = APIRouter(prefix="/admin", tags=["admin"])

_TOP_USERS_LIMIT = 10


def _month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


@router.get("/embedding-costs", response_model=EmbeddingCostsResponse)
async def get_embedding_costs(db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    month_start = _month_start(now)

    total_result = await db.execute(
        select(func.coalesce(func.sum(EmbeddingCost.cost_usd), 0)).where(
            EmbeddingCost.created_at >= month_start
        )
    )
    total_cost_this_month = float(total_result.scalar())

    per_user_result = await db.execute(
        select(
            User.id,
            User.full_name,
            User.email,
            func.sum(EmbeddingCost.cost_usd).label("total_cost"),
        )
        .join(EmbeddingCost, EmbeddingCost.user_id == User.id)
        .where(EmbeddingCost.created_at >= month_start)
        .group_by(User.id, User.full_name, User.email)
        .order_by(func.sum(EmbeddingCost.cost_usd).desc())
        .limit(_TOP_USERS_LIMIT)
    )
    cost_per_user = [
        CostPerUserItem(
            user_id=row.id, user_name=row.full_name, email=row.email, total_cost_usd=float(row.total_cost)
        )
        for row in per_user_result.all()
    ]

    avg_result = await db.execute(
        select(func.avg(EmbeddingCost.cost_usd)).where(EmbeddingCost.created_at >= month_start)
    )
    avg_cost = avg_result.scalar()
    average_cost_per_document = float(avg_cost) if avg_cost is not None else 0.0

    # Straight-line projection from the rate observed so far this month.
    days_elapsed = max((now - month_start).days + 1, 1)
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    projected_monthly_cost = (total_cost_this_month / days_elapsed) * days_in_month

    return EmbeddingCostsResponse(
        total_cost_this_month_usd=total_cost_this_month,
        cost_per_user=cost_per_user,
        average_cost_per_document_usd=average_cost_per_document,
        projected_monthly_cost_usd=round(projected_monthly_cost, 6),
    )