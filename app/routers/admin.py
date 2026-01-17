"""Admin API router."""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List

from ..database import (
    get_db_context,
    get_all_samples,
    get_all_studies,
    get_study_by_id,
    create_study,
    update_study_status,
    add_samples_to_study,
    get_study_samples,
    get_specialists,
    create_assignment,
    get_study_assignments,
    get_study_progress,
    get_all_users,
    create_user,
    update_user,
    deactivate_user,
    get_user_by_id_include_inactive,
    get_user_by_email,
)
from ..models import (
    StudyCreate,
    StudyUpdate,
    StudyResponse,
    StudyWithSamples,
    SampleResponse,
    SampleSelectionRequest,
    AssignmentCreate,
    AssignmentResponse,
)
from ..models.auth import UserCreate, UserUpdate, UserResponse
from ..models.studies import SampleInStudy, AssignmentProgress
from ..services.auth import require_admin, hash_password

router = APIRouter(prefix="/api/admin", tags=["admin"])


# Sample endpoints
@router.get("/samples", response_model=List[SampleResponse])
async def list_samples(_: dict = Depends(require_admin)):
    """Get all available samples."""
    async with get_db_context() as db:
        samples = await get_all_samples(db)
        return [SampleResponse(**s) for s in samples]


# Study endpoints
@router.get("/studies", response_model=List[StudyResponse])
async def list_studies(_: dict = Depends(require_admin)):
    """Get all studies."""
    async with get_db_context() as db:
        studies = await get_all_studies(db)
        return [StudyResponse(**s) for s in studies]


@router.post("/studies", response_model=StudyResponse, status_code=status.HTTP_201_CREATED)
async def create_new_study(data: StudyCreate, admin: dict = Depends(require_admin)):
    """Create a new study."""
    async with get_db_context() as db:
        study_id = await create_study(
            db,
            name=data.name,
            description=data.description,
            instructions=data.instructions,
            created_by=admin["id"]
        )
        study = await get_study_by_id(db, study_id)
        return StudyResponse(**study)


