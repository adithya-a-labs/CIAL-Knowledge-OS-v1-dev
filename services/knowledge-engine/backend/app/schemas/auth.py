"""Authentication endpoint schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SignupRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=8, max_length=256)


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class AuthenticatedUser(BaseModel):
    id: str
    email: str
    display_name: str
    initials: str
    organization_name: str | None = None
    department_name: str | None = None
    role_names: list[str] = Field(default_factory=list)
    permission_names: list[str] = Field(default_factory=list)
    notifications_count: int = 0


class AuthResponse(BaseModel):
    user: AuthenticatedUser
    message: str


class LogoutResponse(BaseModel):
    message: str
