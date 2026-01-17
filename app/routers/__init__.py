"""API routers for PAD Salience Annotation System."""

from .auth import router as auth_router
from .admin import router as admin_router
from .specialist import router as specialist_router

__all__ = ["auth_router", "admin_router", "specialist_router"]
