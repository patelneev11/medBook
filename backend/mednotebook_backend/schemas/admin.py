import uuid

from pydantic import BaseModel


class CostPerUserItem(BaseModel):
    user_id: uuid.UUID
    user_name: str
    email: str
    total_cost_usd: float


class EmbeddingCostsResponse(BaseModel):
    total_cost_this_month_usd: float
    cost_per_user: list[CostPerUserItem]
    average_cost_per_document_usd: float
    projected_monthly_cost_usd: float