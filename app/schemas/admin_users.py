from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class VerifyUserIn(BaseModel):
    verified: bool


class SuspendUserIn(BaseModel):
    suspended: bool


class RoleIn(BaseModel):
    role: str = Field(min_length=1, max_length=20)

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in {"user", "admin"}:
            raise ValueError("Role must be user or admin")
        return value


class BalanceIn(BaseModel):
    field: str
    delta: Decimal

    @field_validator("field")
    @classmethod
    def validate_field(cls, value: str) -> str:
        if value not in {"balance", "investBalance"}:
            raise ValueError(
                "Field must be balance or investBalance"
            )
        return value