@router.get("/studies/{study_id}", response_model=StudyWithSamples)
async def get_study(study_id: int, _: dict = Depends(require_admin)):
    """Get a specific study with its samples."""
    async with get_db_context() as db:
        study = await get_study_by_id(db, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")

        samples = await get_study_samples(db, study_id)
        sample_models = [SampleInStudy(**s) for s in samples]

        return StudyWithSamples(
            **study,
            samples=sample_models,
            sample_count=len(sample_models)
        )


@router.put("/studies/{study_id}", response_model=StudyResponse)
async def update_study(study_id: int, data: StudyUpdate, _: dict = Depends(require_admin)):
    """Update a study."""
    async with get_db_context() as db:
        study = await get_study_by_id(db, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")

        # Update fields
        if data.name is not None:
            await db.execute(
                "UPDATE studies SET name = ?, updated_at = datetime('now') WHERE id = ?",
                (data.name, study_id)
            )
        if data.description is not None:
            await db.execute(
                "UPDATE studies SET description = ?, updated_at = datetime('now') WHERE id = ?",
                (data.description, study_id)
            )
        if data.instructions is not None:
            await db.execute(
                "UPDATE studies SET instructions = ?, updated_at = datetime('now') WHERE id = ?",
                (data.instructions, study_id)
            )
        if data.status is not None:
            await update_study_status(db, study_id, data.status)
        else:
            await db.commit()

        study = await get_study_by_id(db, study_id)
        return StudyResponse(**study)


@router.delete("/studies/{study_id}")
async def delete_study(study_id: int, _: dict = Depends(require_admin)):
    """Delete a study (only if draft)."""
    async with get_db_context() as db:
        study = await get_study_by_id(db, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")

        if study["status"] not in ("draft", "archived"):
            raise HTTPException(
                status_code=400,
                detail="Can only delete draft or archived studies"
            )

        await db.execute("DELETE FROM studies WHERE id = ?", (study_id,))
        await db.commit()

        return {"status": "success", "message": "Study deleted"}


@router.post("/studies/{study_id}/activate")
async def activate_study(study_id: int, _: dict = Depends(require_admin)):
    """Activate a study (move from draft to active)."""
    async with get_db_context() as db:
        study = await get_study_by_id(db, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")

        if study["status"] != "draft":
            raise HTTPException(
                status_code=400,
                detail="Can only activate draft studies"
            )

        # Check that study has samples
        samples = await get_study_samples(db, study_id)
        if not samples:
            raise HTTPException(
                status_code=400,
                detail="Cannot activate study without samples"
            )

        # Check that study has assignments
        assignments = await get_study_assignments(db, study_id)
        if not assignments:
            raise HTTPException(
                status_code=400,
                detail="Cannot activate study without specialist assignments"
            )

        await update_study_status(db, study_id, "active")

        return {"status": "success", "message": "Study activated"}


@router.post("/studies/{study_id}/pause")
async def pause_study(study_id: int, _: dict = Depends(require_admin)):
    """Pause an active study."""
    async with get_db_context() as db:
        study = await get_study_by_id(db, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")

        if study["status"] != "active":
            raise HTTPException(
                status_code=400,
                detail="Can only pause active studies"
            )

        await update_study_status(db, study_id, "paused")

        return {"status": "success", "message": "Study paused"}


@router.post("/studies/{study_id}/resume")
async def resume_study(study_id: int, _: dict = Depends(require_admin)):
    """Resume a paused study."""
    async with get_db_context() as db:
        study = await get_study_by_id(db, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")

        if study["status"] != "paused":
            raise HTTPException(
                status_code=400,
                detail="Can only resume paused studies"
            )

        await update_study_status(db, study_id, "active")

        return {"status": "success", "message": "Study resumed"}


# Sample management for studies
@router.get("/studies/{study_id}/samples", response_model=List[SampleInStudy])
async def get_study_sample_list(study_id: int, _: dict = Depends(require_admin)):
    """Get samples assigned to a study."""
    async with get_db_context() as db:
        study = await get_study_by_id(db, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")

        samples = await get_study_samples(db, study_id)
        return [SampleInStudy(**s) for s in samples]


@router.post("/studies/{study_id}/samples")
async def set_study_samples(
    study_id: int,
    data: SampleSelectionRequest,
    _: dict = Depends(require_admin)
):
    """Set the samples for a study (replaces existing)."""
    async with get_db_context() as db:
        study = await get_study_by_id(db, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")

        if study["status"] != "draft":
            raise HTTPException(
                status_code=400,
                detail="Can only modify samples for draft studies"
            )

        # Clear existing samples
        await db.execute(
            "DELETE FROM study_samples WHERE study_id = ?",
            (study_id,)
        )
        await db.commit()

        # Add new samples
        await add_samples_to_study(db, study_id, data.sample_ids)

        return {"status": "success", "sample_count": len(data.sample_ids)}


# Specialist management
@router.get("/specialists", response_model=List[dict])
async def list_specialists(_: dict = Depends(require_admin)):
    """Get all specialists."""
    async with get_db_context() as db:
        specialists = await get_specialists(db)
        return [
            {
                "id": s["id"],
                "email": s["email"],
                "name": s["name"],
                "expertise_level": s.get("expertise_level"),
                "is_active": bool(s["is_active"])
            }
            for s in specialists
        ]


# User management endpoints
@router.get("/users", response_model=List[UserResponse])
async def list_users(
    include_inactive: bool = Query(False, description="Include inactive users"),
    _: dict = Depends(require_admin)
):
    """Get all users."""
    async with get_db_context() as db:
        users = await get_all_users(db, include_inactive=include_inactive)
        return [
            UserResponse(
                id=u["id"],
                email=u["email"],
                name=u["name"],
                role=u["role"],
                expertise_level=u.get("expertise_level"),
                years_experience=u.get("years_experience"),
                training_date=u.get("training_date"),
                institution=u.get("institution"),
                specializations=u.get("specializations"),
                is_active=bool(u["is_active"]),
                created_at=u.get("created_at")
            )
            for u in users
        ]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_new_user(data: UserCreate, _: dict = Depends(require_admin)):
    """Create a new user."""
    async with get_db_context() as db:
        # Check if email already exists
        existing = await get_user_by_email(db, data.email)
        if existing:
            raise HTTPException(
                status_code=400,
                detail="User with this email already exists"
            )

        password_hash = hash_password(data.password)

        user_id = await create_user(
            db,
            email=data.email,
            name=data.name,
            password_hash=password_hash,
            role=data.role,
            expertise_level=data.expertise_level,
            years_experience=data.years_experience,
            training_date=data.training_date,
            institution=data.institution,
            specializations=data.specializations
        )

        user = await get_user_by_id_include_inactive(db, user_id)
        return UserResponse(
            id=user["id"],
            email=user["email"],
            name=user["name"],
            role=user["role"],
            expertise_level=user.get("expertise_level"),
            years_experience=user.get("years_experience"),
            training_date=user.get("training_date"),
            institution=user.get("institution"),
            specializations=user.get("specializations"),
            is_active=bool(user["is_active"]),
            created_at=user.get("created_at")
        )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, _: dict = Depends(require_admin)):
    """Get a specific user."""
    async with get_db_context() as db:
        user = await get_user_by_id_include_inactive(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return UserResponse(
            id=user["id"],
            email=user["email"],
            name=user["name"],
            role=user["role"],
            expertise_level=user.get("expertise_level"),
            years_experience=user.get("years_experience"),
            training_date=user.get("training_date"),
            institution=user.get("institution"),
            specializations=user.get("specializations"),
            is_active=bool(user["is_active"]),
            created_at=user.get("created_at")
        )


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_existing_user(user_id: int, data: UserUpdate, _: dict = Depends(require_admin)):
    """Update a user."""
    async with get_db_context() as db:
        user = await get_user_by_id_include_inactive(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Check if email is being changed and already exists
        if data.email and data.email != user["email"]:
            existing = await get_user_by_email(db, data.email)
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail="User with this email already exists"
                )

        # Hash password if being changed
        password_hash = None
        if data.password:
            password_hash = hash_password(data.password)

        await update_user(
            db,
            user_id=user_id,
            email=data.email,
            name=data.name,
            password_hash=password_hash,
            role=data.role,
            expertise_level=data.expertise_level,
            years_experience=data.years_experience,
            training_date=data.training_date,
            institution=data.institution,
            specializations=data.specializations,
            is_active=data.is_active
        )

        user = await get_user_by_id_include_inactive(db, user_id)
        return UserResponse(
            id=user["id"],
            email=user["email"],
            name=user["name"],
            role=user["role"],
            expertise_level=user.get("expertise_level"),
            years_experience=user.get("years_experience"),
            training_date=user.get("training_date"),
            institution=user.get("institution"),
            specializations=user.get("specializations"),
            is_active=bool(user["is_active"]),
            created_at=user.get("created_at")
        )


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, admin: dict = Depends(require_admin)):
    """Deactivate a user (soft delete)."""
    if user_id == admin["id"]:
        raise HTTPException(
            status_code=400,
            detail="Cannot deactivate your own account"
        )

    async with get_db_context() as db:
        user = await get_user_by_id_include_inactive(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        await deactivate_user(db, user_id)

        return {"status": "success", "message": "User deactivated"}


# Assignment management
@router.get("/studies/{study_id}/assignments", response_model=List[AssignmentResponse])
async def get_assignments(study_id: int, _: dict = Depends(require_admin)):
    """Get all assignments for a study."""
    async with get_db_context() as db:
        study = await get_study_by_id(db, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")

        assignments = await get_study_assignments(db, study_id)
        return [AssignmentResponse(**a) for a in assignments]


@router.post("/studies/{study_id}/assignments", response_model=AssignmentResponse)
async def create_new_assignment(
    study_id: int,
    data: AssignmentCreate,
    _: dict = Depends(require_admin)
):
    """Assign a specialist to a study."""
    async with get_db_context() as db:
        study = await get_study_by_id(db, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")

        if study["status"] not in ("draft", "active"):
            raise HTTPException(
                status_code=400,
                detail="Cannot add assignments to this study"
            )

        # Fetch specialist profile for snapshot
        specialist = await get_user_by_id_include_inactive(db, data.specialist_id)
        if not specialist:
            raise HTTPException(status_code=404, detail="Specialist not found")

        try:
            assignment_id = await create_assignment(
                db,
                study_id,
                data.specialist_id,
                expertise_level_snapshot=specialist.get("expertise_level"),
                years_experience_snapshot=specialist.get("years_experience"),
                training_date_snapshot=specialist.get("training_date")
            )
        except Exception as e:
            if "UNIQUE constraint" in str(e):
                raise HTTPException(
                    status_code=400,
                    detail="Specialist already assigned to this study"
                )
            raise

        assignments = await get_study_assignments(db, study_id)
        assignment = next((a for a in assignments if a["id"] == assignment_id), None)

        return AssignmentResponse(**assignment)


@router.delete("/studies/{study_id}/assignments/{specialist_id}")
async def delete_assignment(
    study_id: int,
    specialist_id: int,
    _: dict = Depends(require_admin)
):
    """Remove a specialist from a study."""
    async with get_db_context() as db:
        study = await get_study_by_id(db, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")

        if study["status"] not in ("draft",):
            raise HTTPException(
                status_code=400,
                detail="Can only remove assignments from draft studies"
            )

        await db.execute(
            "DELETE FROM assignments WHERE study_id = ? AND specialist_id = ?",
            (study_id, specialist_id)
        )
        await db.commit()

        return {"status": "success", "message": "Assignment removed"}


# Progress tracking
@router.get("/studies/{study_id}/progress")
async def get_progress(study_id: int, _: dict = Depends(require_admin)):
    """Get detailed progress for a study."""
    async with get_db_context() as db:
        study = await get_study_by_id(db, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")

        progress = await get_study_progress(db, study_id)
        progress["study"] = StudyResponse(**study).model_dump()

        return progress
