"""Authentication service with JWT and password hashing."""

import os
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from ..database import get_db_context, get_user_by_id, get_user_roles

# JWT settings
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "pad-salience-annotations-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# Bearer token scheme
security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    try:
        password_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_current_user_from_token(token: str) -> Optional[dict]:
    """Get current user from JWT token."""
    payload = decode_token(token)
    if not payload:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    async with get_db_context() as db:
        user = await get_user_by_id(db, int(user_id))
        if not user:
            return None

        # Get roles from database
        roles = await get_user_roles(db, int(user_id))

        # Fallback: if user_roles table is empty, use the role from users table
        if not roles:
            roles = [user["role"]]

        user["roles"] = roles

        # Get active_role from token, default to first role or user's role
        active_role = payload.get("active_role")
        if not active_role or active_role not in roles:
            active_role = roles[0] if roles else user["role"]

        user["active_role"] = active_role

        return user


def extract_token_from_request(request: Request) -> Optional[str]:
    """Extract token from Authorization header or cookie (can be called directly)."""
    # Try Authorization header first
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]

    # Try cookie
    token = request.cookies.get("access_token")
    if token:
        # Remove 'Bearer ' prefix if present
        if token.startswith("Bearer "):
            token = token[7:]
        return token

    return None


async def get_current_user_optional(request: Request) -> Optional[dict]:
    """Get the current user if authenticated, None otherwise. Can be called directly."""
    token = extract_token_from_request(request)
    if not token:
        return None
    return await get_current_user_from_token(token)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> dict:
    """Get the current authenticated user. Raises 401 if not authenticated."""
    # Try credentials from dependency first
    token = None
    if credentials:
        token = credentials.credentials
    else:
        token = extract_token_from_request(request)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_current_user_from_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def require_super_admin(user: dict = Depends(get_current_user)) -> dict:
    """Require the current user to be acting as super_admin."""
    if user.get("active_role") != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required"
        )
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Require the current user to be acting as admin or super_admin."""
    if user.get("active_role") not in ("admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user


async def require_specialist(user: dict = Depends(get_current_user)) -> dict:
    """Require the current user to be acting as a specialist (or admin/super_admin)."""
    if user.get("active_role") not in ("specialist", "admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Specialist access required"
        )
    return user


def create_token_with_role(user_id: int, roles: list[str], active_role: str) -> str:
    """Create a JWT token with roles and active role."""
    return create_access_token({
        "sub": str(user_id),
        "roles": roles,
        "active_role": active_role
    })
