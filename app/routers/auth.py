"""Authentication API router."""

from fastapi import APIRouter, HTTPException, status, Response, Depends

from ..database import get_db_context, get_user_by_email, create_user
from ..models import UserCreate, UserLogin, UserResponse, Token
from ..services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_admin,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=Token)
async def login(data: UserLogin, response: Response):
    """Authenticate user and return JWT token."""
    async with get_db_context() as db:
        user = await get_user_by_email(db, data.email)

        if not user or not verify_password(data.password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # Create token
        token = create_access_token({"sub": str(user["id"])})

        # Set cookie for browser-based access
        response.set_cookie(
            key="access_token",
            value=f"Bearer {token}",
            httponly=True,
            max_age=24 * 60 * 60,  # 24 hours
            samesite="lax"
        )

        return Token(
            access_token=token,
            user=UserResponse(
                id=user["id"],
                email=user["email"],
                name=user["name"],
                role=user["role"],
                expertise_level=user.get("expertise_level"),
                is_active=bool(user["is_active"]),
                created_at=user.get("created_at")
            )
        )


@router.post("/logout")
async def logout(response: Response):
    """Log out the current user by clearing the cookie."""
    response.delete_cookie("access_token")
    return {"status": "success", "message": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    """Get the current authenticated user."""
    return UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        role=user["role"],
        expertise_level=user.get("expertise_level"),
        is_active=bool(user["is_active"]),
        created_at=user.get("created_at")
    )


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_new_user(data: UserCreate, admin: dict = Depends(require_admin)):
    """Create a new user (admin only)."""
    async with get_db_context() as db:
        # Check if email already exists
        existing = await get_user_by_email(db, data.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        # Create user
        password_hash = hash_password(data.password)
        user_id = await create_user(
            db,
            email=data.email,
            name=data.name,
            password_hash=password_hash,
            role=data.role,
            expertise_level=data.expertise_level
        )

        return UserResponse(
            id=user_id,
            email=data.email,
            name=data.name,
            role=data.role,
            expertise_level=data.expertise_level,
            is_active=True
        )
