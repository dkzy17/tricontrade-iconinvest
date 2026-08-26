from pydantic import BaseModel, EmailStr, Field

class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    phone: str | None = None
    f_name: str | None = None
    l_name: str | None = None
    country: str = "USA"
    refId: str | None = None

class SigninIn(BaseModel):
    email: EmailStr
    password: str

class OTPIn(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6)

class ResetPasswordIn(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6)
    password: str = Field(min_length=8)

class UpdateUserIn(BaseModel):
    f_name: str | None = None
    l_name: str | None = None
    country: str | None = None
    phone: str | None = None
