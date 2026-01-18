"""Authentication API router."""

from fastapi import APIRouter, HTTPException, status, Response, Depends

from ..database import get_db_context, get_user_by_email, create_user, get_user_roles, add_user_role
from ..models import UserCreate, UserLogin, UserResponse, Token, SwitchRoleRequest
from ..services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_token_with_role,
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

        # Get user roles
        roles = await get_user_roles(db, user["id"])

        # Fallback: if user_roles table is empty, use the role from users table
        if not roles:
            roles = [user["role"]]

        # Default active role is admin if available, otherwise first role
        active_role = "admin" if "admin" in roles else roles[0]

        # Create token with roles
        token = create_token_with_role(user["id"], roles, active_role)

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
                roles=roles,
                active_role=active_role,
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
        roles=user.get("roles", [user["role"]]),
        active_role=user.get("active_role", user["role"]),
        expertise_level=user.get("expertise_level"),
        is_active=bool(user["is_active"]),
        created_at=user.get("created_at")
    )


@router.post("/switch-role", response_model=Token)
async def switch_role(data: SwitchRoleRequest, response: Response, user: dict = Depends(get_current_user)):
    """Switch the active role for the current user."""
    roles = user.get("roles", [user["role"]])

    if data.role not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have the '{data.role}' role"
        )

    # Create new token with the new active role
    token = create_token_with_role(user["id"], roles, data.role)

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
            roles=roles,
            active_role=data.role,
            expertise_level=user.get("expertise_level"),
            is_active=bool(user["is_active"]),
            created_at=user.get("created_at")
        )
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
