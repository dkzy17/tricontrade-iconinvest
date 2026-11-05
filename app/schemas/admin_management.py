from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


class AdminStaffCreateIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=72)
    f_name: str | None = Field(default=None, max_length=100)
    l_name: str | None = Field(default=None, max_length=100)

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password cannot exceed 72 UTF-8 bytes.")
        return value


class AdminStaffRoleUpdateIn(BaseModel):
    role: Literal["admin", "user"]


class AdminStaffSuspensionIn(BaseModel):
    suspended: bool
