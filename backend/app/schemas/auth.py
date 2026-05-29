"""Auth-related schemas."""
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserPublic(BaseModel):
    id: str
    email: str
    name: str | None = None
    plan: str = "starter"
    token_credits: float = 0.0
    token_credits_monthly: float = 0.0

    model_config = {"from_attributes": True}
