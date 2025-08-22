from typing import List

from pydantic import BaseModel

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
    status: int # 1 for success, 0 for failure
    payload: Payload
    competition: list[CompetitionEdge] | None = None
    final_price: CompareTarget | None = None
    log_message: str | None = None
