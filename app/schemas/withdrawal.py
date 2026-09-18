from pydantic import BaseModel, Field


class WithdrawalVerificationIn(BaseModel):
    code: str = Field(
        min_length=7,
        max_length=7,
        pattern=r"^[A-Za-z0-9]{7}$",
    )
