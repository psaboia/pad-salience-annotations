"""Authentication models."""

from pydantic import BaseModel
from typing import Optional


class UserCreate(BaseModel):
    """Request model for creating a user."""
    email: str
    name: str
    password: str
    role: str = "specialist"
    expertise_level: Optional[str] = None


class UserLogin(BaseModel):
    """Request model for user login."""
    email: str
    password: str


class UserResponse(BaseModel):
    """Response model for user data."""
    id: int
    email: str
    name: str
    role: str
    expertise_level: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None


class Token(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
