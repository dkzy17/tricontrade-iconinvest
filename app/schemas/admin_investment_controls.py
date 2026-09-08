from decimal import Decimal

from pydantic import BaseModel, Field


class InvestmentROIAdjustmentIn(BaseModel):
    amount: Decimal = Field(..., decimal_places=2)
    reason: str = Field(..., min_length=1, max_length=500)


class InvestmentPauseIn(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class InvestmentResumeIn(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)
