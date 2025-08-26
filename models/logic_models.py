from typing import List

from pydantic import BaseModel
from pydantic_core.core_schema import computed_field

from models.eneba_models import CompetitionEdge
from models.sheet_models import Payload


class CompareTarget(BaseModel):
    name: str
    price: float


class AnalysisResult(BaseModel):
    competitor_name: str | None = None
    competitive_price: float | None = None
    top_sellers_for_log: List[CompetitionEdge] | None = None
    sellers_below_min: List[CompetitionEdge] | None = None


class PayloadResult(BaseModel):
    status: int  # 1 for success, 0 for failure
    payload: Payload
    competition: list[CompetitionEdge] | None = None
    final_price: CompareTarget | None = None
    log_message: str | None = None


class CommissionPrice(BaseModel):
    price_without_commission: int
    price_with_commission: int

    def get_price_without_commission(self) -> float:
        return self.price_without_commission/100

    def get_price_with_commission(self) -> float:
        return self.price_with_commission/100
