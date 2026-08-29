from decimal import Decimal

from pydantic import BaseModel, Field


class DepositIn(BaseModel):
    amount: Decimal = Field(gt=0)


class InvestmentIn(BaseModel):
    amount: Decimal = Field(gt=0)
    name: str


class WithdrawalIn(BaseModel):
    amount: Decimal = Field(gt=0)
    address: str = Field(min_length=10)
    coin: str = Field(min_length=1)
    network: str = Field(min_length=1)


class PlanIn(BaseModel):
    name: str
    minimum: Decimal = Field(ge=0)
    maximun: Decimal = Field(ge=0)
    percentage: Decimal = Field(ge=0, le=100)
    wDate: str
    isActive: bool = True


class WalletIn(BaseModel):
    cryptocurrency: str = Field(min_length=1)
    network: str = Field(min_length=1)
    address: str = Field(min_length=10)
    isActive: bool = True