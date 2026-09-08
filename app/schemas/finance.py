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
    w_date: str | None = None
    is_active: bool | None = None
    wDate: str | None = None
    isActive: bool | None = None

    @property
    def duration(self) -> str:
        value = self.w_date if self.w_date is not None else self.wDate
        if value is None:
            raise ValueError("w_date is required")
        return value.strip()

    @property
    def active(self) -> bool:
        if self.is_active is not None:
            return self.is_active
        if self.isActive is not None:
            return self.isActive
        return True


class WalletIn(BaseModel):
    cryptocurrency: str = Field(min_length=1)
    network: str = Field(min_length=1)
    address: str = Field(min_length=10)
    isActive: bool = True