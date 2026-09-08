from decimal import Decimal

from pydantic import BaseModel, Field


class AdminInvestmentIn(BaseModel):
    amount: Decimal = Field(..., gt=0)
    name: str = Field(..., min_length=1)
