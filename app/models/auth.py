"""Authentication models."""

from pydantic import BaseModel
from typing import Optional, List


class UserCreate(BaseModel):
    """Request model for creating a user."""
    email: str
    name: str
    password: str
    role: str = "specialist"
    expertise_level: Optional[str] = None
    years_experience: Optional[int] = None
    training_date: Optional[str] = None
    institution: Optional[str] = None
    specializations: Optional[List[str]] = None


class UserUpdate(BaseModel):
    """Request model for updating a user."""
    email: Optional[str] = None
    name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    roles: Optional[List[str]] = None
    expertise_level: Optional[str] = None
    years_experience: Optional[int] = None
    training_date: Optional[str] = None
    institution: Optional[str] = None
    specializations: Optional[List[str]] = None
    is_active: Optional[bool] = None


class UserLogin(BaseModel):
    """Request model for user login."""
    email: str
    password: str


class UserResponse(BaseModel):
    """Response model for user data."""
    id: int
    email: str
    name: str
    role: str  # Primary role (for backward compatibility)
    roles: List[str] = []  # All roles the user has
    active_role: Optional[str] = None  # Currently active role
    expertise_level: Optional[str] = None
    years_experience: Optional[int] = None
    training_date: Optional[str] = None
    institution: Optional[str] = None
    specializations: Optional[List[str]] = None
    is_active: bool = True
    created_at: Optional[str] = None


class SwitchRoleRequest(BaseModel):
    """Request model for switching active role."""
    role: str


class Token(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
