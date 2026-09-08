from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class AdminMoneyAdjustmentIn(BaseModel):
    field: str = Field(
        ...,
        description="balance, depositBalance, investBalance, referralBalance, or withdrawBalance",
    )
    amount: Decimal = Field(..., gt=0)
    reason: str = Field(..., min_length=1, max_length=500)

    @field_validator("field")
    @classmethod
    def validate_field(cls, value: str) -> str:
        allowed = {
            "balance",
            "depositBalance",
            "investBalance",
            "referralBalance",
            "withdrawBalance",
        }

        if value not in allowed:
            raise ValueError(
                "field must be one of: balance, depositBalance, "
                "investBalance, referralBalance, withdrawBalance"
            )

        return value

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("reason cannot be empty")

        return value
